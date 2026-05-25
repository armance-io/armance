"""POST /projects/{pid}/sessions/{sid}/turn — submit user text.

Fires dispatch_input in a background asyncio.Task (fire-and-forget).
Returns 202 Accepted immediately so the browser can subscribe to SSE.

Non-negotiable: all .armance/ writes go through Storage ABC.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from armance.platform.user import get_current_user
from armance.service.tui_bridge import dispatch_input

from backend.deps import get_app_state
from backend.state import AppState, WebSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["turn"])


class TurnIn(BaseModel):
    text: str


async def _run_turn(ws: WebSession, text: str) -> None:
    """Background task: call dispatch_input then publish turn.completed."""
    try:
        reply, agent_name = await dispatch_input(text, ws.ctx)
        await ws.bus.emit("turn.completed", attributes={
            "reply": reply,
            "agent": agent_name or "",
        })
    except Exception as exc:
        logger.exception("turn failed sid=%s", ws.sid)
        await ws.bus.emit("turn.error", attributes={"error": str(exc)})


@router.post("/turn", status_code=202)
async def submit_turn(
    pid: str,
    sid: str,
    body: TurnIn,
    request: Request,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Submit a turn of user text; runs dispatch_input in background."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    # Read-along guard: only the driver may submit turns.
    client_id = request.cookies.get("armance_client_id", user)
    if ws.driver_client_id is not None and client_id != ws.driver_client_id:
        raise HTTPException(status_code=409, detail={"error": "read_along_only"})

    asyncio.create_task(_run_turn(ws, body.text))
    return {"ack": True}
