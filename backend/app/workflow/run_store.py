from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_live_state_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(state)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    return payload

RunStoreBackend = Literal["legacy_db", "in_memory", "async_persistent"]
ExecutionMode = Literal["sync_db", "async_db"]


class RunStore(Protocol):
    async def begin_run(
        self,
        *,
        run_id: str,
        idea: str,
        config: Optional[Dict[str, Any]],
        user_id: Optional[str],
    ) -> None:
        ...

    async def append_agent_result(
        self,
        *,
        run_id: str,
        agent_name: str,
        iteration: int,
        input_payload: Dict[str, Any],
        output_payload: Optional[Dict[str, Any]],
        status: str,
        duration_ms: int,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        ...

    async def append_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        content: Dict[str, Any],
        version: int = 1,
    ) -> None:
        ...

    async def update_run_state(self, *, run_id: str, state: Dict[str, Any]) -> None:
        ...

    async def flush(self) -> None:
        ...

    async def finalize_run(self, *, run_id: str, final_state: Dict[str, Any]) -> None:
        ...


def _resolve_backend(config: Optional[Dict[str, Any]]) -> RunStoreBackend:
    raw = str((config or {}).get("run_store_backend") or settings.RUN_STORE_BACKEND).strip().lower()
    if raw in {"legacy_db", "in_memory", "async_persistent"}:
        return raw  # type: ignore[return-value]
    logger.warning("Unknown run_store_backend=%s, falling back to async_persistent", raw)
    return "async_persistent"


def _resolve_execution_mode(config: Optional[Dict[str, Any]]) -> ExecutionMode:
    raw = str((config or {}).get("execution_mode") or settings.RUN_STORE_EXECUTION_MODE).strip().lower()
    if raw in {"sync_db", "async_db"}:
        return raw  # type: ignore[return-value]
    logger.warning("Unknown execution_mode=%s, defaulting to sync_db", raw)
    return "sync_db"


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "y", "on"}:
            return True
        if raw in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _resolve_strict_durability(config: Optional[Dict[str, Any]]) -> bool:
    if "strict_durability" in (config or {}):
        return _as_bool((config or {}).get("strict_durability"), default=False)
    return _as_bool(settings.RUN_STORE_STRICT_DURABILITY, default=False)


def _resolve_canary_percent(config: Optional[Dict[str, Any]]) -> int:
    raw = (config or {}).get("canary_percent", settings.RUN_STORE_CANARY_PERCENT)
    try:
        value = int(raw)
    except Exception:
        value = int(settings.RUN_STORE_CANARY_PERCENT)
    return max(0, min(100, value))


def _resolve_shadow_mode(config: Optional[Dict[str, Any]]) -> bool:
    if "shadow_mode" in (config or {}):
        return _as_bool((config or {}).get("shadow_mode"), default=False)
    return _as_bool(settings.RUN_STORE_SHADOW_MODE, default=False)


def _resolve_flush_batch_size(config: Optional[Dict[str, Any]]) -> int:
    raw = (
        (config or {}).get("flush_batch_size")
        or (config or {}).get("run_store_flush_batch_size")
        or settings.RUN_STORE_FLUSH_BATCH_SIZE
    )
    try:
        value = int(raw)
    except Exception:
        value = int(settings.RUN_STORE_FLUSH_BATCH_SIZE)
    return max(1, value)


def _resolve_flush_interval_ms(config: Optional[Dict[str, Any]]) -> int:
    raw = (
        (config or {}).get("flush_interval_ms")
        or (config or {}).get("run_store_flush_interval_ms")
        or settings.RUN_STORE_FLUSH_INTERVAL_MS
    )
    try:
        value = int(raw)
    except Exception:
        value = int(settings.RUN_STORE_FLUSH_INTERVAL_MS)
    return max(10, value)


def _resolve_checkpoint_interval_ms(config: Optional[Dict[str, Any]]) -> int:
    raw = (
        (config or {}).get("checkpoint_interval_ms")
        or (config or {}).get("run_store_checkpoint_interval_ms")
        or settings.RUN_STORE_CHECKPOINT_INTERVAL_MS
    )
    try:
        value = int(raw)
    except Exception:
        value = int(settings.RUN_STORE_CHECKPOINT_INTERVAL_MS)
    return max(500, value)


