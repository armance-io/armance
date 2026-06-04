"""POST /projects/{pid}/sessions/{sid}/library/action — library mutations.

A button click in the web library (index / load / unload / unindex) runs
the action synchronously against the storage layer and returns a
structured ``{ok, message, error}`` — no LLM turn, no conversation entry,
real success/failure feedback for the UI.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from armance.platform.user import get_current_user
from armance.service.library_web_ops import run_library_action

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["library"])


class LibraryActionIn(BaseModel):
    action: Literal["index", "load", "unload", "unindex"]
    name: Optional[str] = None


@router.post("/library/action")
async def library_action(
    pid: str,
    sid: str,
    body: LibraryActionIn,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Run a library action and return ``{ok, message, error}``."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    # The web session caches the config snapshot taken at session creation, so
    # an embedding-model change (PATCH /admin/config or a hand-edit of
    # config.yaml) wouldn't reach the live indexing path. Reload from disk here
    # so indexing always uses the current embedding provider/model.
    from armance.config import load_config
    try:
        ws.ctx.cfg = load_config(ws.ctx.armance_root.parent)
    except Exception:  # noqa: BLE001 — keep the cached cfg if reload fails
        logger.warning("config reload failed before library action sid=%s", sid, exc_info=True)

    result = await run_library_action(body.action, body.name, ws.ctx)
    logger.info(
        "library action sid=%s action=%s name=%s ok=%s",
        sid, body.action, body.name, result.get("ok"),
    )
    return result
