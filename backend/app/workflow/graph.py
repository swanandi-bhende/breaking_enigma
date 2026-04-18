"""
LangGraph StateGraph definition — the brain of the ADWF pipeline.

Defines:
  - All agent nodes (thin wrappers that call agent_executor)
  - Linear flow: research → pm → designer → developer → qa
  - Conditional routing after QA (PASS / FAIL / human_review)
  - Parallel final stage (DevOps + Documentation via asyncio.gather)
  - Human checkpoint support at any configured stage

Owned by: Nisarg (Workflow Engine & Agent Orchestration)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from app.core.events import EventType
from app.core.redis import publish_event, signal_human_checkpoint, wait_for_human_approval
from app.workflow.executor import agent_executor
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)


async def _publish_global_state_snapshot(state: PipelineState) -> None:
    """Push the latest full pipeline state to the dashboard."""
    await publish_event(
        state["run_id"],
        EventType.GLOBAL_STATE_UPDATED,
        metadata={"state": dict(state)},
    )


# ════════════════════════════════════════════════════════════════════════════
# Agent stub imports
# Each of these is implemented by Aditya / Anshul in backend/app/agents/.
# They are imported here as plain async functions; the executor wraps them.
# ════════════════════════════════════════════════════════════════════════════

def _load_agent(module_path: str, fn_name: str):
    """
    Lazy loader — imports an agent function only when the node is invoked.
    This prevents circular imports and allows stub-based unit testing.
    """
    async def _stub(input_dict: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
        import importlib
        mod = importlib.import_module(module_path)
        fn = getattr(mod, fn_name)
        return await fn(input_dict)
    _stub.__name__ = fn_name
    return _stub


# Lazy references — modules don't need to exist for the graph to compile
_run_research = _load_agent("app.agents.research", "run_research_agent")
_run_pm = _load_agent("app.agents.product_manager", "run_pm_agent")
_run_designer = _load_agent("app.agents.designer", "run_designer_agent")
_run_developer = _load_agent("app.agents.developer", "run_developer_agent")
_run_qa = _load_agent("app.agents.qa", "run_qa_agent")
_run_devops = _load_agent("app.agents.devops", "run_devops_agent")
_run_documentation = _load_agent("app.agents.documentation", "run_documentation_agent")


# ════════════════════════════════════════════════════════════════════════════
# Human checkpoint helper
# ════════════════════════════════════════════════════════════════════════════

async def _maybe_checkpoint(state: PipelineState, after_agent: str) -> PipelineState:
    """
    If `after_agent` is listed in config.human_checkpoints, suspend the
    pipeline until the user approves/rejects via the API.

    Returns an updated state with run_state = AWAITING_HUMAN temporarily,
    then either continues (RUNNING) or marks as FAILED (user rejected).
    """
    checkpoints: list = state["config"].get("human_checkpoints", [])
    if after_agent not in checkpoints:
        return state  # no checkpoint — pass through

    run_id = state["run_id"]
    logger.info("[graph] Human checkpoint triggered after '%s' for run_id=%s", after_agent, run_id)

    await signal_human_checkpoint(run_id, after_agent)

    # This blocks the asyncio coroutine (and therefore the graph node)
    # until a human approves or rejects.
    result = await wait_for_human_approval(run_id)

    if result["approved"]:
        await publish_event(run_id, EventType.PIPELINE_RESUMED, metadata={"after_agent": after_agent})
        return {**state, "run_state": "RUNNING"}
    else:
        feedback = result.get("feedback", "Rejected by user")
        await publish_event(run_id, EventType.PIPELINE_FAILED, metadata={"reason": feedback})
        return {
            **state,
            "run_state": "FAILED",
            "error": f"Human rejected pipeline after '{after_agent}': {feedback}",
            "last_failed_agent": after_agent,
        }


# ════════════════════════════════════════════════════════════════════════════
# Graph nodes — each is an async function that accepts & returns PipelineState
# ════════════════════════════════════════════════════════════════════════════

async def node_research(state: PipelineState) -> PipelineState:
    output = await agent_executor("research", _run_research, state, iteration=1)
    state = {
        **state,
        "research_report": output.get("research_report"),
        "research_embedding_ids": output.get("embedding_ids", []),
    }
    state["phases"]["research"]["status"] = "COMPLETE"
    await _publish_global_state_snapshot(state)
    return await _maybe_checkpoint(state, "research")


async def node_product_manager(state: PipelineState) -> PipelineState:
    # Skip if in skip_agents list
    if "product_manager" in state["config"].get("skip_agents", []):
        state["phases"]["product_manager"]["status"] = "SKIPPED"
        await _publish_global_state_snapshot(state)
        return state

    output = await agent_executor("product_manager", _run_pm, state, iteration=1)
    state = {**state, "prd": output.get("prd")}
    state["phases"]["product_manager"]["status"] = "COMPLETE"
    await _publish_global_state_snapshot(state)
    return await _maybe_checkpoint(state, "product_manager")


async def node_designer(state: PipelineState) -> PipelineState:
    if "designer" in state["config"].get("skip_agents", []):
        state["phases"]["designer"]["status"] = "SKIPPED"
        await _publish_global_state_snapshot(state)
        return state

    output = await agent_executor("designer", _run_designer, state, iteration=1)
    state = {**state, "design_spec": output.get("design_spec")}
    state["phases"]["designer"]["status"] = "COMPLETE"
    await _publish_global_state_snapshot(state)
    return await _maybe_checkpoint(state, "designer")


async def node_developer(state: PipelineState) -> PipelineState:
    iteration = state.get("qa_iteration", 0) + 1  # 1 on first run, 2+ on re-runs
    output = await agent_executor("developer", _run_developer, state, iteration=iteration)
    state = {**state, "developer_output": output}
    state["phases"]["developer"]["status"] = "COMPLETE"
    state["phases"]["developer"]["iteration"] = iteration
    await _publish_global_state_snapshot(state)
    return state


async def node_qa(state: PipelineState) -> PipelineState:
    qa_iter = state.get("qa_iteration", 0) + 1
    output = await agent_executor("qa", _run_qa, state, iteration=qa_iter)

    state = {
        **state,
        "qa_output": output,
        "qa_iteration": qa_iter,
    }
    state["phases"]["qa"]["status"] = "COMPLETE"
    state["phases"]["qa"]["iteration"] = qa_iter

    # Emit QA verdict event so the dashboard can show score + routing animation
    verdict = output.get("verdict")
    run_id = state["run_id"]
    await publish_event(
        run_id,
        EventType.QA_VERDICT,
        metadata={
            "verdict": verdict,
            "qa_score": output.get("qa_score"),
            "bugs_count": len(output.get("bugs", [])),
            "critical_bugs_count": output.get("critical_bugs_count", 0),
            "iteration": qa_iter,
        },
        agent_name="qa",
    )

    if verdict == "FAIL":
        await publish_event(
            run_id,
            EventType.QA_ROUTING_LOOP,
            metadata={"from": "qa", "to": "developer", "iteration": qa_iter},
        )

    await _publish_global_state_snapshot(state)

    return state


async def node_parallel_final(state: PipelineState) -> PipelineState:
    """
    Run DevOps and Documentation agents in parallel via asyncio.gather.
    Neither depends on the other so there is no ordering constraint.
    """
    run_id = state["run_id"]
    logger.info("[graph] Starting parallel final stage for run_id=%s", run_id)

    devops_task = asyncio.create_task(
        agent_executor("devops", _run_devops, state, iteration=1)
    )
    docs_task = asyncio.create_task(
        agent_executor("documentation", _run_documentation, state, iteration=1)
    )

    results = await asyncio.gather(devops_task, docs_task, return_exceptions=True)
    devops_result, docs_result = results

    # Handle failures gracefully — one failing shouldn't kill the other
    if isinstance(devops_result, Exception):
        logger.error("[graph] DevOps agent failed in parallel stage: %s", devops_result)
        state["phases"]["devops"]["status"] = "FAILED"
        state["phases"]["devops"]["error"] = str(devops_result)
        devops_result = None
    else:
        state["phases"]["devops"]["status"] = "COMPLETE"

    if isinstance(docs_result, Exception):
        logger.error("[graph] Documentation agent failed in parallel stage: %s", docs_result)
        state["phases"]["documentation"]["status"] = "FAILED"
        state["phases"]["documentation"]["error"] = str(docs_result)
        docs_result = None
    else:
        state["phases"]["documentation"]["status"] = "COMPLETE"

    state = {
        **state,
        "devops_output": devops_result,
        "docs_output": docs_result,
        "run_state": "COMPLETE",
    }

    await _publish_global_state_snapshot(state)
    await publish_event(run_id, EventType.PIPELINE_COMPLETE)
    return state


# ════════════════════════════════════════════════════════════════════════════
# Routing function (conditional edge after QA)
# ════════════════════════════════════════════════════════════════════════════

def route_after_qa(state: PipelineState) -> str:
    """
    Decide the next node after QA completes.

    Rules:
      - QA PASS                               → parallel_final
      - QA FAIL + iterations < max            → developer (loop)
      - QA FAIL + iterations >= max           → human_review (END)
      - Pipeline already FAILED (user rejected checkpoint) → END
    """
    if state.get("run_state") == "FAILED":
        return "__end__"

    qa_output = state.get("qa_output", {})
    verdict = qa_output.get("verdict", "FAIL")
    routing = qa_output.get("routing_decision", {})
    route_to = routing.get("route_to", "developer")

    if verdict == "PASS" or route_to == "devops_and_docs":
        logger.info("[graph] QA PASS → parallel_final")
        return "parallel_final"

    if route_to == "human_review":
        logger.info("[graph] QA max iterations reached → human_review (END)")
        return "__end__"

    # QA FAIL — loop back to developer
    qa_iter = state.get("qa_iteration", 0)
    max_iter = state.get("max_qa_iterations", 3)

    if qa_iter >= max_iter:
        logger.info(
            "[graph] QA FAIL after %d/%d iterations → human_review (END)",
            qa_iter, max_iter,
        )
        return "__end__"

    logger.info("[graph] QA FAIL (iteration %d/%d) → developer", qa_iter, max_iter)
    return "developer"


# ════════════════════════════════════════════════════════════════════════════
# Graph builder
# ════════════════════════════════════════════════════════════════════════════

def build_pipeline_graph() -> Any:
    """
    Compile and return the LangGraph StateGraph for the full ADWF pipeline.

    Node order:
        research → product_manager → designer → developer → qa
          ↑                                              |
          └─── (on FAIL, ≤ max_iterations) ─────────────┘
                                                        |
                                          (on PASS) → parallel_final → END
                                          (max iters) → END (human review)

    Returns:
        A compiled LangGraph runnable (invoke / astream compatible).
    """
    graph = StateGraph(PipelineState)

    # ── Register nodes ────────────────────────────────────────────────────────
    graph.add_node("research", node_research)
    graph.add_node("product_manager", node_product_manager)
    graph.add_node("designer", node_designer)
    graph.add_node("developer", node_developer)
    graph.add_node("qa", node_qa)
    graph.add_node("parallel_final", node_parallel_final)

    # ── Entry point ────────────────────────────────────────────────────────────
    graph.set_entry_point("research")

    # ── Linear edges ──────────────────────────────────────────────────────────
    graph.add_edge("research", "product_manager")
    graph.add_edge("product_manager", "designer")
    graph.add_edge("designer", "developer")
    graph.add_edge("developer", "qa")

    # ── Conditional routing at QA ─────────────────────────────────────────────
    graph.add_conditional_edges(
        "qa",
        route_after_qa,
        {
            "developer": "developer",           # FAIL loop
            "parallel_final": "parallel_final", # PASS
            "__end__": END,                     # Human review / max retries
        },
    )

    # ── Final stage → END ─────────────────────────────────────────────────────
    graph.add_edge("parallel_final", END)

    compiled = graph.compile()
    logger.info("[graph] Pipeline graph compiled — %d nodes", 6)
    return compiled


# ── Singleton graph instance (compiled once at import time) ──────────────────
pipeline_graph = build_pipeline_graph()
