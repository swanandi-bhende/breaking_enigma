"""
Redis connection & pub/sub helpers for the ADWF workflow layer.

Owned by: Nisarg (Workflow Engine & Agent Orchestration)
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings
from app.core.events import (
    AgentStatus,
    EventType,
    LogLevel,
    build_event,
    pipeline_events_channel,
    pipeline_logs_channel,
    GLOBAL_CHANNEL,
)

logger = logging.getLogger(__name__)

# ── Singleton pool ──────────────────────────────────────────────────────────

_redis_pool: Optional[Redis] = None


async def get_redis() -> Redis:
    """Return (and lazily create) the shared async Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await aioredis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
    return _redis_pool


async def close_redis() -> None:
    """Gracefully close the Redis pool (call on app shutdown)."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


# ── Agent lock helpers ──────────────────────────────────────────────────────

AGENT_LOCK_TTL = 300  # seconds


def _lock_key(run_id: str, agent_name: str) -> str:
    return f"agent_lock:{run_id}:{agent_name}"


def _status_key(run_id: str, agent_name: str) -> str:
    return f"agent_status:{run_id}:{agent_name}"


async def acquire_agent_lock(run_id: str, agent_name: str) -> bool:
    """
    Attempt to acquire an exclusive lock for an agent run.
    Returns True if lock was acquired, False if already locked.
    """
    redis = await get_redis()
    result = await redis.set(
        _lock_key(run_id, agent_name),
        "locked",
        nx=True,
        ex=AGENT_LOCK_TTL,
    )
    return result is not None


async def release_agent_lock(run_id: str, agent_name: str) -> None:
    """Release the agent lock after execution (success or failure)."""
    redis = await get_redis()
    await redis.delete(_lock_key(run_id, agent_name))


# ── Agent status cache ──────────────────────────────────────────────────────


async def set_agent_status_cache(
    run_id: str,
    agent_name: str,
    status: AgentStatus,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Write fast-read agent status to Redis (used by dashboard polling)."""
    redis = await get_redis()
    payload = {"status": status.value, **(extra or {})}
    await redis.set(
        _status_key(run_id, agent_name),
        json.dumps(payload),
        ex=3600,
    )


async def get_agent_status_cache(run_id: str, agent_name: str) -> Optional[Dict[str, Any]]:
    """Read cached agent status. Returns None if not found."""
    redis = await get_redis()
    raw = await redis.get(_status_key(run_id, agent_name))
    return json.loads(raw) if raw else None


# ── Pub/Sub event emission ──────────────────────────────────────────────────


async def publish_event(
    run_id: str,
    event_type: EventType,
    metadata: Optional[Dict[str, Any]] = None,
    agent_name: Optional[str] = None,
) -> None:
    """
    Publish a structured event to the Redis pub/sub channel for a run.
    Also mirrors to the global channel for system-wide listeners.
    """
    redis = await get_redis()
    payload = build_event(event_type, run_id, metadata=metadata, agent_name=agent_name)
    channel = pipeline_events_channel(run_id)

    await redis.publish(channel, payload)
    await redis.publish(GLOBAL_CHANNEL, payload)

    logger.debug("Published %s on %s", event_type.value, channel)


async def publish_log_line(
    run_id: str,
    agent_name: str,
    line: str,
    level: LogLevel = LogLevel.INFO,
) -> None:
    """
    Stream a single log line to the pipeline log channel.
    The frontend LiveLogStream component subscribes to this channel.
    """
    redis = await get_redis()
    payload = build_event(
        EventType.AGENT_LOG_LINE,
        run_id,
        metadata={"line": line, "level": level.value},
        agent_name=agent_name,
    )
    await redis.publish(pipeline_logs_channel(run_id), payload)


# ── Human checkpoint suspend/resume ────────────────────────────────────────

_CHECKPOINT_KEY = "human_checkpoint:{run_id}"
_CHECKPOINT_RESULT_KEY = "human_checkpoint_result:{run_id}"
_CHECKPOINT_POLL_INTERVAL = 2  # seconds
_CHECKPOINT_TTL = 86400  # 24 hours


async def signal_human_checkpoint(run_id: str, after_agent: str) -> None:
    """
    Mark a pipeline as waiting for human approval.
    The /api/v1/runs/{run_id}/approve endpoint writes the result key.
    """
    redis = await get_redis()
    await redis.set(
        _CHECKPOINT_KEY.format(run_id=run_id),
        after_agent,
        ex=_CHECKPOINT_TTL,
    )
    await publish_event(
        run_id,
        EventType.PIPELINE_AWAITING_HUMAN,
        metadata={"after_agent": after_agent},
    )


async def wait_for_human_approval(run_id: str) -> Dict[str, Any]:
    """
    Poll Redis until the human approval result is written.
    Returns: {"approved": bool, "feedback": str | None}

    This is called inside the LangGraph node so the graph suspends here.
    """
    import asyncio

    redis = await get_redis()
    result_key = _CHECKPOINT_RESULT_KEY.format(run_id=run_id)

    while True:
        raw = await redis.get(result_key)
        if raw:
            await redis.delete(result_key)  # consume once
            return json.loads(raw)
        await asyncio.sleep(_CHECKPOINT_POLL_INTERVAL)


async def submit_human_approval(
    run_id: str,
    approved: bool,
    feedback: Optional[str] = None,
) -> None:
    """
    Called by the API route /api/v1/runs/{run_id}/approve.
    Writes the result so wait_for_human_approval() can unblock.
    """
    redis = await get_redis()
    result_key = _CHECKPOINT_RESULT_KEY.format(run_id=run_id)
    payload = json.dumps({"approved": approved, "feedback": feedback})
    await redis.set(result_key, payload, ex=300)

    # Clean up checkpoint marker
    await redis.delete(_CHECKPOINT_KEY.format(run_id=run_id))

    event = EventType.PIPELINE_RESUMED if approved else EventType.PIPELINE_FAILED
    await publish_event(run_id, event, metadata={"feedback": feedback})


# ── Rate limiting ────────────────────────────────────────────────────────────


async def check_rate_limit(agent_name: str, limit: int = 60) -> bool:
    """
    Increment the per-minute request counter for an agent's LLM calls.
    Returns True if within limit, False if exceeded.
    """
    redis = await get_redis()
    key = f"rate_limit:llm:{agent_name}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)  # reset window every 60s
    return count <= limit
