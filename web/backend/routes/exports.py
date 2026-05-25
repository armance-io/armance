"""GET /projects/{pid}/sessions/{sid}/exports/{file} — deliverable download.

Serves files from <armance_root>/exports/<file> as binary responses.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from armance.platform.storage import LocalFilesystemStorage
from armance.platform.user import get_current_user

from backend.deps import get_app_state
from backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["exports"])


@router.get("/exports/{filename:path}")
async def download_export(
    pid: str,
    sid: str,
    filename: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> Response:
    """Download a deliverable from <armance_root>/exports/<filename>.
    
    Reads using Storage.read_bytes for V3 backend compatibility.
    """
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    exports_root = ws.ctx.armance_root / "exports"
    
    # Security: resolve and ensure the path doesn't escape exports_root.
    try:
        file_path = (exports_root / filename).resolve()
        if not file_path.is_relative_to(exports_root.resolve()):
            raise ValueError()
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_path")

    # The file path must exist for LocalFilesystemStorage, 
    # but the actual read happens through the Storage interface.
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="export_not_found")

    # Read bytes through the storage interface
    storage = LocalFilesystemStorage(root=ws.ctx.armance_root)
    # The key is relative to armance_root.
    # Note: `filename` might contain subdirectories, so we compute the relative key.
    rel_key = f"exports/{file_path.relative_to(exports_root)}"
    
    try:
        data = await storage.read_bytes(rel_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="export_not_found")

    ext = file_path.suffix.lower()
    if ext == ".md":
        media_type = "text/markdown; charset=utf-8"
    else:
        media_type = "application/octet-stream"

    return Response(content=data, media_type=media_type)
