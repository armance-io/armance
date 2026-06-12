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
    providers_keys: Optional[dict[str, str]] = None
    model: str
    # Two curated postures only (2026-06-10): zero-cost, or the
    # adequacy/environment-optimised heuristic. Power users can still set
    # the other historical values directly in config.yaml.
    budget: Literal["free-first", "optimised"] = "optimised"
    language: Literal["en", "fr", "es", "de", "zh", "ja"] = "en"
    electricity_zone: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None


@router.get("/status")
async def setup_status(
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Check if Armance is initialised (global config — clean break)."""
    from armance import paths

    if not paths.global_config_path().exists():
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

    from armance.config import (
        Config,
        ProviderConfig,
        ensure_data_tree,
        ensure_global_setup,
        save_config,
        write_env,
    )

    # Map the primary provider key
    primary_key = body.api_key or ""
    
    # Gather all configured providers
    providers_dict = body.providers_keys or {}
    if body.provider not in providers_dict and primary_key:
        providers_dict[body.provider] = primary_key

    # Extract metadata keys (e.g. custom-openai_base_url) before iterating
    # so only real provider names are processed.
    custom_base_url = providers_dict.pop("custom-openai_base_url", None)

    providers_list = []
    for prov_name, k in providers_dict.items():
        if prov_name not in ALL_PROVIDERS:
            raise HTTPException(status_code=400, detail=f"unknown_provider: {prov_name}")
        prov = ProviderConfig(
            name=prov_name, # type: ignore
            api_key=k or None,
        )
        if prov_name in _DEFAULT_BASE_URLS:
            prov.base_url = _DEFAULT_BASE_URLS[prov_name]
        # Apply the custom base URL if it was provided for custom-openai
        if prov_name == "custom-openai" and custom_base_url:
            prov.base_url = custom_base_url
        providers_list.append(prov)

    # In case no providers keys dictionary was sent, make sure at least the primary is added
    if not providers_list:
        prov = ProviderConfig(
            name=body.provider, # type: ignore
            api_key=body.api_key or None,
        )
        if body.provider in _DEFAULT_BASE_URLS:
            prov.base_url = _DEFAULT_BASE_URLS[body.provider]
        providers_list.append(prov)

    cfg = Config(
        providers=providers_list,
        default_provider=body.provider,
        default_model=body.model,
        budget_effort=body.budget,
        language=body.language,
        embedding_provider=body.embedding_provider or "",
        embedding_model=body.embedding_model or "",
    )
    if body.electricity_zone:
        from armance.service.footprint_zones import is_valid_zone

        if not is_valid_zone(body.electricity_zone):
            raise HTTPException(status_code=400, detail="unknown_zone")
        cfg.footprint.electricity_mix_zone = body.electricity_zone

    from armance import paths

    try:
        ensure_global_setup(cfg)
        save_config(cfg)
        write_env(providers_list)
        ensure_data_tree(app_state.armance_root)
        from armance.providers.discovery import reset_cache
        reset_cache()
    except Exception as exc:
        logger.exception("Failed to initialise config from setup wizard")
        raise HTTPException(status_code=500, detail=str(exc))

    # Write self-check: confirm config.yaml landed on disk and parses. A silent
    # write failure (Windows %APPDATA% perms / AV / sandbox) otherwise looks like
    # success here but redirects back to /setup on the next boot ("lost info").
    config_dir = paths.global_config_dir()
    config_path = paths.global_config_path()
    if not config_path.exists():
        logger.error("config.yaml absent after save: %s", config_path)
        raise HTTPException(
            status_code=500,
            detail=f"config_write_failed: {config_path} was not created on disk",
        )
    try:
        from armance.config import load_config

        load_config()
    except Exception as exc:
        logger.exception("config.yaml unreadable after save: %s", config_path)
        raise HTTPException(
            status_code=500,
            detail=f"config_write_corrupt: {config_path}: {exc}",
        )

    logger.info("setup config persisted at %s", config_dir)
    return {
        "configured": True,
        "project_id": "default",
        "config_dir": str(config_dir),
    }
