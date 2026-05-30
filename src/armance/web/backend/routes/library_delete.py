"""DELETE /projects/{pid}/sessions/{sid}/library/docs/{name} — unindex + delete.

Requires a confirmation body {\"confirm\": true}.
Without it → 409 {error: confirm_required}.
Calls forget_doc then removes the file from .armance/docs/.

B.3 spec: web-b-viewer.md §B.3
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from armance.platform.storage import LocalFilesystemStorage
from armance.platform.user import get_current_user
from armance.storage.rag_status import forget_doc

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["library"])


class DeleteDocIn(BaseModel):
    confirm: bool = False


@router.delete("/library/docs/{name}")
async def delete_doc(
    pid: str,
    sid: str,
    name: str,
    body: DeleteDocIn,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Unindex and delete a document from <armance_root>/docs/<name>.

    Requires {confirm: true} in the request body.
    """
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    if not body.confirm:
        raise HTTPException(status_code=409, detail={"error": "confirm_required"})

    # I.12: every backend write goes through Storage ABC.
    storage = LocalFilesystemStorage(root=ws.ctx.armance_root)
    key = f"docs/{name}"
    if not await storage.exists(key):
        raise HTTPException(status_code=404, detail="doc_not_found")

    # Unindex (remove from vector store / JSONL index).
    try:
        forget_doc(ws.ctx.armance_root, name)
        unindexed = True
    except Exception as exc:
        logger.warning("forget_doc failed for %s: %s", name, exc)
        unindexed = False

    # Delete via Storage (no direct pathlib.unlink — I.12).
    await storage.delete(key)

    logger.info("doc deleted sid=%s name=%s unindexed=%s", sid, name, unindexed)
    return {"unindexed": unindexed, "deleted": True}