def _resolve_checkpoint_every_n_events(config: Optional[Dict[str, Any]]) -> int:
    raw = (
        (config or {}).get("checkpoint_every_n_events")
        or (config or {}).get("run_store_checkpoint_every_n_events")
        or settings.RUN_STORE_CHECKPOINT_EVERY_N_EVENTS
    )
    try:
        value = int(raw)
    except Exception:
        value = int(settings.RUN_STORE_CHECKPOINT_EVERY_N_EVENTS)
    return max(1, value)


def _is_canary_run(run_id: str, canary_percent: int) -> bool:
    if canary_percent <= 0:
        return False
    if canary_percent >= 100:
        return True
    bucket = int(hashlib.md5(run_id.encode("utf-8")).hexdigest(), 16) % 100
    return bucket < canary_percent


@dataclass
class _StoreOperation:
    kind: str
    payload: Dict[str, Any]
    seq: int = 0


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._agent_runs: Dict[str, list[Dict[str, Any]]] = {}
        self._artifacts: Dict[str, list[Dict[str, Any]]] = {}

    async def begin_run(
        self,
        *,
        run_id: str,
        idea: str,
        config: Optional[Dict[str, Any]],
        user_id: Optional[str],
    ) -> None:
        self._runs[run_id] = {
            "run_id": run_id,
            "idea": idea,
            "config": config or {},
            "user_id": user_id,
            "run_state": "INITIALIZING",
            "error": None,
        }
        self._agent_runs.setdefault(run_id, [])
        self._artifacts.setdefault(run_id, [])

    async def append_agent_result(
        self,
        *,
        run_id: str,
        agent_name: str,
        iteration: int,
        input_payload: Dict[str, Any],
        output_payload: Optional[Dict[str, Any]],
        status: str,
        duration_ms: int,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._agent_runs.setdefault(run_id, []).append(
            {
                "agent_name": agent_name,
                "iteration": iteration,
                "status": status,
                "input": input_payload,
                "output": output_payload,
                "duration_ms": duration_ms,
                "error_details": error_details,
            }
        )

    async def append_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        content: Dict[str, Any],
        version: int = 1,
    ) -> None:
        self._artifacts.setdefault(run_id, []).append(
            {
                "artifact_type": artifact_type,
                "version": version,
                "content": content,
            }
        )

    async def update_run_state(self, *, run_id: str, state: Dict[str, Any]) -> None:
        from app.core.redis import set_run_status_cache

        current = self._runs.setdefault(run_id, {"run_id": run_id})
        current.update(
            {
                "run_state": state.get("run_state", current.get("run_state", "RUNNING")),
                "error": state.get("error"),
                "project_brief": state.get("project_brief"),
                "phases": state.get("phases"),
                "artifacts": state.get("artifact_urls"),
            }
        )
        await set_run_status_cache(run_id, _build_live_state_payload(state))

    async def flush(self) -> None:
        return

    async def finalize_run(self, *, run_id: str, final_state: Dict[str, Any]) -> None:
        await self.update_run_state(run_id=run_id, state=final_state)


class LegacyDbRunStore:
    async def begin_run(
        self,
        *,
        run_id: str,
        idea: str,
        config: Optional[Dict[str, Any]],
        user_id: Optional[str],
    ) -> None:
        from app.core.database import create_pipeline_run

        await create_pipeline_run(run_id=run_id, idea=idea, config=config, user_id=user_id)

    async def append_agent_result(
        self,
        *,
        run_id: str,
        agent_name: str,
        iteration: int,
        input_payload: Dict[str, Any],
        output_payload: Optional[Dict[str, Any]],
        status: str,
        duration_ms: int,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        from app.core.database import save_agent_run

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

    async def append_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        content: Dict[str, Any],
        version: int = 1,
    ) -> None:
        from app.core.database import save_artifact

        await save_artifact(run_id=run_id, artifact_type=artifact_type, content=content, version=version)

    async def update_run_state(self, *, run_id: str, state: Dict[str, Any]) -> None:
        from app.core.database import upsert_global_state
        from app.core.redis import set_run_status_cache

        await set_run_status_cache(run_id, _build_live_state_payload(state))
        await upsert_global_state(run_id=run_id, state=state)

    async def flush(self) -> None:
        return

    async def finalize_run(self, *, run_id: str, final_state: Dict[str, Any]) -> None:
        await self.update_run_state(run_id=run_id, state=final_state)


