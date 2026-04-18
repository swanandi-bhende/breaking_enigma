"""
FastAPI application entry point.

Owned by: Nisarg — app bootstrap, lifespan, and /api/v1/runs endpoints
that kick off pipeline runs and return run_id for WebSocket tracking.

Note: WebSocket server, other API routes (agents, artifacts) are Anshul's domain.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.events import EventType
from app.core.redis import close_redis, get_redis, publish_event, submit_human_approval

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before yielding, then shutdown tasks after."""
    logger.info("ADWF backend starting up…")

    # Verify Redis is reachable
    redis = await get_redis()
    await redis.ping()
    logger.info("Redis connection OK")

    # Create DB tables (idempotent)
    try:
        from app.core.database import create_tables
        await create_tables()
        logger.info("Database tables ready")
    except Exception as exc:
        logger.warning("DB table creation skipped: %s", exc)

    yield  # <— application runs here

    # Shutdown
    logger.info("ADWF backend shutting down…")
    await close_redis()


# ── App factory ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Digital Workforce API",
    version="1.0.0",
    description=(
        "Autonomous multi-agent product lifecycle system. "
        "Submit a product idea, watch agents build it live."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════════════════════════════════════════
# Health & readiness
# ════════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["Infrastructure"])
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["Infrastructure"])
async def ready() -> Dict[str, Any]:
    """Check all critical dependencies are reachable."""
    checks: Dict[str, str] = {}

    # Redis
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    # Database (Anshul's module — optional at this stage)
    try:
        from app.core.database import check_db_health  # type: ignore[import]
        await check_db_health()
        checks["database"] = "ok"
    except ImportError:
        checks["database"] = "not_yet_implemented"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    all_ok = all(v in ("ok", "not_yet_implemented") for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}


# ════════════════════════════════════════════════════════════════════════════
# Pipeline Run endpoints (Nisarg's domain)
# ════════════════════════════════════════════════════════════════════════════


class CreateRunRequest(BaseModel):
    idea: str = Field(..., min_length=10, max_length=1000, description="Raw product idea")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Pipeline config overrides")
    user_id: Optional[str] = Field(default=None, description="Authenticated user UUID")


class CreateRunResponse(BaseModel):
    run_id: str
    task_id: str
    message: str


@app.post(
    "/api/v1/runs",
    response_model=CreateRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Pipeline"],
)
async def create_run(
    body: CreateRunRequest,
    background_tasks: BackgroundTasks,
) -> CreateRunResponse:
    """
    Submit a product idea to start a new pipeline run.

    Returns immediately with a `run_id` — the client connects to the
    WebSocket using this ID to receive live updates.
    """
    run_id = str(uuid.uuid4())
    logger.info("Creating pipeline run run_id=%s idea='%s'", run_id, body.idea[:60])

    # Enqueue via Celery (preferred) or fall back to FastAPI BackgroundTasks
    try:
        from app.worker import enqueue_pipeline  # type: ignore[import]
        task_id = enqueue_pipeline(
            run_id=run_id,
            idea=body.idea,
            config=body.config,
            user_id=body.user_id,
        )
    except ImportError:
        # Celery not configured — run in a background task (dev mode)
        logger.warning("Celery not available — using BackgroundTasks (dev mode)")
        from app.worker import _execute_pipeline  # type: ignore[import]
        background_tasks.add_task(
            _execute_pipeline,
            run_id=run_id,
            idea=body.idea,
            config=body.config,
            user_id=body.user_id,
        )
        task_id = f"bg-{run_id}"

    return CreateRunResponse(
        run_id=run_id,
        task_id=task_id,
        message="Pipeline run started. Connect to WebSocket for live updates.",
    )


class GetRunResponse(BaseModel):
    run_id: str
    run_state: Optional[str] = None
    phases: Optional[Dict[str, Any]] = None
    project_brief: Optional[Dict[str, Any]] = None


@app.get("/api/v1/runs/{run_id}", response_model=GetRunResponse, tags=["Pipeline"])
async def get_run(run_id: str) -> GetRunResponse:
    """Get the current state of a pipeline run."""
    try:
        from app.core.database import get_pipeline_run  # type: ignore[import]
        run = await get_pipeline_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return GetRunResponse(**run)
    except ImportError:
        # DB not yet implemented — return minimal response
        return GetRunResponse(run_id=run_id, run_state="UNKNOWN")


# ── Human checkpoint approval ─────────────────────────────────────────────────


class ApproveRunRequest(BaseModel):
    approved: bool
    feedback: Optional[str] = None


@app.post("/api/v1/runs/{run_id}/approve", tags=["Pipeline"])
async def approve_run(run_id: str, body: ApproveRunRequest) -> Dict[str, str]:
    """
    Approve or reject a pipeline that is paused at a human checkpoint.
    The paused graph node polls Redis until this endpoint is called.
    """
    await submit_human_approval(
        run_id=run_id,
        approved=body.approved,
        feedback=body.feedback,
    )
    action = "approved" if body.approved else "rejected"
    return {"status": "ok", "message": f"Pipeline {action}"}


# ── Include additional route modules (Anshul's domain) ────────────────────────
# These are imported conditionally so the app boots even without them.

try:
    from app.api.routes import agents as agents_router  # type: ignore[import]
    app.include_router(agents_router.router, prefix="/api/v1", tags=["Agents"])
except ImportError:
    logger.debug("agents router not yet implemented")

try:
    from app.api.routes import artifacts as artifacts_router  # type: ignore[import]
    app.include_router(artifacts_router.router, prefix="/api/v1", tags=["Artifacts"])
except ImportError:
    logger.debug("artifacts router not yet implemented")

try:
    from app.api.websocket import socket_app, router as ws_router  # type: ignore[import]
    app.include_router(ws_router, tags=["WebSocket"])
    # Mount Socket.IO ASGI app — handles /socket.io/* paths
    app.mount("/socket.io", socket_app)
    logger.info("Socket.IO server mounted at /socket.io")
except ImportError as e:
    logger.warning("websocket handler not yet available: %s", e)
except Exception as e:
    logger.error("Failed to mount Socket.IO: %s", e)
