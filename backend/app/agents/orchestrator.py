"""
Orchestrator Agent — the pipeline entry point.

Responsibilities:
  1. Parse and normalise the raw idea string into a structured ProjectBrief
  2. Initialise the pipeline_runs and global_state records in PostgreSQL
  3. Set run_state = RUNNING and emit PIPELINE_STARTED event
  4. Return the updated PipelineState with project_brief populated

The Orchestrator does NOT run any other agents itself — that is the
LangGraph graph's job.  It simply prepares the state for the first
real agent (Research).

Owned by: Nisarg (Workflow Engine & Agent Orchestration)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.events import EventType
from app.core.redis import publish_event, publish_log_line
from app.schemas.agents import OrchestratorInput, OrchestratorOutput, ProjectBrief, RunState
from app.workflow.state import PipelineState, initial_state

logger = logging.getLogger(__name__)

# ── System prompt for idea normalisation ─────────────────────────────────────

_NORMALISE_SYSTEM_PROMPT = """\
You are the Orchestrator in an autonomous product development system.

Your job is to parse the user's raw product idea and return ONLY a valid JSON
object matching the schema below.  Do NOT include any explanatory text,
markdown code fences, or preamble.

OUTPUT SCHEMA:
{
  "title": "Short product name (3-5 words)",
  "normalized_idea": "One clear sentence describing what the product does and for whom",
  "domain": "Industry/product category (e.g. 'EdTech', 'HealthTech', 'Developer Tools')",
  "target_platform": "web | mobile | api-only"
}

