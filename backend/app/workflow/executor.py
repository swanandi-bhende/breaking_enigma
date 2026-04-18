"""
Agent Execution Wrapper — the standard shell every agent runs inside.

Responsibilities:
  1. Acquire Redis lock (prevent concurrent runs of same agent)
  2. Validate input against Pydantic schema
  3. Update agent status → RUNNING + publish event
  4. Call the actual agent function
  5. Validate output against Pydantic schema
  6. Persist to PostgreSQL (agent_runs + artifacts tables)
  7. Emit Qdrant embeddings (delegated to agent-specific hook)
  8. Update status → COMPLETE + publish event
  9. Release lock (always, in finally)
  10. On exception: update status → FAILED + publish event

Owned by: Nisarg (Workflow Engine & Agent Orchestration)
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.core.events import AgentStatus, EventType, LogLevel
from app.core.redis import (
    acquire_agent_lock,
    publish_event,
    publish_log_line,
    release_agent_lock,
    set_agent_status_cache,
)
from app.schemas.agents import AGENT_SCHEMAS
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)


# ── Custom Exceptions ────────────────────────────────────────────────────────


class AgentLockError(RuntimeError):
    """Raised when the agent lock cannot be acquired (concurrent run detected)."""


class AgentInputValidationError(ValueError):
    """Raised when the input payload fails Pydantic schema validation."""


class AgentOutputValidationError(ValueError):
    """Raised when the agent's output payload fails Pydantic schema validation."""


class AgentMaxRetriesError(RuntimeError):
    """Raised when an agent fails and has reached the configured retry limit."""


# ── Persistence stubs (implemented by Anshul in core/database.py) ────────────


