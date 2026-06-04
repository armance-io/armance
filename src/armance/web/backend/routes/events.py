"""GET /projects/{pid}/sessions/{sid}/events — SSE stream.

Subscribes to the session's LocalEventBus (asyncio.Queue) and streams
events via Server-Sent Events.  Each event is:
  event: <name>
  data: <json payload>

The stream runs until the client disconnects.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from armance.platform.user import get_current_user

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["events"])

# Polling interval in seconds between queue checks (keeps connection alive).
_HEARTBEAT_INTERVAL = 15.0


@router.get("/events")
async def stream_events(
    pid: str,
    sid: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> EventSourceResponse:
    """SSE stream: subscribe to all events on the session bus."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    bus = ws.bus
    queue = bus.subscribe()

    async def _generator() -> AsyncIterator[dict]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL)
                except asyncio.TimeoutError:
                    # Send a heartbeat comment to keep the connection alive.
                    yield {"comment": "heartbeat"}
                    continue
                payload = {
                    "name": event.name,
                    "attributes": event.attributes,
                    "timestamp": event.timestamp.isoformat(),
                }
                yield {
                    "event": event.name,
                    "data": json.dumps(payload),
                }
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(_generator())