Rules:
- title must be compelling and concise
- normalized_idea must be a complete, unambiguous description
- domain must be a recognisable industry vertical
- target_platform must be exactly one of: web, mobile, api-only
"""


def _fallback_brief(idea: str, target_platform_hint: str) -> Dict[str, Any]:
    short_title = " ".join(idea.strip().split()[:4]).strip()
    if not short_title:
        short_title = "Generated Product"
    allowed_platforms = {"web", "mobile", "api-only"}
    platform = target_platform_hint if target_platform_hint in allowed_platforms else "web"
    return {
        "title": short_title[:50],
        "normalized_idea": idea.strip() or "Build a useful software product for target users.",
        "domain": "General Software",
        "target_platform": platform,
    }


async def _normalise_idea(
    idea: str,
    target_platform_hint: str,
    llm_model: str,
) -> Dict[str, Any]:
    """
    Call the LLM to turn the raw idea into a structured ProjectBrief dict.
    Retries up to 3 times on malformed JSON.
    """
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )
    user_prompt = f'Product idea: "{idea}"\nHint — target platform: {target_platform_hint}'

    for attempt in range(1, 4):
        try:
            response = await client.chat.completions.create(
                model=llm_model,
                messages=[
                    {"role": "system", "content": _NORMALISE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or "{}"
            brief_dict = json.loads(raw)
            required = {"title", "normalized_idea", "domain", "target_platform"}
            if not required.issubset(brief_dict.keys()):
                raise ValueError(f"Missing keys: {required - brief_dict.keys()}")
            return brief_dict
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "[orchestrator] Attempt %d: failed to parse brief JSON: %s", attempt, exc
            )
        except Exception as exc:
            logger.warning("[orchestrator] Attempt %d: LLM call failed: %s", attempt, str(exc)[:220])

        if attempt == 3:
            logger.error("[orchestrator] All attempts failed — using fallback brief")
            return _fallback_brief(idea, target_platform_hint)

    return _fallback_brief(idea, target_platform_hint)


async def _init_pipeline_run(run_id: str, state: PipelineState) -> None:
    """
    Write the initial pipeline_runs and global_state rows to PostgreSQL.
    Implementation is in core/database.py (Anshul's domain).
    """
    try:
        from app.core.database import create_pipeline_run  # type: ignore[import]

        await create_pipeline_run(
            run_id=run_id,
            idea=state["idea"],
            config=state["config"],
            user_id=state.get("user_id"),
        )
    except ImportError:
        logger.warning("[orchestrator] database.create_pipeline_run not available — skipping DB init")


async def _update_global_state(run_id: str, state: PipelineState) -> None:
    """Upsert the global_state JSON snapshot for fast dashboard reads."""
    try:
        from app.core.database import upsert_global_state  # type: ignore[import]

        await upsert_global_state(run_id=run_id, state=dict(state))
    except ImportError:
        logger.warning("[orchestrator] database.upsert_global_state not available — skipping")


# ── Public entry point ────────────────────────────────────────────────────────


async def run_orchestrator(
    run_id: str,
    idea: str,
    config: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> PipelineState:
    """
    Initialise a new pipeline run and return the populated PipelineState
    ready to be fed into the LangGraph graph.

    This is called by the FastAPI route handler (/api/v1/runs POST).

    Args:
        run_id:   UUID string for the pipeline run.
        idea:     Raw product idea from the user.
        config:   Optional pipeline configuration overrides.
        user_id:  Optional authenticated user UUID.

    Returns:
        PipelineState with run_state='RUNNING' and project_brief populated.
    """
    logger.info("[orchestrator] Initialising pipeline run_id=%s", run_id)

    # 1. Build initial state
    state = initial_state(run_id=run_id, idea=idea, config=config, user_id=user_id)

    # 2. Validate orchestrator input
    OrchestratorInput(
        run_id=UUID(run_id),
        idea=idea,
        config=state["config"],  # type: ignore[arg-type]
    )

    # 3. Persist pipeline_runs row
    await _init_pipeline_run(run_id, state)

    # 4. Emit PIPELINE_STARTED
    await publish_event(run_id, EventType.PIPELINE_STARTED, metadata={"idea": idea})
    await publish_log_line(run_id, "orchestrator", f"Pipeline started for idea: {idea[:80]}")

    # 5. Normalise idea → ProjectBrief via LLM
    llm_model = state["config"].get("llm_model", settings.OPENAI_MODEL)
    target_platform = state["config"].get("target_platform", settings.DEFAULT_TARGET_PLATFORM)

    await publish_log_line(run_id, "orchestrator", "Normalising product idea…")
    brief_dict = await _normalise_idea(idea, target_platform, llm_model)
    project_brief = ProjectBrief(**brief_dict)

    await publish_log_line(
        run_id, "orchestrator",
        f"Project brief created: '{project_brief.title}' ({project_brief.domain})"
    )

    # 6. Update state
    state = {
        **state,
        "project_brief": project_brief.model_dump(),
        "run_state": "RUNNING",
    }
    state["phases"]["research"]["status"] = "PENDING"

    # 7. Persist global_state snapshot
    await _update_global_state(run_id, state)

    # 8. Emit GLOBAL_STATE_UPDATED for dashboard
    await publish_event(
        run_id,
        EventType.GLOBAL_STATE_UPDATED,
        metadata={"state": {k: v for k, v in state.items() if k != "developer_output"}},
    )

    logger.info(
        "[orchestrator] State initialised: title='%s', domain='%s', platform='%s'",
        project_brief.title,
        project_brief.domain,
        project_brief.target_platform,
    )
    return state


# ── Agent-callable wrapper (for executor.py integration) ─────────────────────


async def run_orchestrator_agent(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Thin wrapper that makes the orchestrator callable from agent_executor().
    Accepts the OrchestratorInput dict and returns OrchestratorOutput dict.
    """
    inp = OrchestratorInput.model_validate(input_dict)

    # Kick off full init (returns PipelineState, but we return OrchestratorOutput)
    state = await run_orchestrator(
        run_id=str(inp.run_id),
        idea=inp.idea,
        config=inp.config.model_dump(),
    )

    output = OrchestratorOutput(
        run_id=inp.run_id,
        run_state=RunState(state["run_state"]),
        project_brief=ProjectBrief(**state["project_brief"]),
        phases={
            k: v for k, v in state["phases"].items()
        },
        artifact_urls=state.get("artifact_urls") or {},
    )
    return output.model_dump(mode="json")
