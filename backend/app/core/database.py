"""
Database layer — PostgreSQL via SQLAlchemy async.

Implements all 6 functions called by the workflow engine:
  - create_pipeline_run
  - save_agent_run
  - save_artifact
  - upsert_global_state
  - get_pipeline_run
  - check_db_health

Owned by: Anshul
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    select,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import JSONB

from .config import settings

logger = logging.getLogger(__name__)

# ── SQLAlchemy engine & session ───────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # reconnect on dropped connections
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ── ORM Models ────────────────────────────────────────────────────────────────


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    idea = Column(Text, nullable=False)
    config = Column(JSONB, nullable=True)
    user_id = Column(String, nullable=True)
    run_state = Column(String, default="INITIALIZING")
    project_brief = Column(JSONB, nullable=True)
    phases = Column(JSONB, nullable=True)
    full_state = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, nullable=False, index=True)
    agent_name = Column(String, nullable=False)
    iteration = Column(Integer, default=1)
    input_payload = Column(JSONB, nullable=True)
    output_payload = Column(JSONB, nullable=True)
    status = Column(String, default="RUNNING")
    duration_ms = Column(Integer, nullable=True)
    error_details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, nullable=False, index=True)
    artifact_type = Column(String, nullable=False)
    content = Column(JSONB, nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class GlobalState(Base):
    __tablename__ = "global_state"

    run_id = Column(String, primary_key=True)
    state = Column(JSONB, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Table creation helper ─────────────────────────────────────────────────────


async def create_tables() -> None:
    """Create all tables if they don't exist (idempotent)."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created.")
    except Exception as exc:
        logger.error("Failed to create tables: %s", exc)
        raise


# ── Required functions (called by workflow engine) ────────────────────────────


async def create_pipeline_run(
    run_id: str,
    idea: str,
    config: dict,
    user_id: Optional[str] = None,
) -> None:
    """Insert the initial pipeline_runs row. Called by Orchestrator."""
    try:
        async with AsyncSessionLocal() as session:
            run = PipelineRun(
                id=run_id,
                idea=idea,
                config=config,
                user_id=user_id,
                run_state="INITIALIZING",
            )
            session.add(run)
            await session.commit()
            logger.debug("Created pipeline_run row for run_id=%s", run_id)
    except Exception as exc:
        logger.error("create_pipeline_run failed for run_id=%s: %s", run_id, exc)
        # Do NOT re-raise — pipeline execution must not be blocked by DB issues


async def save_agent_run(
    run_id: str,
    agent_name: str,
    iteration: int,
    input_payload: Dict[str, Any],
    output_payload: Optional[Dict[str, Any]],
    status: str,
    duration_ms: int,
    error_details: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert/update an agent_runs row. Called by executor after each agent."""
    try:
        async with AsyncSessionLocal() as session:
            agent_run = AgentRun(
                id=str(uuid.uuid4()),
                run_id=run_id,
                agent_name=agent_name,
                iteration=iteration,
                input_payload=input_payload,
                output_payload=output_payload,
                status=status,
                duration_ms=duration_ms,
                error_details=error_details,
            )
            session.add(agent_run)
            await session.commit()
            logger.debug("Saved agent_run %s/%s status=%s", run_id, agent_name, status)
    except Exception as exc:
        logger.error("save_agent_run failed for %s/%s: %s", run_id, agent_name, exc)


async def save_artifact(
    run_id: str,
    artifact_type: str,
    content: Dict[str, Any],
    version: int = 1,
) -> None:
    """Insert an artifact row. Called by executor after each agent completes."""
    try:
        async with AsyncSessionLocal() as session:
            artifact = Artifact(
                id=str(uuid.uuid4()),
                run_id=run_id,
                artifact_type=artifact_type,
                content=content,
                version=version,
            )
            session.add(artifact)
            await session.commit()
            logger.debug("Saved artifact %s v%s for run_id=%s", artifact_type, version, run_id)
    except Exception as exc:
        logger.error("save_artifact failed for run_id=%s: %s", run_id, exc)


async def upsert_global_state(run_id: str, state: Dict[str, Any]) -> None:
    """
    Upsert the full PipelineState JSON snapshot for fast dashboard reads.
    Called by orchestrator and worker after the pipeline completes.
    """
    try:
        async with AsyncSessionLocal() as session:
            existing = await session.get(GlobalState, run_id)
            if existing:
                existing.state = state
                existing.updated_at = datetime.now(timezone.utc)
            else:
                session.add(GlobalState(run_id=run_id, state=state))

            # Also update pipeline_runs summary columns
            pipeline_run = await session.get(PipelineRun, run_id)
            if pipeline_run:
                pipeline_run.run_state = state.get("run_state", "RUNNING")
                pipeline_run.project_brief = state.get("project_brief")
                pipeline_run.phases = state.get("phases")
                pipeline_run.full_state = state
                pipeline_run.updated_at = datetime.now(timezone.utc)

            await session.commit()
            logger.debug("Upserted global_state for run_id=%s", run_id)
    except Exception as exc:
        logger.error("upsert_global_state failed for run_id=%s: %s", run_id, exc)


async def get_pipeline_run(run_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch pipeline run summary. Called by GET /api/v1/runs/{run_id}.
    Returns None if not found.
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.get(PipelineRun, run_id)
            if not result:
                return None
            return {
                "run_id": result.id,
                "run_state": result.run_state,
                "phases": result.phases or {},
                "project_brief": result.project_brief,
                "idea": result.idea,
                "created_at": result.created_at.isoformat() if result.created_at else None,
            }
    except Exception as exc:
        logger.error("get_pipeline_run failed for run_id=%s: %s", run_id, exc)
        return None


async def check_db_health() -> None:
    """
    Ping the database. Raises if unreachable.
    Called by GET /ready health check.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
