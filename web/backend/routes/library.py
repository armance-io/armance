"""GET /projects/{pid}/sessions/{sid}/library — library status.

Returns the RAG / bibliothèque status for the current session's armance_root.
Delegates to armance.storage.rag_status.get_rag_status.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from armance.platform.user import get_current_user
from armance.storage.rag_status import get_rag_status

from backend.deps import get_app_state
from backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["library"])


@router.get("/library")
async def library_status(
    pid: str,
    sid: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Return indexed + read state of the bibliothèque."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    try:
        status = get_rag_status(ws.ctx.armance_root, ws.ctx.cfg)
    except Exception as exc:
        logger.warning("library_status failed sid=%s: %s", sid, exc)
        status = {}

    return {"library": status}
