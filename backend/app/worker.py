"""
Celery application — background task queue for long-running pipeline runs.

Pipelines can take 10-30 minutes.  Running them inside a FastAPI request
would block the server and risk timeout.  Instead, the API route enqueues
a Celery task and returns the run_id immediately; the client polls status
via WebSocket.

Owned by: Nisarg (Workflow Engine & Agent Orchestration)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from celery import Celery
from celery.utils.log import get_task_logger

from app.core.config import settings
from app.workflow.run_store import clear_run_store, get_run_store

logger = get_task_logger(__name__)

# Reuse one asyncio event loop per Celery worker process.
# Creating a new loop for every task can invalidate pooled async DB connections
# and trigger asyncpg "another operation is in progress" errors.
_WORKER_EVENT_LOOP: asyncio.AbstractEventLoop | None = None

# ── Celery app instance ───────────────────────────────────────────────────────

celery_app = Celery(
    "adwf",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,          # Ack only after task completes (safer)
    worker_prefetch_multiplier=1, # One task at a time per worker process
    task_soft_time_limit=3600,    # 60-minute soft limit
    task_time_limit=3900,         # 65-minute hard kill
    task_routes={
        "app.worker.run_pipeline_task": {"queue": "pipeline"},
    },
)


# ── Pipeline task ─────────────────────────────────────────────────────────────


@celery_app.task(
    bind=True,
    name="app.worker.run_pipeline_task",
    max_retries=0,  # No automatic Celery retry — graph handles its own retries
    acks_late=True,
)
def run_pipeline_task(
    self,
    run_id: str,
    idea: str,
    config: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Celery task that runs the full ADWF multi-agent pipeline.

    Steps:
    1. Initialise pipeline via the Orchestrator
    2. Feed the initial state into the LangGraph pipeline_graph
    3. Stream state updates via Redis pub/sub (handled inside graph nodes)
    4. Return the final PipelineState as the Celery result

    Args:
        run_id:   UUID string for this pipeline run.
        idea:     Raw product idea text.
        config:   Optional pipeline config overrides.
        user_id:  Optional authenticated user UUID.

    Returns:
        Final PipelineState dict (stored in Celery result backend).
    """
    logger.info("Starting pipeline task run_id=%s", run_id)

    # Celery workers are sync; run async pipeline on a persistent per-process loop.
    global _WORKER_EVENT_LOOP
    if _WORKER_EVENT_LOOP is None or _WORKER_EVENT_LOOP.is_closed():
        _WORKER_EVENT_LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_WORKER_EVENT_LOOP)

    return _WORKER_EVENT_LOOP.run_until_complete(
        _execute_pipeline(run_id, idea, config, user_id)
    )


async def _execute_pipeline(
    run_id: str,
    idea: str,
    config: Optional[Dict[str, Any]],
    user_id: Optional[str],
) -> Dict[str, Any]:
    """
    Async implementation of the pipeline execution.
    1. Call orchestrator to get initial PipelineState.
    2. Invoke the LangGraph compiled graph.
    3. Persist final state to PostgreSQL global_state.
    4. Return final state dict.
    """
    from app.agents.orchestrator import run_orchestrator
    from app.core.redis import publish_event
    from app.core.events import EventType
    from app.workflow.graph import pipeline_graph

    try:
        run_store = get_run_store(run_id=run_id, config=config)

        # Step 1 — Orchestrator initialises the state
        initial = await run_orchestrator(
            run_id=run_id,
            idea=idea,
            config=config,
            user_id=user_id,
        )

        # Step 2 — Run the LangGraph pipeline
        logger.info("Invoking LangGraph pipeline for run_id=%s", run_id)
        final_state = await pipeline_graph.ainvoke(initial)

        # Step 3 — Finalize and flush state persistence for this run
        await run_store.finalize_run(run_id=run_id, final_state=dict(final_state))
        clear_run_store(run_id)

        logger.info(
            "Pipeline complete for run_id=%s, run_state=%s",
            run_id,
            final_state.get("run_state"),
        )
        return dict(final_state)

    except Exception as exc:
        logger.exception("Pipeline task FAILED for run_id=%s: %s", run_id, exc)

        try:
            run_store = get_run_store(run_id=run_id, config=config)
            await run_store.finalize_run(
                run_id=run_id,
                final_state={
                    "run_id": run_id,
                    "idea": idea,
                    "config": config or {},
                    "run_state": "FAILED",
                    "error": str(exc),
                },
            )
            clear_run_store(run_id)
        except Exception:
            logger.exception("Failed to finalize run_store for failed run_id=%s", run_id)

        # Emit failure event so the dashboard knows
        try:
            await publish_event(
                run_id,
                EventType.PIPELINE_FAILED,
                metadata={"error": str(exc)},
            )
        except Exception:
            pass

        # Re-raise so Celery marks this task as FAILURE
        raise


# ── Convenience enqueue helper ────────────────────────────────────────────────


def enqueue_pipeline(
    run_id: str,
    idea: str,
    config: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> str:
    """
    Enqueue a pipeline run task and return the Celery task ID.
    Called from the FastAPI route handler after creating the DB record.

    Returns:
        Celery task ID (different from run_id; useful for task status polling).
    """
    result = run_pipeline_task.apply_async(
        kwargs={
            "run_id": run_id,
            "idea": idea,
            "config": config,
            "user_id": user_id,
        },
        task_id=f"pipeline-{run_id}",  # deterministic task ID
        queue="pipeline",
    )
    logger.info("Enqueued pipeline task_id=%s for run_id=%s", result.id, run_id)
    return result.id
