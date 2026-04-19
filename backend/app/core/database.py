from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from .config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False
)

Base = declarative_base()

_tables_initialized = False


async def init_database() -> None:
    """Create DB tables if they do not exist."""
    global _tables_initialized
    if _tables_initialized:
        return

    # Import models lazily so metadata is fully registered before create_all.
    from app.models import base as _models_base  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _tables_initialized = True

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def create_pipeline_run(
    run_id: str,
    idea: str,
    config: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> None:
    await init_database()
    from app.models.base import GlobalState, PipelineRun

    async with AsyncSessionLocal() as session:
        run = await session.get(PipelineRun, run_id)
        if run is None:
            run = PipelineRun(
                id=run_id,
                user_id=user_id,
                idea=idea,
                config=config or {},
                run_state="INITIALIZING",
            )
            session.add(run)
        else:
            run.user_id = user_id
            run.idea = idea
            run.config = config or {}
            run.run_state = "INITIALIZING"
            run.error = None
            run.completed_at = None

        gs = await session.get(GlobalState, run_id)
        if gs is None:
            gs = GlobalState(
                id=run_id,
                run_state="INITIALIZING",
                phases={},
                artifacts={},
            )
            session.add(gs)

        await session.commit()


async def upsert_global_state(run_id: str, state: Dict[str, Any]) -> None:
    await init_database()
    from app.models.base import GlobalState, PipelineRun

    run_state = str(state.get("run_state", "RUNNING"))

    async with AsyncSessionLocal() as session:
        gs = await session.get(GlobalState, run_id)
        if gs is None:
            gs = GlobalState(id=run_id)
            session.add(gs)

        gs.run_state = run_state
        gs.project_brief = state.get("project_brief")
        gs.phases = state.get("phases")
        # Keep artifact_urls under the existing artifacts column for compatibility.
        gs.artifacts = state.get("artifact_urls") or gs.artifacts or {}

        run = await session.get(PipelineRun, run_id)
        if run is None:
            run = PipelineRun(
                id=run_id,
                user_id=state.get("user_id"),
                idea=state.get("idea", ""),
                config=state.get("config") or {},
                run_state=run_state,
            )
            session.add(run)
        else:
            run.run_state = run_state
            run.error = state.get("error")

        if run_state in {"COMPLETE", "FAILED"} and run is not None and run.completed_at is None:
            run.completed_at = datetime.now(timezone.utc)

        await session.commit()


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
    await init_database()
    from app.models.base import AgentRun

    async with AsyncSessionLocal() as session:
        session.add(
            AgentRun(
                id=str(uuid4()),
                global_state_id=run_id,
                agent_name=agent_name,
                iteration=iteration,
                status=status,
                output={
                    "input": input_payload,
                    "output": output_payload,
                    "duration_ms": duration_ms,
                    "error_details": error_details,
                },
                error=(error_details or {}).get("message") if error_details else None,
            )
        )
        await session.commit()


async def save_artifact(
    run_id: str,
    artifact_type: str,
    content: Dict[str, Any],
    version: int = 1,
) -> None:
    await init_database()
    from app.models.base import GlobalState

    async with AsyncSessionLocal() as session:
        gs = await session.get(GlobalState, run_id)
        if gs is None:
            gs = GlobalState(id=run_id, run_state="RUNNING", phases={}, artifacts={})
            session.add(gs)

        artifacts = dict(gs.artifacts or {})
        existing = artifacts.get(artifact_type)

        entry = {
            "version": version,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "content": content,
        }
        if isinstance(existing, list):
            existing.append(entry)
            artifacts[artifact_type] = existing
        elif existing is None:
            artifacts[artifact_type] = [entry]
        else:
            artifacts[artifact_type] = [existing, entry]

        gs.artifacts = artifacts
        await session.commit()


async def get_pipeline_run(run_id: str) -> Optional[Dict[str, Any]]:
    await init_database()
    from app.models.base import AgentRun, GlobalState, PipelineRun

    async with AsyncSessionLocal() as session:
        run = await session.get(PipelineRun, run_id)
        gs = await session.get(GlobalState, run_id)

        if run is None and gs is None:
            return None

        agent_rows = (
            await session.execute(
                select(AgentRun)
                .where(AgentRun.global_state_id == run_id)
                .order_by(AgentRun.created_at.desc())
                .limit(100)
            )
        ).scalars().all()

        return {
            "run_id": run_id,
            "user_id": run.user_id if run else None,
            "idea": run.idea if run else None,
            "config": run.config if run else {},
            "run_state": (run.run_state if run else None) or (gs.run_state if gs else "UNKNOWN"),
            "error": run.error if run else None,
            "project_brief": gs.project_brief if gs else None,
            "phases": gs.phases if gs else None,
            "artifacts": gs.artifacts if gs else None,
            "created_at": run.created_at.isoformat() if run and run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run and run.updated_at else None,
            "completed_at": run.completed_at.isoformat() if run and run.completed_at else None,
            "agent_runs": [
                {
                    "id": row.id,
                    "agent_name": row.agent_name,
                    "iteration": row.iteration,
                    "status": row.status,
                    "error": row.error,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in agent_rows
            ],
        }
