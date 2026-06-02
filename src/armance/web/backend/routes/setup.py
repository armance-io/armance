"""Setup routes for browser onboarding (Epic E.1, E.3).

GET  /setup/status  - uninitialised | ready
POST /setup/init    - {provider, api_key, model, budget, language}
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException

from armance.platform.user import get_current_user
from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])


class SetupInitIn(BaseModel):
    provider: str
    api_key: Optional[str] = None
    model: str
    budget: Literal["free-first", "low", "medium", "high", "adaptive"] = "free-first"
    language: Literal["en", "fr", "es", "de", "zh", "ja"] = "en"


@router.get("/status")
async def setup_status(
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Check if the project is initialised."""
    config_path = app_state.armance_root / "config.yaml"
    if not config_path.exists():
        return {
            "configured": False,
            "missing": ["default_provider", "default_model"],
        }
    return {"configured": True}


@router.post("/init", status_code=201)
async def setup_init(
    body: SetupInitIn,
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Initialise the .armance directory from browser inputs."""
    from armance.cli import ALL_PROVIDERS, _DEFAULT_BASE_URLS
    if body.provider not in ALL_PROVIDERS:
        raise HTTPException(status_code=400, detail="unknown_provider")

    from armance.config import Config, ProviderConfig, ensure_armance_tree, save_config, write_env

    prov = ProviderConfig(
        name=body.provider, # type: ignore
        api_key=body.api_key or None,
    )
    if body.provider in _DEFAULT_BASE_URLS:
        prov.base_url = _DEFAULT_BASE_URLS[body.provider]

    cfg = Config(
        providers=[prov],
        default_provider=body.provider,
        default_model=body.model,
        budget_effort=body.budget,
        language=body.language,
    )

    try:
        ensure_armance_tree(app_state.armance_root.parent, cfg)
        save_config(app_state.armance_root.parent, cfg)
        if body.api_key:
            write_env(app_state.armance_root.parent, [prov])
    except Exception as exc:
        logger.exception("Failed to initialise config from setup wizard")
        raise HTTPException(status_code=500, detail=str(exc))

    return {"configured": True, "project_id": "default"}
