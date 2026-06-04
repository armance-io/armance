"""POST /projects/{pid}/sessions/{sid}/checkpoint — resolve a checkpoint.

Called by the frontend after the user answers a checkpoint prompt.
Delegates to WebCheckpointHandler.resolve().
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from armance.platform.user import get_current_user

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["checkpoint"])


class CheckpointIn(BaseModel):
    checkpoint_id: str
    content: str
    is_abort: bool = False


@router.post("/checkpoint")
async def resolve_checkpoint(
    pid: str,
    sid: str,
    body: CheckpointIn,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Resolve a pending checkpoint by id."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    resolved = ws.handler.resolve(body.checkpoint_id, body.content, body.is_abort)
    return {"resolved": resolved}
