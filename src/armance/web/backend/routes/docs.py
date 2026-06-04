"""POST /projects/{pid}/sessions/{sid}/docs — upload a document.

Saves the file to <armance_root>/docs/<filename>.
The indexing step is NOT triggered here — the user initiates it via
/turn with "/library index <file>" or via the library endpoint.
Per web-layer.md §4.1 and I.12 (all writes through Storage ABC).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from armance.platform.storage import LocalFilesystemStorage
from armance.platform.user import get_current_user

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["docs"])


@router.post("/docs", status_code=201)
async def upload_doc(
    pid: str,
    sid: str,
    file: UploadFile,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Upload a document to <armance_root>/docs/<filename>.

    I.12: all writes go through the Storage ABC, not pathlib directly.
    """
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    storage = LocalFilesystemStorage(root=ws.ctx.armance_root)
    filename = file.filename or "unnamed"
    key = f"docs/{filename}"
    data = await file.read()
    await storage.write_bytes(key, data)

    size = len(data)
    logger.info("doc uploaded sid=%s filename=%s size=%d", sid, filename, size)
    return {"name": filename, "size": size}
