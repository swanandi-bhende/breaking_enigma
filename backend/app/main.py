"""
FastAPI application entry point.

Owned by: Nisarg — app bootstrap, lifespan, and /api/v1/runs endpoints
that kick off pipeline runs and return run_id for WebSocket tracking.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.redis import (
    close_redis,
    get_redis,
    get_run_status_cache,
    set_run_status_cache,
    submit_human_approval,
)
from app.core.database import init_database, get_pipeline_run

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ADWF backend starting up…")

    try:
        await init_database()
        logger.info("Database tables ready")
    except Exception as exc:
        logger.warning("Database init skipped: %s", exc)

    redis = await get_redis()
    await redis.ping()
    logger.info("Redis connection OK")

    yield

    logger.info("ADWF backend shutting down…")
    await close_redis()


# ── App ─────────────────────────────────────────────

app = FastAPI(
    title="AI Digital Workforce API",
    version="1.0.0",
    lifespan=lifespan,
)

# ✅ FIXED CORS (critical)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ─────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/health")
async def api_health():
    return {"status": "ok"}


# ── Pipeline Run Models ─────────────────────────────

class CreateRunRequest(BaseModel):
    idea: str = Field(..., min_length=10)
    config: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None


class CreateRunResponse(BaseModel):
    run_id: str
    task_id: str
    message: str


# ── Pipeline Endpoint ─────────────────────────────

@app.post("/api/v1/runs", response_model=CreateRunResponse, status_code=202)
async def create_run(body: CreateRunRequest, background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())
    logger.info("Creating run %s", run_id)

    # Seed live run status so read-path polling works before worker flushes to DB.
    await set_run_status_cache(
        run_id,
        {
            "run_id": run_id,
            "user_id": body.user_id,
            "idea": body.idea,
            "config": body.config or {},
            "run_state": "INITIALIZING",
            "error": None,
            "project_brief": None,
            "phases": None,
            "artifacts": {},
            "agent_runs": [],
        },
        event_sequence=0,
    )

    try:
        from app.worker import enqueue_pipeline
        task_id = enqueue_pipeline(
            run_id=run_id,
            idea=body.idea,
            config=body.config,
            user_id=body.user_id,
        )
    except ImportError:
        from app.worker import _execute_pipeline
        background_tasks.add_task(
            _execute_pipeline,
            run_id,
            body.idea,
            body.config,
            body.user_id,
        )
        task_id = f"bg-{run_id}"

    return CreateRunResponse(
        run_id=run_id,
        task_id=task_id,
        message="Pipeline started"
    )


@app.get("/api/v1/runs/{run_id}")
async def get_run(run_id: str):
    live_run = await get_run_status_cache(run_id)
    persisted_run = await get_pipeline_run(run_id)

    if live_run is None and persisted_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    response = dict(persisted_run or {})

    if live_run is not None:
        response.update(live_run)
        if persisted_run is not None:
            # Keep DB canonical timestamps/metadata while exposing real-time state fields.
            response["created_at"] = persisted_run.get("created_at")
            response["completed_at"] = persisted_run.get("completed_at")
            response["agent_runs"] = persisted_run.get("agent_runs", [])

    response["persistence_lag_ms"] = _compute_persistence_lag_ms(live_run, persisted_run)
    return response


def _parse_iso_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _compute_persistence_lag_ms(
    live_run: Optional[Dict[str, Any]],
    persisted_run: Optional[Dict[str, Any]],
) -> Optional[int]:
    if live_run is None:
        return 0 if persisted_run is not None else None

    live_ts = _parse_iso_timestamp(live_run.get("live_updated_at") or live_run.get("updated_at"))
    if live_ts is None:
        return None

    if persisted_run is None:
        return None

    persisted_ts = (
        _parse_iso_timestamp(persisted_run.get("updated_at"))
        or _parse_iso_timestamp(persisted_run.get("completed_at"))
        or _parse_iso_timestamp(persisted_run.get("created_at"))
    )
    if persisted_ts is None:
        return None

    delta_ms = int((live_ts - persisted_ts).total_seconds() * 1000)
    return max(0, delta_ms)


# ── Human approval ─────────────────────────────

class ApproveRunRequest(BaseModel):
    approved: bool
    feedback: Optional[str] = None


@app.post("/api/v1/runs/{run_id}/approve")
async def approve_run(run_id: str, body: ApproveRunRequest):
    await submit_human_approval(run_id, body.approved, body.feedback)
    return {"status": "ok"}


# ── WebSocket Router (IMPORTANT) ─────────────────────────────

try:
    from app.api.websocket import router as websocket_router
    app.include_router(websocket_router)
    logger.info("WebSocket router loaded")
except Exception as e:
    logger.warning("WebSocket router NOT loaded: %s", e)