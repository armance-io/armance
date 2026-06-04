"""POST /projects/{pid}/sessions/{sid}/library/docs — import document.

Uploads a document to <armance_root>/docs/<filename>.
Optionally triggers sync_docs (auto-index) after the upload.

I.12: all writes go through Storage.write_bytes (LocalFilesystemStorage).
B.2 spec: web-b-viewer.md §B.2
"""
from __future__ import annotations

import logging
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi import Form

from armance.platform.storage import LocalFilesystemStorage
from armance.platform.user import get_current_user
from armance.storage.ingestion import sync_docs

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["library"])

# Maximum upload size: 50 MB
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _validate_filename(filename: str) -> str:
    """Validate and sanitise the uploaded filename.

    Raises HTTPException(400) on empty, path traversal, or absolute path.
    Returns the bare filename (no directory component).
    """
    if not filename or filename.strip() == "":
        raise HTTPException(status_code=400, detail="empty_filename")

    pure = PurePosixPath(filename)
    name = pure.name
    # Reject path traversal or absolute paths.
    if not name or name != filename or ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="invalid_filename")
    return name


@router.post("/library/docs", status_code=201)
async def import_doc(
    pid: str,
    sid: str,
    file: UploadFile,
    auto_index: str = Form(default="false"),
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Import a document into <armance_root>/docs/<filename>.

    auto_index=true: calls sync_docs() after writing.
    All writes go through LocalFilesystemStorage (Storage ABC).
    """
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    filename = _validate_filename(file.filename or "")
    data = await file.read()

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"file_too_large: max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )

    # Write through Storage ABC (I.12).
    storage = LocalFilesystemStorage(root=ws.ctx.armance_root)
    key = f"docs/{filename}"
    await storage.write_bytes(key, data)

    # Auto-index if requested.
    should_index = auto_index.lower() in ("true", "1", "yes")
    indexed = False
    if should_index:
        try:
            result = sync_docs(ws.ctx.armance_root, ws.ctx.cfg)
            indexed = True
            logger.info("sync_docs completed sid=%s result=%s", sid, result)
        except Exception as exc:
            logger.warning("sync_docs failed sid=%s: %s", sid, exc)

    logger.info("doc imported sid=%s filename=%s size=%d indexed=%s", sid, filename, len(data), indexed)
    return {"name": filename, "size": len(data), "indexed": indexed}
