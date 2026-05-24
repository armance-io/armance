"""GET /projects/{pid}/sessions/{sid}/exports/{file} — deliverable download.

Serves files from <armance_root>/exports/<file> as binary responses.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

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
) -> FileResponse:
    """Download a deliverable from <armance_root>/exports/<filename>."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    exports_root = ws.ctx.armance_root / "exports"
    # Security: resolve and ensure the path doesn't escape exports_root.
    try:
        file_path = (exports_root / filename).resolve()
        file_path.relative_to(exports_root.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_path")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="export_not_found")

    return FileResponse(path=str(file_path), filename=file_path.name)
