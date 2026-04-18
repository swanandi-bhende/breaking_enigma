"""
Tests for the Workflow Engine — Nisarg's domain.

Covers:
  - PipelineState initialisation
  - Schema validation (valid + invalid payloads)
  - Agent executor (mocked agent functions)
  - QA routing logic
  - Human checkpoint suspend/resume
  - Redis event emission

Run with:
    pytest tests/test_workflow.py -v
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.workflow.state import PipelineState, initial_state
from app.schemas.agents import (
    AGENT_SCHEMAS,
    OrchestratorInput,
    ResearchAgentOutput,
    PMAgentOutput,
    QAAgentOutput,
    QAVerdict,
    QARoute,
    RoutingDecision,
)
from app.workflow.graph import route_after_qa
from app.workflow.executor import (
    AgentInputValidationError,
    AgentOutputValidationError,
    AgentLockError,
    validate_agent_input,
    validate_agent_output,
    _extract_input,
)
from app.core.events import EventType, build_event, pipeline_events_channel


# ════════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def run_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def base_state(run_id: str) -> PipelineState:
    return initial_state(run_id=run_id, idea="A mobile app to track daily water intake for busy professionals")


# ════════════════════════════════════════════════════════════════════════════
# PipelineState
# ════════════════════════════════════════════════════════════════════════════

class TestInitialState:
    def test_creates_valid_state(self, run_id):
        state = initial_state(run_id=run_id, idea="Test idea that is long enough")
        assert state["run_id"] == run_id
        assert state["run_state"] == "INITIALIZING"
        assert state["qa_iteration"] == 0
        assert state["max_qa_iterations"] == 3
        assert state["project_brief"] is None

    def test_all_agents_start_pending(self, base_state):
        for agent in ["research", "product_manager", "designer", "developer", "qa", "devops", "documentation"]:
            assert base_state["phases"][agent]["status"] == "PENDING"

    def test_config_defaults(self, base_state):
        cfg = base_state["config"]
        assert cfg["max_qa_iterations"] == 3
        assert cfg["target_platform"] == "web"
        assert cfg["skip_agents"] == []
        assert cfg["human_checkpoints"] == []

    def test_custom_config_override(self, run_id):
        state = initial_state(
            run_id=run_id,
            idea="An app for something interesting enough",
            config={"max_qa_iterations": 5, "target_platform": "mobile"},
        )
        assert state["config"]["max_qa_iterations"] == 5
        assert state["config"]["target_platform"] == "mobile"
        assert state["max_qa_iterations"] == 5


# ════════════════════════════════════════════════════════════════════════════
# Schema validation
# ════════════════════════════════════════════════════════════════════════════

class TestSchemaValidation:
    def test_orchestrator_input_valid(self, run_id):
        inp = OrchestratorInput(run_id=uuid.UUID(run_id), idea="Build a recipe app for college students")
        assert str(inp.run_id) == run_id

    def test_orchestrator_input_idea_too_short(self, run_id):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            OrchestratorInput(run_id=uuid.UUID(run_id), idea="short")

    def test_agent_schemas_registry_complete(self):
        expected_agents = {
            "orchestrator", "research", "product_manager", "designer",
            "developer", "qa", "devops", "documentation"
        }
        assert set(AGENT_SCHEMAS.keys()) == expected_agents

    def test_validate_agent_input_unknown_agent(self):
        with pytest.raises(ValueError, match="Unknown agent"):
            validate_agent_input("nonexistent_agent", {})

    def test_validate_agent_input_invalid_payload(self, run_id):
        with pytest.raises(AgentInputValidationError):
            validate_agent_input("research", {"run_id": run_id})  # missing project_brief


# ════════════════════════════════════════════════════════════════════════════
# Input extraction
# ════════════════════════════════════════════════════════════════════════════

class TestExtractInput:
    def test_research_input(self, base_state):
        base_state["project_brief"] = {
            "title": "WaterTrack",
            "normalized_idea": "An app to track water intake",
            "domain": "HealthTech",
            "target_platform": "web",
        }
        inp = _extract_input("research", base_state)
        assert inp["run_id"] == base_state["run_id"]
        assert "project_brief" in inp
        assert "tools_available" in inp

    def test_developer_includes_qa_feedback(self, base_state):
        base_state["design_spec"] = {}
        base_state["prd"] = {}
        base_state["qa_output"] = {"verdict": "FAIL", "bugs": []}
        inp = _extract_input("developer", base_state)
        assert inp["qa_feedback"] is not None

    def test_unknown_agent_raises(self, base_state):
        with pytest.raises(ValueError, match="No input extractor"):
            _extract_input("unknown_agent", base_state)


# ════════════════════════════════════════════════════════════════════════════
# QA routing logic
# ════════════════════════════════════════════════════════════════════════════

def _make_qa_state(verdict: str, iteration: int, max_iterations: int, route_to: str, run_id: str) -> PipelineState:
    state = initial_state(run_id=run_id, idea="A sufficiently long idea for testing purposes here")
    state["qa_output"] = {
        "verdict": verdict,
        "qa_score": 85.0 if verdict == "PASS" else 45.0,
        "iteration": iteration,
        "traceability_matrix": [],
        "bugs": [],
        "routing_decision": {"route_to": route_to, "reason": "test", "fix_instructions": []},
        "must_have_coverage_percent": 100.0 if verdict == "PASS" else 60.0,
        "critical_bugs_count": 0,
    }
    state["qa_iteration"] = iteration
    state["max_qa_iterations"] = max_iterations
    return state


class TestQARouting:
    def test_qa_pass_routes_to_parallel_final(self, run_id):
        state = _make_qa_state("PASS", 1, 3, "devops_and_docs", run_id)
        assert route_after_qa(state) == "parallel_final"

    def test_qa_fail_iteration_1_routes_to_developer(self, run_id):
        state = _make_qa_state("FAIL", 1, 3, "developer", run_id)
        assert route_after_qa(state) == "developer"

    def test_qa_fail_at_max_iteration_routes_to_end(self, run_id):
        state = _make_qa_state("FAIL", 3, 3, "human_review", run_id)
        assert route_after_qa(state) == "__end__"

    def test_failed_pipeline_state_routes_to_end(self, run_id):
        state = _make_qa_state("FAIL", 1, 3, "developer", run_id)
        state["run_state"] = "FAILED"
        assert route_after_qa(state) == "__end__"

    def test_human_review_route_to_ends(self, run_id):
        state = _make_qa_state("FAIL", 2, 3, "human_review", run_id)
        assert route_after_qa(state) == "__end__"


# ════════════════════════════════════════════════════════════════════════════
# Executor (mocked)
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestAgentExecutor:
    async def test_successful_execution(self, base_state):
        """Executor should call agent_fn, validate output, return dict."""
        from app.workflow.executor import agent_executor

        # Minimal valid research output
        mock_output = {
            "run_id": base_state["run_id"],
            "research_report": {
                "problem_statement": {
                    "core_problem": "People forget to drink water",
                    "affected_users": "Busy professionals",
                    "current_solutions_fail_because": "Apps are too complex",
                    "opportunity_window": "Wearable growth",
                },
                "market": {
                    "industry": "HealthTech",
                    "key_trends": ["Mobile health", "Wearables"],
                },
                "personas": [
                    {
                        "name": "Sarah",
                        "age_range": "25-35",
                        "occupation": "Software Engineer",
                        "goals": ["Stay healthy"],
                        "frustrations": ["Forgetting water"],
                        "tech_savviness": "high",
                        "primary_device": "iPhone",
                    }
                ],
                "pain_points": [
                    {
                        "pain": "No reminder system",
                        "severity": "high",
                        "frequency": "frequent",
                    }
                ],
                "competitors": [],
                "viability": {
                    "revenue_models": ["Freemium"],
                    "recommended_model": "Freemium",
                    "go_to_market_strategy": "App Store",
                    "viability_score": 7,
                },
                "feasibility": {
                    "complexity": "low",
                    "estimated_mvp_weeks": 4,
                    "feasibility_score": 8,
                },
            },
            "embedding_ids": [],
        }

        async def mock_agent_fn(input_dict):
            return mock_output

        base_state["project_brief"] = {
            "title": "WaterTrack",
            "normalized_idea": "An app to track daily water intake",
            "domain": "HealthTech",
            "target_platform": "web",
        }

        with (
            patch("app.workflow.executor.acquire_agent_lock", new_callable=AsyncMock, return_value=True),
            patch("app.workflow.executor.release_agent_lock", new_callable=AsyncMock),
            patch("app.workflow.executor.set_agent_status_cache", new_callable=AsyncMock),
            patch("app.workflow.executor.publish_event", new_callable=AsyncMock),
            patch("app.workflow.executor.publish_log_line", new_callable=AsyncMock),
            patch("app.workflow.executor._persist_agent_run", new_callable=AsyncMock),
            patch("app.workflow.executor._persist_artifact", new_callable=AsyncMock),
        ):
            result = await agent_executor("research", mock_agent_fn, base_state)

        assert result["run_id"] == base_state["run_id"]
        assert "research_report" in result

    async def test_lock_error_on_duplicate_run(self, base_state):
        """Executor should raise AgentLockError if lock cannot be acquired."""
        from app.workflow.executor import agent_executor

        base_state["project_brief"] = {
            "title": "Test",
            "normalized_idea": "Test idea",
            "domain": "Tech",
            "target_platform": "web",
        }

        with patch("app.workflow.executor.acquire_agent_lock", new_callable=AsyncMock, return_value=False):
            with pytest.raises(AgentLockError):
                await agent_executor("research", AsyncMock(), base_state)


# ════════════════════════════════════════════════════════════════════════════
# Event builder
# ════════════════════════════════════════════════════════════════════════════

class TestEventBuilding:
    def test_build_event_has_required_fields(self, run_id):
        payload_str = build_event(EventType.PIPELINE_STARTED, run_id)
        payload = json.loads(payload_str)
        assert payload["event_type"] == "PIPELINE_STARTED"
        assert payload["run_id"] == run_id
        assert "timestamp" in payload

    def test_build_event_with_metadata(self, run_id):
        payload_str = build_event(
            EventType.AGENT_STATUS_CHANGED,
            run_id,
            metadata={"new_status": "RUNNING"},
            agent_name="research",
        )
        payload = json.loads(payload_str)
        assert payload["new_status"] == "RUNNING"
        assert payload["agent_name"] == "research"

    def test_pipeline_events_channel_format(self, run_id):
        channel = pipeline_events_channel(run_id)
        assert channel == f"pipeline:{run_id}:events"
