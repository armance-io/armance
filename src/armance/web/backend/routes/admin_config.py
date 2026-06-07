"""Admin config routes — GET/PATCH /projects/{pid}/admin/config."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from armance.config import load_config, save_config
from armance.platform.user import get_current_user
from armance.service.config_ops import ConfigValidationError, validate_config_patch
from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

router = APIRouter()


def _config_to_dict_safe(cfg: Any) -> dict[str, Any]:
    """Serialise Config to dict, stripping api_key from providers."""
    payload: dict[str, Any] = cfg.model_dump()
    for provider in payload.get("providers", []):
        provider.pop("api_key", None)
    return payload


@router.get("/projects/{pid}/admin/config")
async def get_config(
    pid: str,
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    cfg = load_config()
    return _config_to_dict_safe(cfg)


@router.patch("/projects/{pid}/admin/config")
async def patch_config(
    pid: str,
    patch: dict[str, Any],
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    current = load_config()
    try:
        updated = validate_config_patch(current, patch)
    except ConfigValidationError as exc:
        raise HTTPException(status_code=422, detail={"fields": exc.fields}) from exc
    save_config(updated)
    from armance.providers.discovery import reset_cache
    reset_cache()
    return _config_to_dict_safe(updated)
