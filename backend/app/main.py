"""
FastAPI application entry point.

Owned by: Nisarg — app bootstrap, lifespan, and /api/v1/runs endpoints
that kick off pipeline runs and return run_id for WebSocket tracking.
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
from app.core.redis import get_redis, close_redis, submit_human_approval

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ADWF backend starting up…")

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