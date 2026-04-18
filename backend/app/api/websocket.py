import json
import logging
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.redis import get_redis
from app.core.events import pipeline_events_channel, pipeline_logs_channel

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def handle_websocket(websocket: WebSocket):
    run_id = websocket.query_params.get("run_id")

    if not run_id:
        await websocket.close(code=1008, reason="Missing run_id")
        return

    await websocket.accept()
    logger.info("WebSocket connected run_id=%s", run_id)

    redis = await get_redis()
    pubsub = redis.pubsub()

    await pubsub.subscribe(
        pipeline_events_channel(run_id),
        pipeline_logs_channel(run_id),
    )

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)

            if message and message.get("type") == "message":
                data = message.get("data")

                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")

                # ensure valid JSON output
                try:
                    json.loads(data)
                    payload = data
                except Exception:
                    payload = json.dumps({
                        "event_type": "AGENT_LOG_LINE",
                        "line": str(data)
                    })

                await websocket.send_text(payload)

            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected run_id=%s", run_id)

    except Exception as exc:
        logger.warning("WebSocket error run_id=%s error=%s", run_id, exc)

    finally:
        await pubsub.unsubscribe(
            pipeline_events_channel(run_id),
            pipeline_logs_channel(run_id),
        )
        await pubsub.close()