class AsyncPersistentRunStore:
    def __init__(
        self,
        *,
        batch_size: int,
        flush_interval_ms: int,
        checkpoint_interval_ms: int,
        checkpoint_every_n_events: int,
        strict_durability: bool,
        apply_materialized_writes: bool = True,
    ) -> None:
        self._queue: asyncio.Queue[_StoreOperation] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._batch_size = max(1, int(batch_size))
        self._flush_interval = max(10, int(flush_interval_ms)) / 1000.0
        self._checkpoint_interval = max(500, int(checkpoint_interval_ms)) / 1000.0
        self._checkpoint_every_n_events = max(1, int(checkpoint_every_n_events))
        self._strict_durability = bool(strict_durability)
        self._apply_materialized_writes = bool(apply_materialized_writes)
        self._stopping = False
        self._next_seq = 1
        self._events_since_checkpoint = 0
        self._last_checkpoint_at = time.monotonic()
        self._latest_compact_state: Dict[str, Any] = {}

    async def begin_run(
        self,
        *,
        run_id: str,
        idea: str,
        config: Optional[Dict[str, Any]],
        user_id: Optional[str],
    ) -> None:
        await self._ensure_worker()
        # Ensure run record exists before any async writes.
        from app.core.database import create_pipeline_run

        await create_pipeline_run(run_id=run_id, idea=idea, config=config, user_id=user_id)

    async def append_agent_result(
        self,
        *,
        run_id: str,
        agent_name: str,
        iteration: int,
        input_payload: Dict[str, Any],
        output_payload: Optional[Dict[str, Any]],
        status: str,
        duration_ms: int,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._put(
            _StoreOperation(
                kind="agent_result",
                payload={
                    "run_id": run_id,
                    "agent_name": agent_name,
                    "iteration": iteration,
                    "input_payload": input_payload,
                    "output_payload": output_payload,
                    "status": status,
                    "duration_ms": duration_ms,
                    "error_details": error_details,
                },
            )
        )
        if self._strict_durability:
            await self.flush()

    async def append_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        content: Dict[str, Any],
        version: int = 1,
    ) -> None:
        await self._put(
            _StoreOperation(
                kind="artifact",
                payload={
                    "run_id": run_id,
                    "artifact_type": artifact_type,
                    "content": content,
                    "version": version,
                },
            )
        )
        if self._strict_durability:
            await self.flush()

    async def update_run_state(self, *, run_id: str, state: Dict[str, Any]) -> None:
        from app.core.redis import set_run_status_cache

        self._latest_compact_state = self._compact_checkpoint_state(run_id=run_id, state=state)
        run_state = str(state.get("run_state", "")).upper()
        terminal = run_state in {"COMPLETE", "FAILED"}
        queued_seq = self._next_seq
        await set_run_status_cache(
            run_id,
            _build_live_state_payload(state),
            event_sequence=queued_seq,
        )
        await self._put(
            _StoreOperation(
                kind="state",
                payload={"run_id": run_id, "state": state},
            )
        )
        if self._strict_durability or terminal:
            await self.flush()

    async def flush(self) -> None:
        await self._ensure_worker()
        await self._queue.join()

    async def finalize_run(self, *, run_id: str, final_state: Dict[str, Any]) -> None:
        await self.update_run_state(run_id=run_id, state=final_state)
        await self.flush()
        self._stopping = True
        await self._put(_StoreOperation(kind="shutdown", payload={"run_id": run_id}))
        if self._worker_task is not None:
            await self._worker_task

    async def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._stopping = False
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def _put(self, op: _StoreOperation) -> None:
        await self._ensure_worker()
        if op.kind != "shutdown":
            op.seq = self._next_seq
            self._next_seq += 1
        await self._queue.put(op)

    async def _worker_loop(self) -> None:
        while True:
            batch = await self._collect_batch()
            normal_ops = [op for op in batch if op.kind != "shutdown"]

            try:
                if normal_ops:
                    await self._flush_batch(normal_ops)
            except Exception as exc:
                logger.exception("run_store async batch persist failed size=%s error=%s", len(normal_ops), exc)
            finally:
                for _ in batch:
                    self._queue.task_done()

            if any(op.kind == "shutdown" for op in batch):
                break

    async def _collect_batch(self) -> list[_StoreOperation]:
        first = await self._queue.get()
        batch = [first]

        if first.kind == "shutdown":
            return batch

        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._flush_interval

        while len(batch) < self._batch_size:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break

            try:
                nxt = await asyncio.wait_for(self._queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                break

            batch.append(nxt)
            if nxt.kind == "shutdown":
                break

        return batch

    async def _flush_batch(self, ops: list[_StoreOperation]) -> None:
        from app.core.database import persist_store_operations_batch

        max_seq = max((op.seq for op in ops), default=0)
        events_in_batch = len(ops)
        checkpoint = self._select_checkpoint_payload(events_in_batch=events_in_batch, max_seq=max_seq)

        await persist_store_operations_batch(
            run_id=ops[0].payload["run_id"],
            operations=[
                {"kind": op.kind, "payload": op.payload, "seq": op.seq}
                for op in ops
            ],
            checkpoint=checkpoint,
            checkpoint_seq=max_seq if checkpoint is not None else None,
            apply_materialized_writes=self._apply_materialized_writes,
        )

        self._events_since_checkpoint += events_in_batch
        if checkpoint is not None:
            self._events_since_checkpoint = 0
            self._last_checkpoint_at = time.monotonic()

    def _select_checkpoint_payload(self, *, events_in_batch: int, max_seq: int) -> Optional[Dict[str, Any]]:
        if not self._latest_compact_state:
            return None

        now = time.monotonic()
        by_event_count = (self._events_since_checkpoint + events_in_batch) >= self._checkpoint_every_n_events
        by_time = (now - self._last_checkpoint_at) >= self._checkpoint_interval
        terminal = str(self._latest_compact_state.get("run_state", "")).upper() in {"COMPLETE", "FAILED"}

        if by_event_count or by_time or terminal:
            checkpoint = dict(self._latest_compact_state)
            checkpoint["event_sequence"] = max_seq
            return checkpoint
        return None

    @staticmethod
    def _compact_checkpoint_state(*, run_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "run_id": run_id,
            "user_id": state.get("user_id"),
            "idea": state.get("idea"),
            "config": state.get("config"),
            "run_state": state.get("run_state"),
            "error": state.get("error"),
            "project_brief": state.get("project_brief"),
            "phases": state.get("phases"),
            "artifact_urls": state.get("artifact_urls"),
            "qa_iteration": state.get("qa_iteration"),
            "max_qa_iterations": state.get("max_qa_iterations"),
            "last_failed_agent": state.get("last_failed_agent"),
        }


class ShadowRunStore:
    """Shadow mode: keep sync DB writes authoritative while exercising async pipeline writes."""

    def __init__(self, primary: RunStore, shadow: RunStore) -> None:
        self._primary = primary
        self._shadow = shadow

    async def begin_run(
        self,
        *,
        run_id: str,
        idea: str,
        config: Optional[Dict[str, Any]],
        user_id: Optional[str],
    ) -> None:
        await self._primary.begin_run(run_id=run_id, idea=idea, config=config, user_id=user_id)
        try:
            await self._shadow.begin_run(run_id=run_id, idea=idea, config=config, user_id=user_id)
        except Exception as exc:
            logger.exception("shadow begin_run failed run_id=%s error=%s", run_id, exc)

    async def append_agent_result(
        self,
        *,
        run_id: str,
        agent_name: str,
        iteration: int,
        input_payload: Dict[str, Any],
        output_payload: Optional[Dict[str, Any]],
        status: str,
        duration_ms: int,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._primary.append_agent_result(
            run_id=run_id,
            agent_name=agent_name,
            iteration=iteration,
            input_payload=input_payload,
            output_payload=output_payload,
            status=status,
            duration_ms=duration_ms,
            error_details=error_details,
        )
        try:
            await self._shadow.append_agent_result(
                run_id=run_id,
                agent_name=agent_name,
                iteration=iteration,
                input_payload=input_payload,
                output_payload=output_payload,
                status=status,
                duration_ms=duration_ms,
                error_details=error_details,
            )
        except Exception as exc:
            logger.exception("shadow append_agent_result failed run_id=%s agent=%s error=%s", run_id, agent_name, exc)

    async def append_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        content: Dict[str, Any],
        version: int = 1,
    ) -> None:
        await self._primary.append_artifact(
            run_id=run_id,
            artifact_type=artifact_type,
            content=content,
            version=version,
        )
        try:
            await self._shadow.append_artifact(
                run_id=run_id,
                artifact_type=artifact_type,
                content=content,
                version=version,
            )
        except Exception as exc:
            logger.exception("shadow append_artifact failed run_id=%s artifact=%s error=%s", run_id, artifact_type, exc)

    async def update_run_state(self, *, run_id: str, state: Dict[str, Any]) -> None:
        await self._primary.update_run_state(run_id=run_id, state=state)
        try:
            await self._shadow.update_run_state(run_id=run_id, state=state)
        except Exception as exc:
            logger.exception("shadow update_run_state failed run_id=%s error=%s", run_id, exc)

    async def flush(self) -> None:
        await self._primary.flush()
        try:
            await self._shadow.flush()
        except Exception as exc:
            logger.exception("shadow flush failed error=%s", exc)

    async def finalize_run(self, *, run_id: str, final_state: Dict[str, Any]) -> None:
        await self._primary.finalize_run(run_id=run_id, final_state=final_state)
        try:
            await self._shadow.finalize_run(run_id=run_id, final_state=final_state)
        except Exception as exc:
            logger.exception("shadow finalize_run failed run_id=%s error=%s", run_id, exc)


_RUN_STORE_REGISTRY: Dict[str, RunStore] = {}


def get_run_store(run_id: str, config: Optional[Dict[str, Any]]) -> RunStore:
    existing = _RUN_STORE_REGISTRY.get(run_id)
    if existing is not None:
        return existing

    backend = _resolve_backend(config)
    strict_durability = _resolve_strict_durability(config)
    execution_mode = _resolve_execution_mode(config)
    canary_percent = _resolve_canary_percent(config)
    shadow_mode = _resolve_shadow_mode(config)

    if backend == "in_memory":
        store: RunStore = InMemoryRunStore()
    elif backend == "legacy_db":
        store = LegacyDbRunStore()
    else:
        batch_size = _resolve_flush_batch_size(config)
        flush_interval_ms = _resolve_flush_interval_ms(config)
        checkpoint_interval_ms = _resolve_checkpoint_interval_ms(config)
        checkpoint_every_n_events = _resolve_checkpoint_every_n_events(config)

        if shadow_mode:
            logger.info("run_store rollout=shadow run_id=%s", run_id)
            store = ShadowRunStore(
                primary=LegacyDbRunStore(),
                shadow=AsyncPersistentRunStore(
                    batch_size=batch_size,
                    flush_interval_ms=flush_interval_ms,
                    checkpoint_interval_ms=checkpoint_interval_ms,
                    checkpoint_every_n_events=checkpoint_every_n_events,
                    strict_durability=strict_durability,
                    apply_materialized_writes=False,
                ),
            )
        else:
            use_async = execution_mode == "async_db"
            if not use_async and canary_percent > 0:
                use_async = _is_canary_run(run_id, canary_percent)

            if use_async:
                stage = "cutover" if execution_mode == "async_db" and canary_percent in {0, 100} else "canary"
                logger.info(
                    "run_store rollout=%s run_id=%s canary_percent=%s strict_durability=%s",
                    stage,
                    run_id,
                    canary_percent,
                    strict_durability,
                )
                store = AsyncPersistentRunStore(
                    batch_size=batch_size,
                    flush_interval_ms=flush_interval_ms,
                    checkpoint_interval_ms=checkpoint_interval_ms,
                    checkpoint_every_n_events=checkpoint_every_n_events,
                    strict_durability=strict_durability,
                )
            else:
                logger.info("run_store rollout=sync run_id=%s canary_percent=%s", run_id, canary_percent)
                store = LegacyDbRunStore()

    _RUN_STORE_REGISTRY[run_id] = store
    return store


def clear_run_store(run_id: str) -> None:
    _RUN_STORE_REGISTRY.pop(run_id, None)
