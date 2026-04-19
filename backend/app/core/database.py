from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import func, select
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


async def persist_store_operations_batch(
    *,
    run_id: str,
    operations: list[Dict[str, Any]],
    checkpoint: Optional[Dict[str, Any]] = None,
    checkpoint_seq: Optional[int] = None,
    apply_materialized_writes: bool = True,
) -> None:
    """
    Persist a run-store batch in a single AsyncSession + single commit.

    This amortizes DB round-trips and avoids concurrent use of the same
    connection across many tiny writes.
    """
    if not operations:
        return

    await init_database()
    from app.models.base import AgentRun, GlobalState, PipelineRun, RunCheckpoint, RunEvent

    async with AsyncSessionLocal() as session:
        for op in operations:
            kind = str(op.get("kind", "")).strip().lower()
            payload = op.get("payload") or {}
            seq = int(op.get("seq") or 0)

            if seq <= 0:
                raise ValueError(f"Invalid run_store sequence number: {seq}")

            session.add(
                RunEvent(
                    id=str(uuid4()),
                    run_id=run_id,
                    seq=seq,
                    kind=kind,
                    payload=payload,
                )
            )

            if not apply_materialized_writes:
                continue

            if kind == "agent_result":
                session.add(
                    AgentRun(
                        id=str(uuid4()),
                        global_state_id=payload["run_id"],
                        agent_name=payload["agent_name"],
                        iteration=payload["iteration"],
                        status=payload["status"],
                        output={
                            "input": payload["input_payload"],
                            "output": payload.get("output_payload"),
                            "duration_ms": payload["duration_ms"],
                            "error_details": payload.get("error_details"),
                        },
                        error=(payload.get("error_details") or {}).get("message"),
                    )
                )
                continue

            if kind == "artifact":
                run_id = payload["run_id"]
                artifact_type = payload["artifact_type"]
                content = payload["content"]
                version = payload.get("version", 1)

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
                continue

            if kind == "state":
                run_id = payload["run_id"]
                state = payload["state"]
                run_state = str(state.get("run_state", "RUNNING"))

                gs = await session.get(GlobalState, run_id)
                if gs is None:
                    gs = GlobalState(id=run_id)
                    session.add(gs)

                gs.run_state = run_state
                gs.project_brief = state.get("project_brief")
                gs.phases = state.get("phases")
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

                if run_state in {"COMPLETE", "FAILED"} and run.completed_at is None:
                    run.completed_at = datetime.now(timezone.utc)
                continue

            raise ValueError(f"Unsupported run_store batch operation kind: {kind}")

        if checkpoint is not None:
            if checkpoint_seq is None:
                raise ValueError("checkpoint_seq is required when checkpoint is provided")
            session.add(
                RunCheckpoint(
                    id=str(uuid4()),
                    run_id=run_id,
                    seq=int(checkpoint_seq),
                    state=checkpoint,
                )
            )

        await session.commit()


def _apply_recovery_event(state: Dict[str, Any], kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if kind == "state":
        snapshot = dict(payload.get("state") or {})
        state.update(
            {
                "run_id": payload.get("run_id") or state.get("run_id"),
                "run_state": snapshot.get("run_state", state.get("run_state")),
                "error": snapshot.get("error", state.get("error")),
                "project_brief": snapshot.get("project_brief", state.get("project_brief")),
                "phases": snapshot.get("phases", state.get("phases")),
                "artifact_urls": snapshot.get("artifact_urls", state.get("artifact_urls")),
                "config": snapshot.get("config", state.get("config")),
                "user_id": snapshot.get("user_id", state.get("user_id")),
                "idea": snapshot.get("idea", state.get("idea")),
                "qa_iteration": snapshot.get("qa_iteration", state.get("qa_iteration")),
                "max_qa_iterations": snapshot.get("max_qa_iterations", state.get("max_qa_iterations")),
            }
        )
    elif kind == "artifact":
        artifact_urls = dict(state.get("artifact_urls") or {})
        artifact_type = payload.get("artifact_type")
        if artifact_type:
            artifact_urls[artifact_type] = artifact_urls.get(artifact_type) or "persisted"
            state["artifact_urls"] = artifact_urls
    return state


async def reconstruct_run_state(run_id: str) -> Dict[str, Any]:
    """
    Deterministically reconstruct compact run state from latest checkpoint + events.
    """
    await init_database()
    from app.models.base import RunCheckpoint, RunEvent

    async with AsyncSessionLocal() as session:
        checkpoint_row = (
            await session.execute(
                select(RunCheckpoint)
                .where(RunCheckpoint.run_id == run_id)
                .order_by(RunCheckpoint.seq.desc())
                .limit(1)
            )
        ).scalars().first()

        state: Dict[str, Any] = dict((checkpoint_row.state if checkpoint_row else {}) or {})
        state["run_id"] = run_id
        checkpoint_seq = int(checkpoint_row.seq) if checkpoint_row else 0

        event_rows = (
            await session.execute(
                select(RunEvent)
                .where(RunEvent.run_id == run_id, RunEvent.seq > checkpoint_seq)
                .order_by(RunEvent.seq.asc())
            )
        ).scalars().all()

        max_seq = checkpoint_seq
        for event in event_rows:
            max_seq = max(max_seq, int(event.seq))
            _apply_recovery_event(state, str(event.kind), dict(event.payload or {}))

        if checkpoint_seq == 0 and max_seq == 0:
            max_seq_row = (
                await session.execute(
                    select(func.max(RunEvent.seq)).where(RunEvent.run_id == run_id)
                )
            ).scalar_one_or_none()
            max_seq = int(max_seq_row or 0)

        state["event_sequence"] = max_seq
        state["checkpoint_sequence"] = checkpoint_seq
        return state


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

        recovered = await reconstruct_run_state(run_id)
        recovered_run_state = recovered.get("run_state")
        recovered_error = recovered.get("error")
        recovered_project_brief = recovered.get("project_brief")
        recovered_phases = recovered.get("phases")
        recovered_artifacts = recovered.get("artifact_urls")

        return {
            "run_id": run_id,
            "user_id": recovered.get("user_id") if recovered.get("user_id") is not None else (run.user_id if run else None),
            "idea": recovered.get("idea") if recovered.get("idea") is not None else (run.idea if run else None),
            "config": recovered.get("config") if recovered.get("config") is not None else (run.config if run else {}),
            "run_state": recovered_run_state or (run.run_state if run else None) or (gs.run_state if gs else "UNKNOWN"),
            "error": recovered_error if recovered_error is not None else (run.error if run else None),
            "project_brief": recovered_project_brief if recovered_project_brief is not None else (gs.project_brief if gs else None),
            "phases": recovered_phases if recovered_phases is not None else (gs.phases if gs else None),
            "artifacts": recovered_artifacts if recovered_artifacts is not None else (gs.artifacts if gs else None),
            "created_at": run.created_at.isoformat() if run and run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run and run.updated_at else None,
            "completed_at": run.completed_at.isoformat() if run and run.completed_at else None,
            "event_sequence": recovered.get("event_sequence", 0),
            "checkpoint_sequence": recovered.get("checkpoint_sequence", 0),
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
