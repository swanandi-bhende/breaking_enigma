"""
Event type definitions for the ADWF Redis pub/sub event bus.

All events emitted from the workflow layer → Redis → WebSocket → Dashboard
follow the schema defined here.

Owned by: Nisarg (Workflow Engine & Agent Orchestration)
"""

from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import json


class EventType(str, Enum):
    # Pipeline lifecycle
    PIPELINE_STARTED = "PIPELINE_STARTED"
    PIPELINE_COMPLETE = "PIPELINE_COMPLETE"
    PIPELINE_FAILED = "PIPELINE_FAILED"
    PIPELINE_AWAITING_HUMAN = "PIPELINE_AWAITING_HUMAN"
    PIPELINE_RESUMED = "PIPELINE_RESUMED"

    # Agent lifecycle
    AGENT_STATUS_CHANGED = "AGENT_STATUS_CHANGED"
    AGENT_LOG_LINE = "AGENT_LOG_LINE"

    # QA-specific
    QA_VERDICT = "QA_VERDICT"
    QA_ROUTING_LOOP = "QA_ROUTING_LOOP"

    # Artifacts
    ARTIFACT_READY = "ARTIFACT_READY"

    # Global state sync
    GLOBAL_STATE_UPDATED = "GLOBAL_STATE_UPDATED"


class AgentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


def build_event(
    event_type: EventType,
    run_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    agent_name: Optional[str] = None,
) -> str:
    """
    Construct a JSON-serialised event payload ready for Redis PUBLISH.

    Args:
        event_type:  One of the EventType enum values.
        run_id:      The pipeline run UUID this event belongs to.
        metadata:    Optional additional data for the event.
        agent_name:  Optional agent name for agent-specific events.

    Returns:
        JSON string suitable for redis.publish(channel, payload).
    """
    payload: Dict[str, Any] = {
        "event_type": event_type.value,
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if agent_name:
        payload["agent_name"] = agent_name
    if metadata:
        payload.update(metadata)

    return json.dumps(payload)


# ── Redis channel helpers ───────────────────────────────────────────────────


def pipeline_events_channel(run_id: str) -> str:
    """Main state-change channel for a single pipeline run."""
    return f"pipeline:{run_id}:events"


def pipeline_logs_channel(run_id: str) -> str:
    """Streaming log line channel for a single pipeline run."""
    return f"pipeline:{run_id}:logs"


GLOBAL_CHANNEL = "pipeline:global"
"""System-wide notification channel (not scoped to a run)."""
