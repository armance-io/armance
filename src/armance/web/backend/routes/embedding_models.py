"""GET /embedding-models — cross-provider embedding catalogue route.

Mirrors ``providers.py`` but narrows to embedding-capable models. Used by
the admin Configuration form and the setup wizard to populate the
embedding-model picker (type-ahead + free text). OpenRouter enumerates
keyless; Gemini needs a saved key; custom-openai cannot be enumerated and
is surfaced as a free-text hint.

Reuses the same discovery helpers the CLI ``armance init`` flow uses, so
there is one source of truth for what counts as an embedding model.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from armance.config import ProviderConfig, load_config
from armance.platform.user import get_current_user

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["providers"])

_DEFAULT_PROVIDERS = ("openrouter", "claude-code", "gemini", "custom-openai")


async def _discover_embedding(armance_root) -> list[dict[str, Any]]:
    """Inner helper — keeps the route trivially mockable in tests.

    Returns a list of ``{provider, id, name, free}`` dicts.
    """
    from armance.providers.model_discovery import (
        discover_gemini_embedding_models,
        discover_openrouter_embedding_models,
    )

    cfg = load_config(armance_root.parent)
    providers = cfg.providers or [ProviderConfig(name=n) for n in _DEFAULT_PROVIDERS]

    out: list[dict[str, Any]] = []
    for prov in providers:
        name = prov.name
        if name == "openrouter":
            for m in await discover_openrouter_embedding_models(prov.api_key):
                out.append({"provider": name, "id": m["id"], "name": m["name"], "free": m["free"]})
        elif name == "gemini" and prov.api_key:
            for m in await discover_gemini_embedding_models(prov.api_key, prov.base_url):
                out.append({"provider": name, "id": m["id"], "name": m["name"], "free": m["free"]})
        # claude-code: no embeddings endpoint. custom-openai: cannot enumerate
        # — both are handled by the free-text picker on the client.
    return out


@router.get("/embedding-models")
async def get_embedding_models(
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    """Return the cross-provider embedding catalogue.

    Shape: ``{ "models": [{provider, id, name, free}, ...] }``. On error,
    returns an empty list (the client falls back to free-text entry).
    """
    try:
        models = await _discover_embedding(app_state.armance_root)
    except Exception as exc:  # noqa: BLE001 — discovery is best-effort
        logger.warning("embedding discovery failed: %s", exc)
        return {"models": []}
    return {"models": models}
