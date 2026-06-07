"""Launcher routes — project registry + server-side folder browser.

Powers the grandma-launcher window: list known projects, open / create one by
folder, and browse the local filesystem to pick a folder. All routes sit
behind the Epic-S auth gate (mounted under both "" and "/api" like every other
data router). ``/browse`` is confined to the user's home directory.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from armance.config import ensure_armance_tree
from armance.platform.user import get_current_user
from armance.service import launcher_browse, launcher_registry

router = APIRouter(tags=["launcher"])


class _PathBody(BaseModel):
    path: str


@router.get("/launcher")
async def get_launcher(_user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Launcher state: known projects, most-recent first."""
    return {"projects": launcher_registry.list_projects()}


@router.post("/launcher/open")
async def open_project(
    body: _PathBody, _user: str = Depends(get_current_user)
) -> Any:
    folder = Path(body.path)
    if not folder.is_dir():
        return JSONResponse(status_code=404, content={"error": "path_not_found"})
    launcher_registry.bump_project(folder)
    return {"name": folder.resolve().name, "path": str(folder.resolve())}


@router.post("/launcher/new")
async def new_project(
    body: _PathBody, _user: str = Depends(get_current_user)
) -> Any:
    folder = Path(body.path)
    if not folder.is_dir():
        return JSONResponse(status_code=404, content={"error": "path_not_found"})
    # Provision the per-folder data tree, then register it.
    ensure_armance_tree(folder)
    launcher_registry.bump_project(folder)
    return {"name": folder.resolve().name, "path": str(folder.resolve())}


@router.get("/launcher/browse")
async def browse(
    path: str | None = None, _user: str = Depends(get_current_user)
) -> Any:
    """List immediate subdirectories of *path*, confined to the user's home."""
    root = Path.home()
    target = Path(path) if path else root
    try:
        return launcher_browse.browse(target, root=root)
    except launcher_browse.BrowseError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_path", "detail": str(exc)})
