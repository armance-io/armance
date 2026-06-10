"""Admin secrets routes — /projects/{pid}/admin/secrets/*.

All routes are V2 IP-guarded: only accessible from 127.0.0.1 or ::1.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from armance.platform.storage import LocalFilesystemStorage
from armance.platform.user import get_current_user
from armance.service.env_ops import EnvKeyError, delete_secret, list_secrets, set_secret
from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

router = APIRouter()

_LOOPBACK = {"127.0.0.1", "::1"}


def _global_config_dir() -> Path:
    """Secrets live in the GLOBAL config dir (clean break), not per-project."""
    from armance import paths

    return paths.global_config_dir()

@router.get("/projects/{pid}/admin/secrets")
async def get_secrets(
    pid: str,
    request: Request,
    reveal: bool = False,
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> Any:
    host = request.client.host if request.client else None
    if host not in _LOOPBACK:
        return JSONResponse(status_code=403, content={"error": "secrets_localhost_only"})
    storage = LocalFilesystemStorage(root=_global_config_dir())
    return await list_secrets(storage, reveal=reveal)


@router.put("/projects/{pid}/admin/secrets/{name}")
async def put_secret(
    pid: str,
    name: str,
    body: dict[str, Any],
    request: Request,
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> Any:
    host = request.client.host if request.client else None
    if host not in _LOOPBACK:
        return JSONResponse(status_code=403, content={"error": "secrets_localhost_only"})
    value = body.get("value", "")
    storage = LocalFilesystemStorage(root=_global_config_dir())
    try:
        await set_secret(storage, name, value)
    except EnvKeyError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_key_name", "detail": str(exc)})
    return {"name": name, "set": True}


@router.delete("/projects/{pid}/admin/secrets/{name}")
async def delete_secret_route(
    pid: str,
    name: str,
    request: Request,
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> Any:
    host = request.client.host if request.client else None
    if host not in _LOOPBACK:
        return JSONResponse(status_code=403, content={"error": "secrets_localhost_only"})
    storage = LocalFilesystemStorage(root=_global_config_dir())
    found = await delete_secret(storage, name)
    return {"deleted": found}
