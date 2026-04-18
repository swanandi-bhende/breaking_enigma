"""
Socket.IO WebSocket server — bridges Redis pub/sub to frontend clients.

The frontend (usePipelineSocket.ts) connects via Socket.IO and subscribes
to pipeline events using query param: run_id.

This module creates a Socket.IO ASGI app that is mounted into the FastAPI
app via the lifespan or by including the router.

Owned by: Anshul
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

import socketio
from fastapi import APIRouter

logger = logging.getLogger(__name__)

# ── Socket.IO server ──────────────────────────────────────────────────────────

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",  # FastAPI already handles CORS
    logger=False,
    engineio_logger=False,
)

socket_app = socketio.ASGIApp(sio, socketio_path="/socket.io")

# Track active subscriptions: {run_id: set(sid)}
_subscriptions: Dict[str, set] = {}

# ── Socket.IO event handlers ──────────────────────────────────────────────────


@sio.event
async def connect(sid: str, environ: dict, auth: Any = None):
    """Client connected — extract run_id from query string and subscribe."""
    # Parse run_id from query string (?run_id=xxx)
    query_string = environ.get("QUERY_STRING", "")
    run_id = None
    for part in query_string.split("&"):
        if part.startswith("run_id="):
            run_id = part.split("=", 1)[1]
            break

    if not run_id:
        logger.warning(f"Socket connected without run_id: sid={sid}")
        return

    logger.info(f"Socket connected: sid={sid}, run_id={run_id}")

    # Join a room named by run_id so we can broadcast to all clients for a run
    await sio.enter_room(sid, run_id)

    if run_id not in _subscriptions:
        _subscriptions[run_id] = set()
        # Start Redis listener for this run_id
        await _start_redis_listener(run_id)

    _subscriptions[run_id].add(sid)

    # Send current agent statuses if we have them cached
    try:
        from app.core.redis import get_agent_status_cache
        agents = ["research", "product_manager", "designer", "developer", "qa", "devops", "documentation"]
        for agent in agents:
            cached = await get_agent_status_cache(run_id, agent)
            if cached:
                await sio.emit(
                    "AGENT_STATUS_CHANGED",
                    {"agent_name": agent, "new_status": cached.get("status", "PENDING")},
                    to=sid,
                )
    except Exception as e:
        logger.debug(f"Could not send cached statuses: {e}")


@sio.event
async def disconnect(sid: str):
    """Client disconnected — clean up room membership."""
    logger.info(f"Socket disconnected: sid={sid}")
    for run_id, sids in list(_subscriptions.items()):
        sids.discard(sid)
        if not sids:
            del _subscriptions[run_id]


async def _start_redis_listener(run_id: str) -> None:
    """
    Start an async background task that subscribes to Redis channels
    for a run and forwards messages to Socket.IO clients.
    """
    import asyncio

    async def _listen():
        try:
            from app.core.redis import get_redis
            from app.core.events import pipeline_events_channel, pipeline_logs_channel

            redis = await get_redis()
            pubsub = redis.pubsub()

            events_channel = pipeline_events_channel(run_id)
            logs_channel = pipeline_logs_channel(run_id)

            await pubsub.subscribe(events_channel, logs_channel)
            logger.info(f"Redis listener started for run_id={run_id}")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                # Check if anyone is still listening
                if run_id not in _subscriptions or not _subscriptions[run_id]:
                    break

                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue

                event_type = data.get("event_type", "")
                agent_name = data.get("agent_name", "")

                # Route to the right Socket.IO event name
                if event_type == "AGENT_STATUS_CHANGED":
                    await sio.emit(
                        "AGENT_STATUS_CHANGED",
                        {
                            "agent_name": agent_name,
                            "new_status": data.get("new_status", "PENDING"),
                            "previous_status": data.get("previous_status"),
                        },
                        room=run_id,
                    )

                elif event_type == "AGENT_LOG_LINE":
                    await sio.emit(
                        "AGENT_LOG_LINE",
                        {
                            "agent_name": agent_name,
                            "line": data.get("line", ""),
                            "level": data.get("level", "info"),
                        },
                        room=run_id,
                    )

                elif event_type == "QA_VERDICT":
                    await sio.emit(
                        "QA_VERDICT",
                        {
                            "qa_score": data.get("qa_score"),
                            "verdict": data.get("verdict"),
                            "bugs_count": data.get("bugs_count", 0),
                            "critical_bugs_count": data.get("critical_bugs_count", 0),
                        },
                        room=run_id,
                    )

                elif event_type == "GLOBAL_STATE_UPDATED":
                    await sio.emit(
                        "GLOBAL_STATE_UPDATED",
                        {"state": data.get("state", {})},
                        room=run_id,
                    )

                elif event_type in ("PIPELINE_STARTED", "PIPELINE_COMPLETE", "PIPELINE_FAILED", "PIPELINE_AWAITING_HUMAN"):
                    await sio.emit(
                        event_type,
                        {k: v for k, v in data.items() if k != "event_type"},
                        room=run_id,
                    )

                elif event_type == "ARTIFACT_READY":
                    await sio.emit(
                        "ARTIFACT_READY",
                        {
                            "agent_name": agent_name,
                            "artifact_type": data.get("artifact_type"),
                            "version": data.get("version"),
                        },
                        room=run_id,
                    )

            await pubsub.unsubscribe(events_channel, logs_channel)
            logger.info(f"Redis listener stopped for run_id={run_id}")

        except Exception as e:
            logger.error(f"Redis listener error for run_id={run_id}: {e}")

    import asyncio
    asyncio.create_task(_listen())


# ── Dummy APIRouter so main.py can import this module ─────────────────────────
# The actual Socket.IO app is mounted separately in main.py via socket_app

router = APIRouter()
