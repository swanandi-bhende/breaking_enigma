"""
Agent Interfaces - Provides structured interfaces for inter-agent communication.
This ensures robust data flow between Research → PM → Designer agents.
"""

from typing import Dict, Any, List, Optional, Protocol, runtime_checkable
from pydantic import BaseModel
from abc import ABC, abstractmethod

from ..schemas.research_pm import (
    ResearchAgentInput,
    ResearchAgentOutput,
    ResearchReport,
    PMAgentInput,
    PMAgentOutput,
    PRD,
)
from ..schemas.designer import DesignerAgentInput, DesignerAgentOutput, DesignSpec


class AgentInputProtocol(Protocol):
    """Protocol for agent input validation."""

    run_id: str


class AgentOutputProtocol(Protocol):
    """Protocol for agent output."""

    run_id: str


class ResearchToPMConnector:
    """Handles data transformation from Research Agent to PM Agent."""

    @staticmethod
    def transform_output(research_output: ResearchAgentOutput) -> PMAgentInput:
        """
        Transform Research Agent output to PM Agent input.

        Args:
            research_output: Output from Research Agent

        Returns:
            Validated PMAgentInput
        """
        return PMAgentInput(
            run_id=research_output.run_id,
            research_report=research_output.research_report,
        )

    @staticmethod
    def extract_key_context(research_output: ResearchAgentOutput) -> Dict[str, Any]:
        """Extract key context for PM Agent prompt enhancement."""
        report = research_output.research_report

        return {
            "core_problem": report.problem_statement.core_problem,
            "target_persona": report.personas[0].name
            if report.personas
            else "target user",
            "top_pain_point": report.pain_points[0].pain if report.pain_points else "",
            "viability_score": report.viability.viability_score,
            "complexity": report.feasibility.complexity,
        }


class PMToDesignerConnector:
    """Handles data transformation from PM Agent to Designer Agent."""

    @staticmethod
    def transform_output(
        pm_output: PMAgentOutput, research_embedding_ids: Optional[List[str]] = None
    ) -> DesignerAgentInput:
        """
        Transform PM Agent output to Designer Agent input.

        Args:
            pm_output: Output from PM Agent
            research_embedding_ids: Optional RAG context IDs from Research Agent

        Returns:
            Validated DesignerAgentInput
        """
        return DesignerAgentInput(
            run_id=pm_output.run_id,
            prd=pm_output.prd.dict(),
            research_context_embedding_ids=research_embedding_ids or [],
        )

    @staticmethod
    def extract_api_requirements(prd: PRD) -> Dict[str, Any]:
        """Extract API requirements from PRD for Designer Agent."""
        return {
            "required_endpoints": [
                {"story_id": us.id, "action": us.action, "outcome": us.outcome}
                for us in prd.user_stories
                if us.priority == "must-have"
            ],
            "mvp_features": [f.name for f in prd.features.mvp],
            "user_flow_screens": [step.screen_name for step in prd.user_flow],
        }


class AgentHub:
    """
    Central hub for agent orchestration.
    Provides unified interface for running agents in sequence or parallel.
    """

    def __init__(self):
        self._research_agent = None
        self._pm_agent = None
        self._designer_agent = None

    @property
    def research_agent(self):
        if self._research_agent is None:
            from .research import run_research_agent

            self._research_agent = run_research_agent
        return self._research_agent

    @property
    def pm_agent(self):
        if self._pm_agent is None:
            from .product_manager import run_pm_agent

            self._pm_agent = run_pm_agent
        return self._pm_agent

    @property
    def designer_agent(self):
        if self._designer_agent is None:
            from .designer import run_designer_agent

            self._designer_agent = run_designer_agent
        return self._designer_agent

    async def run_pipeline(
        self, run_id: str, project_brief: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run the full Research → PM → Designer pipeline.

        Args:
            run_id: Unique run identifier
            project_brief: Project brief from Orchestrator

        Returns:
            Dict containing all agent outputs
        """
        research_input = ResearchAgentInput(
            run_id=str(run_id), project_brief=project_brief, tools_available=["web_search"]
        )

        research_output = await self.research_agent(research_input)

        pm_input = ResearchToPMConnector.transform_output(research_output)
        pm_output = await self.pm_agent(pm_input)

        designer_input = PMToDesignerConnector.transform_output(
            pm_output, research_output.embedding_ids
        )
        designer_output = await self.designer_agent(designer_input)

        return {
            "run_id": run_id,
            "research": research_output.dict(),
            "pm": pm_output.dict(),
            "designer": designer_output.dict(),
        }


agent_hub = AgentHub()
