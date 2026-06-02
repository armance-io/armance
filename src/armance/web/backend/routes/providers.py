"""GET /providers — live provider catalogue route.

Returns the model catalogue per configured provider for frontend
controls (ModelSwitcher in Epic C.9, ProviderStep in Epic E setup).
The provider-discovery layer caches per process, so repeated calls
within the same session don't re-hit the provider APIs.

Spec: web-c-deliberation.md § C.9
"""
from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter, Depends

from armance.config import load_config
from armance.platform.user import get_current_user
from armance.providers.discovery import discover_all

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["providers"])


def _serialise_model(m: Any) -> dict[str, Any]:
    """Coerce a ModelSpec dataclass into a plain JSON-safe dict."""
    if is_dataclass(m):
        d = asdict(m)
    elif isinstance(m, dict):
        d = m
    else:
        d = {k: getattr(m, k) for k in dir(m) if not k.startswith("_")}
    # Drop callables / nested dataclasses we don't surface.
    return {k: v for k, v in d.items() if not callable(v)}


async def _discover_serialised(armance_root) -> dict[str, list[dict[str, Any]]]:
    """Inner helper — keeps the route trivially mockable in tests."""
    cfg = load_config(armance_root.parent)
    if not cfg.providers:
        from armance.config import ProviderConfig
        cfg.providers = [
            ProviderConfig(name="openrouter"),
            ProviderConfig(name="claude-code"),
            ProviderConfig(name="gemini"),
            ProviderConfig(name="custom-openai"),
        ]
    raw = await discover_all(cfg)
    out: dict[str, list[dict[str, Any]]] = {}
    for provider_name, models in raw.items():
        out[provider_name] = [_serialise_model(m) for m in models]
    return out


@router.get("/providers")
async def get_providers(
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    """Return the live provider catalogue.

    Shape: { "providers": { "<provider_name>": [model_spec, ...] } }
    On error, returns an empty catalogue plus a `hint` string.
    """
    try:
        catalogue = await _discover_serialised(app_state.armance_root)
    except Exception as exc:
        logger.warning("provider discovery failed: %s", exc)
        return {
            "providers": {},
            "hint": (
                "Provider discovery failed. Check that at least one provider "
                "key is set in .armance/.env (OPENROUTER_API_KEY, "
                "GEMINI_API_KEY, ...)."
            ),
        }
    return {"providers": catalogue}