async def _persist_agent_run(
    run_id: str,
    agent_name: str,
    iteration: int,
    input_payload: Dict[str, Any],
    output_payload: Optional[Dict[str, Any]],
    status: str,
    duration_ms: int,
    error_details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write an agent_runs row to PostgreSQL.
    Implementation lives in backend/app/core/database.py (Anshul's domain).
    This wrapper calls it via a late import to avoid circular dependencies.
    """
    try:
        from app.core.database import save_agent_run  # type: ignore[import]

        await save_agent_run(
            run_id=run_id,
            agent_name=agent_name,
            iteration=iteration,
            input_payload=input_payload,
            output_payload=output_payload,
            status=status,
            duration_ms=duration_ms,
            error_details=error_details,
        )
    except ImportError:
        # Database module not yet available (unit tests / early development)
        logger.warning("database.save_agent_run not available — skipping persistence")


async def _persist_artifact(
    run_id: str,
    agent_name: str,
    artifact_type: str,
    content: Dict[str, Any],
    version: int = 1,
) -> None:
    """
    Write an artifacts row to PostgreSQL.
    Implementation lives in backend/app/core/database.py.
    """
    try:
        from app.core.database import save_artifact  # type: ignore[import]

        await save_artifact(
            run_id=run_id,
            artifact_type=artifact_type,
            content=content,
            version=version,
        )
    except ImportError:
        logger.warning("database.save_artifact not available — skipping artifact persistence")


# ── Input / Output Validation ────────────────────────────────────────────────


def validate_agent_input(agent_name: str, raw_input: Dict[str, Any]) -> BaseModel:
    """
    Validate `raw_input` against the registered Pydantic input schema
    for `agent_name`. Raises AgentInputValidationError on failure.
    """
    schemas = AGENT_SCHEMAS.get(agent_name)
    if not schemas:
        raise ValueError(f"Unknown agent: '{agent_name}'. Check AGENT_SCHEMAS registry.")

    InputSchema = schemas["input"]
    try:
        return InputSchema.model_validate(raw_input)
    except ValidationError as exc:
        raise AgentInputValidationError(
            f"[{agent_name}] Input validation failed:\n{exc}"
        ) from exc


def validate_agent_output(agent_name: str, raw_output: Dict[str, Any]) -> BaseModel:
    """
    Validate `raw_output` against the registered Pydantic output schema.
    Raises AgentOutputValidationError on failure.
    """
    schemas = AGENT_SCHEMAS.get(agent_name)
    if not schemas:
        raise ValueError(f"Unknown agent: '{agent_name}'. Check AGENT_SCHEMAS registry.")

    OutputSchema = schemas["output"]
    try:
        return OutputSchema.model_validate(raw_output)
    except ValidationError as exc:
        raise AgentOutputValidationError(
            f"[{agent_name}] Output validation failed:\n{exc}"
        ) from exc


# ── Core Executor ────────────────────────────────────────────────────────────


async def agent_executor(
    agent_name: str,
    agent_fn: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    state: PipelineState,
    iteration: int = 1,
    max_retries: int = 2,
    retry_delay_seconds: float = 3.0,
) -> Dict[str, Any]:
    """
    Run an agent function inside the standard execution shell.

    Args:
        agent_name:    Name key matching AGENT_SCHEMAS (e.g. 'research').
        agent_fn:      Async function that accepts a validated dict and returns
                       a dict matching the agent's output schema.
        state:         Current PipelineState (read-only inside this function).
        iteration:     QA loop iteration number (1-based).
        max_retries:   How many times to retry on AgentOutputValidationError
                       or transient errors before raising.
        retry_delay_seconds: Back-off between retries.

    Returns:
        Validated output dict (model.model_dump()).

    Raises:
        AgentLockError              — another run of this agent is active.
        AgentInputValidationError   — state doesn't satisfy input schema.
        AgentMaxRetriesError        — exhausted retries without success.
    """
    run_id = state["run_id"]
    start_ts = time.monotonic()

    # ── 1. Acquire lock ──────────────────────────────────────────────────────
    acquired = await acquire_agent_lock(run_id, agent_name)
    if not acquired:
        raise AgentLockError(
            f"Agent '{agent_name}' is already running for run_id={run_id}. "
            "Concurrent execution is not allowed."
        )

    try:
        # ── 2. Build input payload from state ────────────────────────────────
        raw_input = _extract_input(agent_name, state)

        # ── 3. Validate input ────────────────────────────────────────────────
        validated_input = validate_agent_input(agent_name, raw_input)
        input_dict = validated_input.model_dump(mode="json")

        # ── 4. Update status → RUNNING ───────────────────────────────────────
        now_iso = datetime.now(timezone.utc).isoformat()
        await set_agent_status_cache(run_id, agent_name, AgentStatus.RUNNING, {"started_at": now_iso})
        await publish_event(
            run_id,
            EventType.AGENT_STATUS_CHANGED,
            metadata={"previous_status": "PENDING", "new_status": "RUNNING", "iteration": iteration},
            agent_name=agent_name,
        )
        await publish_log_line(run_id, agent_name, f"[{agent_name}] Starting (iteration {iteration})…")

        # ── 5. Run agent with retry loop ─────────────────────────────────────
        output_dict: Dict[str, Any] = {}
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_retries + 2):  # +2: first attempt + max_retries retries
            try:
                raw_output = await agent_fn(input_dict)
                validated_output = validate_agent_output(agent_name, raw_output)
                output_dict = validated_output.model_dump(mode="json")
                break  # success — exit retry loop

            except AgentOutputValidationError as exc:
                last_exc = exc
                logger.warning(
                    "[%s] Output validation failed (attempt %d/%d): %s",
                    agent_name, attempt, max_retries + 1, exc,
                )
                await publish_log_line(
                    run_id, agent_name,
                    f"Output validation failed (attempt {attempt}): {exc}",
                    level=LogLevel.WARNING,
                )
                if attempt <= max_retries:
                    await asyncio.sleep(retry_delay_seconds * attempt)
                else:
                    raise AgentMaxRetriesError(
                        f"[{agent_name}] Failed after {max_retries + 1} attempts. Last error: {last_exc}"
                    ) from last_exc

            except Exception as exc:
                last_exc = exc
                logger.exception("[%s] Unexpected error (attempt %d): %s", agent_name, attempt, exc)
                await publish_log_line(
                    run_id, agent_name,
                    f"Unexpected error (attempt {attempt}): {exc}",
                    level=LogLevel.ERROR,
                )
                if attempt <= max_retries:
                    await asyncio.sleep(retry_delay_seconds * attempt)
                else:
                    raise AgentMaxRetriesError(
                        f"[{agent_name}] Failed after {max_retries + 1} attempts. Last error: {last_exc}"
                    ) from last_exc

        # ── 6. Persist to PostgreSQL ─────────────────────────────────────────
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await _persist_agent_run(
            run_id=run_id,
            agent_name=agent_name,
            iteration=iteration,
            input_payload=input_dict,
            output_payload=output_dict,
            status="COMPLETE",
            duration_ms=duration_ms,
        )
        await _persist_artifact(
            run_id=run_id,
            agent_name=agent_name,
            artifact_type=f"{agent_name}_output",
            content=output_dict,
            version=iteration,
        )

        # ── 7. Update status → COMPLETE ──────────────────────────────────────
        completed_iso = datetime.now(timezone.utc).isoformat()
        await set_agent_status_cache(
            run_id, agent_name, AgentStatus.COMPLETE,
            {"completed_at": completed_iso, "duration_ms": duration_ms},
        )
        await publish_event(
            run_id,
            EventType.AGENT_STATUS_CHANGED,
            metadata={"previous_status": "RUNNING", "new_status": "COMPLETE", "duration_ms": duration_ms},
            agent_name=agent_name,
        )
        await publish_event(
            run_id,
            EventType.ARTIFACT_READY,
            metadata={"artifact_type": f"{agent_name}_output", "version": iteration},
            agent_name=agent_name,
        )
        await publish_log_line(
            run_id, agent_name,
            f"[{agent_name}] Completed in {duration_ms}ms ✓",
        )

        logger.info("[%s] run_id=%s completed in %dms", agent_name, run_id, duration_ms)
        return output_dict

    except Exception as exc:
        # ── Failure path ─────────────────────────────────────────────────────
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        error_msg = str(exc)

        await set_agent_status_cache(run_id, agent_name, AgentStatus.FAILED, {"error": error_msg})
        await publish_event(
            run_id,
            EventType.AGENT_STATUS_CHANGED,
            metadata={"previous_status": "RUNNING", "new_status": "FAILED", "error": error_msg},
            agent_name=agent_name,
        )
        await publish_log_line(run_id, agent_name, f"[{agent_name}] FAILED: {error_msg}", level=LogLevel.ERROR)

        await _persist_agent_run(
            run_id=run_id,
            agent_name=agent_name,
            iteration=iteration,
            input_payload={},
            output_payload=None,
            status="FAILED",
            duration_ms=duration_ms,
            error_details={"message": error_msg, "type": type(exc).__name__},
        )

        raise

    finally:
        # ── Always release lock ───────────────────────────────────────────────
        await release_agent_lock(run_id, agent_name)


# ── Input extraction helper ───────────────────────────────────────────────────
# Maps each agent name to the slice of PipelineState it needs as input.
# This keeps the graph nodes thin — they just call agent_executor().


def _extract_input(agent_name: str, state: PipelineState) -> Dict[str, Any]:
    """
    Derive the raw input dict for `agent_name` from the current PipelineState.
    This centralises the state→input mapping so graph nodes stay minimal.
    """
    run_id = state["run_id"]

    if agent_name == "orchestrator":
        return {
            "run_id": run_id,
            "idea": state["idea"],
            "config": state["config"],
        }

    if agent_name == "research":
        return {
            "run_id": run_id,
            "project_brief": state["project_brief"],
            "tools_available": ["web_search", "serp_api", "crunchbase_lookup"],
        }

    if agent_name == "product_manager":
        return {
            "run_id": run_id,
            "research_report": state["research_report"],
        }

    if agent_name == "designer":
        return {
            "run_id": run_id,
            "prd": state["prd"],
            "research_context_embedding_ids": state.get("research_embedding_ids") or [],
        }

    if agent_name == "developer":
        return {
            "run_id": run_id,
            "design_spec": state["design_spec"],
            "prd": state["prd"],
            "qa_feedback": state.get("qa_output"),  # None on first run
        }

    if agent_name == "qa":
        return {
            "run_id": run_id,
            "developer_output": state["developer_output"],
            "design_spec": state["design_spec"],
            "prd": state["prd"],
            "iteration": state.get("qa_iteration", 1),
        }

    if agent_name == "devops":
        return {
            "run_id": run_id,
            "developer_output": state["developer_output"],
            "qa_output": state["qa_output"],
            "deployment_target": state["config"].get("deployment_target", "docker-local"),
        }

    if agent_name == "documentation":
        return {
            "run_id": run_id,
            "research_report": state["research_report"],
            "prd": state["prd"],
            "design_spec": state["design_spec"],
            "developer_output": state["developer_output"],
            "qa_output": state["qa_output"],
            "devops_output": None,
        }

    raise ValueError(f"No input extractor defined for agent '{agent_name}'.")
