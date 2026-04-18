"""
Pytest configuration and shared fixtures for the ADWF backend test suite.

Owned by: Nisarg (Workflow Engine)
"""

from __future__ import annotations

import uuid
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workflow.state import PipelineState, initial_state


# ── Shared fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def sample_run_id() -> str:
    """A fixed UUID so snapshot-style assertions stay stable across runs."""
    return "d5f3a1c0-1234-4b5e-89ab-0123456789ab"


@pytest.fixture
def fresh_run_id() -> str:
    """A new UUID for each test — use when tests must not share state."""
    return str(uuid.uuid4())


@pytest.fixture
def base_state(fresh_run_id: str) -> PipelineState:
    return initial_state(
        run_id=fresh_run_id,
        idea="A mobile app that helps busy professionals track their daily water intake",
    )


@pytest.fixture
def state_after_research(base_state: PipelineState) -> PipelineState:
    """PipelineState with a fully populated research_report."""
    base_state["project_brief"] = {
        "title": "HydroTrack",
        "normalized_idea": "A mobile app that helps busy professionals track daily water intake",
        "domain": "HealthTech",
        "target_platform": "web",
    }
    base_state["research_report"] = {
        "problem_statement": {
            "core_problem": "People forget to drink enough water",
            "affected_users": "Busy professionals aged 25–45",
            "current_solutions_fail_because": "Too complex or not contextual",
            "opportunity_window": "Wearable health tracking growth",
        },
        "market": {
            "industry": "HealthTech",
            "tam_usd": 5_000_000_000,
            "sam_usd": 500_000_000,
            "som_usd": 10_000_000,
            "growth_rate_yoy_percent": 12.4,
            "key_trends": ["AI health coaching", "Wearable integration"],
        },
        "personas": [
            {
                "name": "Sarah",
                "age_range": "28-35",
                "occupation": "Software Engineer",
                "goals": ["Stay hydrated", "Improve focus"],
                "frustrations": ["Forgetting to drink", "Complex apps"],
                "tech_savviness": "high",
                "primary_device": "iPhone",
            }
        ],
        "pain_points": [
            {
                "pain": "No contextual reminders",
                "severity": "high",
                "frequency": "frequent",
                "existing_workaround": "Phone alarms",
            }
        ],
        "competitors": [
            {
                "name": "WaterMinder",
                "url": "https://waterminder.com",
                "positioning": "Simple tracking",
                "pricing_model": "Freemium",
                "key_features": ["Reminders", "Graphs"],
                "weaknesses": ["No AI", "No wearable sync"],
                "user_sentiment": "Mixed",
            }
        ],
        "viability": {
            "revenue_models": ["Freemium", "Subscription"],
            "recommended_model": "Freemium",
            "estimated_arpu": "$2/month",
            "go_to_market_strategy": "App Store + Health influencers",
            "viability_score": 7,
        },
        "feasibility": {
            "technical_risks": ["Wearable API access"],
            "complexity": "low",
            "estimated_mvp_weeks": 4,
            "key_dependencies": ["HealthKit", "Google Fit"],
            "feasibility_score": 8,
        },
    }
    base_state["phases"]["research"]["status"] = "COMPLETE"
    return base_state


@pytest.fixture
def mock_redis():
    """
    Patch all Redis calls used in the workflow so tests run without
    a live Redis instance.
    """
    with (
        patch("app.core.redis.acquire_agent_lock", new_callable=AsyncMock, return_value=True),
        patch("app.core.redis.release_agent_lock", new_callable=AsyncMock),
        patch("app.core.redis.set_agent_status_cache", new_callable=AsyncMock),
        patch("app.core.redis.publish_event", new_callable=AsyncMock),
        patch("app.core.redis.publish_log_line", new_callable=AsyncMock),
    ):
        yield


@pytest.fixture
def mock_db():
    """
    Patch all PostgreSQL calls so tests run without a live database.
    """
    with (
        patch("app.workflow.executor._persist_agent_run", new_callable=AsyncMock),
        patch("app.workflow.executor._persist_artifact", new_callable=AsyncMock),
    ):
        yield


@pytest.fixture
def minimal_research_output(fresh_run_id: str) -> Dict[str, Any]:
    """Minimal valid ResearchAgentOutput dict for use as mock agent return value."""
    return {
        "run_id": fresh_run_id,
        "research_report": {
            "problem_statement": {
                "core_problem": "Test problem",
                "affected_users": "Test users",
                "current_solutions_fail_because": "They are bad",
                "opportunity_window": "Now",
            },
            "market": {"industry": "TestTech", "key_trends": []},
            "personas": [
                {
                    "name": "Alice",
                    "age_range": "20-30",
                    "occupation": "Tester",
                    "goals": ["Test things"],
                    "frustrations": ["Bugs"],
                    "tech_savviness": "high",
                    "primary_device": "laptop",
                }
            ],
            "pain_points": [
                {"pain": "Test pain", "severity": "low", "frequency": "rare"}
            ],
            "competitors": [],
            "viability": {
                "revenue_models": ["Free"],
                "recommended_model": "Free",
                "go_to_market_strategy": "Direct",
                "viability_score": 5,
            },
            "feasibility": {
                "complexity": "low",
                "estimated_mvp_weeks": 2,
                "feasibility_score": 9,
            },
        },
        "embedding_ids": [],
    }
