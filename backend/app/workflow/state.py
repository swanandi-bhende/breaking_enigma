"""
PipelineState TypedDict — the single shared memory object that flows
through every node in the LangGraph StateGraph.

Owned by: Nisarg (Workflow Engine & Agent Orchestration)
"""

from typing import TypedDict, Literal, Optional, List, Dict, Any


class PipelineState(TypedDict):
    # ── Identity ────────────────────────────────────────────────────────────
    run_id: str
    """UUID of the active pipeline run (maps to pipeline_runs.id in PG)."""

    user_id: Optional[str]
    """Optional user UUID for authenticated sessions."""

    # ── Input ────────────────────────────────────────────────────────────────
    idea: str
    """Raw product idea string provided by the user."""

    config: Dict[str, Any]
    """
    Pipeline configuration dict:
      - max_qa_iterations (int, default 3)
      - skip_agents (list[str])
      - human_checkpoints (list[str])
      - llm_model (str, default 'llama-3.3-70b-versatile')
      - target_platform (str: 'web' | 'mobile' | 'api-only')
    """

    # ── Orchestrator ─────────────────────────────────────────────────────────
    project_brief: Optional[Dict[str, Any]]
    """
    Structured project brief produced by the Orchestrator:
      - title (str)
      - normalized_idea (str)
      - domain (str)
      - target_platform (str)
    """

    run_state: Literal["INITIALIZING", "RUNNING", "AWAITING_HUMAN", "FAILED", "COMPLETE"]
    """Top-level pipeline run state."""

    phases: Dict[str, Dict[str, Any]]
    """
    Per-agent phase status keyed by agent name.
    Each value: { status, started_at, completed_at, iteration, error }
    """

    # ── Agent Outputs ────────────────────────────────────────────────────────
    research_report: Optional[Dict[str, Any]]
    """Full ResearchAgentOutput.research_report object."""

    research_embedding_ids: Optional[List[str]]
    """Qdrant vector IDs for research embeddings (used by Designer via RAG)."""

    prd: Optional[Dict[str, Any]]
    """Full PMAgentOutput.prd object."""

    design_spec: Optional[Dict[str, Any]]
    """Full DesignerAgentOutput.design_spec object."""

    developer_output: Optional[Dict[str, Any]]
    """Full DeveloperAgentOutput object."""

    qa_output: Optional[Dict[str, Any]]
    """Full QAAgentOutput object (most recent QA run)."""

    devops_output: Optional[Dict[str, Any]]
    """Full DevOpsAgentOutput object."""

    docs_output: Optional[Dict[str, Any]]
    """Full DocumentationAgentOutput object."""

    # ── QA Loop Control ──────────────────────────────────────────────────────
    qa_iteration: int
    """Current QA iteration count (starts at 0, increments on each FAIL)."""

    max_qa_iterations: int
    """Maximum allowed QA iterations before routing to human review."""

    # ── Artifact References ───────────────────────────────────────────────────
    artifact_urls: Optional[Dict[str, str]]
    """
    S3/local paths or download tokens for all output artifacts,
    keyed by agent name. Populated as agents complete.
    """

    # ── Error Tracking ────────────────────────────────────────────────────────
    error: Optional[str]
    """Last pipeline-level error message (if run_state == 'FAILED')."""

    last_failed_agent: Optional[str]
    """Name of the agent that caused the current FAILED state."""


def initial_state(
    run_id: str,
    idea: str,
    config: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> PipelineState:
    """
    Factory function: returns a valid initial PipelineState for a new run.
    Called by the Orchestrator when initialising a pipeline.
    """
    cfg = config or {}
    return PipelineState(
        run_id=run_id,
        user_id=user_id,
        idea=idea,
        config={
            "max_qa_iterations": cfg.get("max_qa_iterations", 3),
            "skip_agents": cfg.get("skip_agents", []),
            "human_checkpoints": cfg.get("human_checkpoints", []),
            "llm_model": cfg.get("llm_model", "llama-3.3-70b-versatile"),
            "target_platform": cfg.get("target_platform", "web"),
        },
        project_brief=None,
        run_state="INITIALIZING",
        phases={
            agent: {"status": "PENDING", "started_at": None, "completed_at": None, "iteration": 0, "error": None}
            for agent in [
                "research",
                "product_manager",
                "designer",
                "developer",
                "qa",
                "devops",
                "documentation",
            ]
        },
        research_report=None,
        research_embedding_ids=None,
        prd=None,
        design_spec=None,
        developer_output=None,
        qa_output=None,
        devops_output=None,
        docs_output=None,
        qa_iteration=0,
        max_qa_iterations=cfg.get("max_qa_iterations", 3),
        artifact_urls={},
        error=None,
        last_failed_agent=None,
    )
