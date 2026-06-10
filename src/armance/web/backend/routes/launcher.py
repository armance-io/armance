"""Launcher routes — project registry + server-side folder browser.

Powers the grandma-launcher window: list known projects, open / create one by
folder, and browse the local filesystem to pick (or create) a folder. All
routes sit behind the Epic-S auth gate. The filesystem routes (browse / new /
mkdir) additionally require a loopback client — they are local-machine
operations with no meaning over the LAN (same guard as admin secrets), so under
``--bind 0.0.0.0`` a remote token-holder gets 403, never a directory walk or a
mkdir. On localhost the browser can reach the whole filesystem (it is the user
on their own disk); the picker just *opens* at home.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from armance.config import ensure_armance_tree
from armance.platform.user import get_current_user
from armance.service import launcher_browse, launcher_registry

router = APIRouter(tags=["launcher"])

_LOOPBACK = {"127.0.0.1", "::1"}

# Filesystem browsing starts here but is not confined to it (local single user).
_FS_ROOT = Path(Path.home().anchor or "/")


def _require_loopback(request: Request) -> JSONResponse | None:
    host = request.client.host if request.client else None
    if host not in _LOOPBACK:
        return JSONResponse(status_code=403, content={"error": "filesystem_localhost_only"})
    return None


class _PathBody(BaseModel):
    path: str


class _MkdirBody(BaseModel):
    path: str
    name: str


def _project_payload(folder: Path) -> dict[str, Any]:
    """Open/new response: the pid the frontend navigates to (/projects/{pid})."""
    resolved = folder.resolve()
    pid = next(
        (p["id"] for p in launcher_registry.list_projects() if p["path"] == str(resolved)),
        None,
    )
    return {"id": pid, "name": resolved.name, "path": str(resolved)}


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
    return _project_payload(folder)


@router.post("/launcher/new")
async def new_project(
    body: _PathBody, request: Request, _user: str = Depends(get_current_user)
) -> Any:
    if (denied := _require_loopback(request)) is not None:
        return denied
    folder = Path(body.path)
    if not folder.is_dir():
        return JSONResponse(status_code=404, content={"error": "path_not_found"})
    # Provision the per-folder data tree, then register it.
    ensure_armance_tree(folder)
    launcher_registry.bump_project(folder)
    return _project_payload(folder)


@router.get("/launcher/browse")
async def browse(
    request: Request,
    path: str | None = None,
    _user: str = Depends(get_current_user),
) -> Any:
    """List immediate subdirectories of *path*.

    Opens at the user's home but can navigate the whole local filesystem
    (loopback-only). ``_confined_resolve`` still rejects nonexistent paths and
    symlink loops.
    """
    if (denied := _require_loopback(request)) is not None:
        return denied
    target = Path(path) if path else Path.home()
    try:
        return launcher_browse.browse(target, root=_FS_ROOT)
    except launcher_browse.BrowseError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_path", "detail": str(exc)})


@router.post("/launcher/mkdir")
async def mkdir(
    body: _MkdirBody, request: Request, _user: str = Depends(get_current_user)
) -> Any:
    """Create a single subdirectory inside *path* (loopback-only)."""
    if (denied := _require_loopback(request)) is not None:
        return denied
    try:
        created = launcher_browse.make_dir(Path(body.path), body.name, root=_FS_ROOT)
    except launcher_browse.BrowseError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_path", "detail": str(exc)})
    return {"path": str(created), "name": created.name}
