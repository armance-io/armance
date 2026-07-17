"""Cross-provider model discovery — the single entry point used by Malik
and Kim to enumerate available models.

Session-cached: results live for the lifetime of the armance process, refreshed
on next `armance run`. The cache key is the provider INSTANCE name (e.g.
`custom-openai:lab`), so two instances of the same type never collide; the
provider *class* is resolved from the type part. Configured providers that
don't appear in cfg are simply not queried.
"""
from __future__ import annotations

import logging

from armance.providers.anthropic_provider import ClaudeCodeProvider
from armance.providers.base import BaseProvider, ModelSpec
from armance.providers.gemini_provider import GeminiProvider
from armance.providers.openrouter_provider import OpenRouterProvider
from armance.providers.static_providers import CustomOpenAIProvider

logger = logging.getLogger(__name__)


_PROVIDER_CLASSES: dict[str, type[BaseProvider]] = {
    "openrouter": OpenRouterProvider,
    "gemini": GeminiProvider,
    "claude-code": ClaudeCodeProvider,
    "custom-openai": CustomOpenAIProvider,
}

# Session cache.
_CACHE: dict[str, list[ModelSpec]] = {}


def _provider_cfg(provider_name: str, cfg):
    """Return the ProviderConfig entry for `provider_name`, if any."""
    for p in getattr(cfg, "providers", []) or []:
        if getattr(p, "name", "") == provider_name:
            return p
    return None


def _api_key_for(provider_name: str, cfg) -> str | None:
    """Pull the api_key from cfg.providers[<name>] if it exists."""
    p = _provider_cfg(provider_name, cfg)
    return getattr(p, "api_key", None) if p is not None else None


def _provider_for(name: str, cfg) -> BaseProvider | None:
    from armance.config import provider_type_of

    cls = _PROVIDER_CLASSES.get(provider_type_of(name))
    if cls is None:
        return None
    # Providers that take an API key for discovery (OpenRouter for the
    # auth header, Gemini for /v1beta/models, Anthropic for /v1/models).
    if cls in (OpenRouterProvider, GeminiProvider, ClaudeCodeProvider):
        return cls(api_key=_api_key_for(name, cfg))
    if cls is CustomOpenAIProvider:
        # Needs the user's endpoint too — /models lives on their base_url.
        p = _provider_cfg(name, cfg)
        return cls(
            api_key=getattr(p, "api_key", None) if p is not None else None,
            base_url=getattr(p, "base_url", None) if p is not None else None,
        )
    return cls()


async def discover_provider(provider_name: str, cfg) -> list[ModelSpec]:
    """Return the catalogue for a single provider. Cached for the session."""
    if provider_name in _CACHE:
        return _CACHE[provider_name]
    provider = _provider_for(provider_name, cfg)
    if provider is None:
        logger.warning("Unknown provider: %s", provider_name)
        return []
    models = await provider.list_models()
    _CACHE[provider_name] = models
    return models


async def discover_all(cfg) -> dict[str, list[ModelSpec]]:
    """Return catalogues for every provider configured in cfg.providers."""
    configured = [p.name for p in (getattr(cfg, "providers", None) or [])]
    out: dict[str, list[ModelSpec]] = {}
    for name in configured:
        out[name] = await discover_provider(name, cfg)
    return out


def reset_cache() -> None:
    """Clear the session cache — useful between tests and on user request."""
    _CACHE.clear()


def known_model_ids(provider_name: str) -> set[str]:
    """Ids already discovered for `provider_name` (session cache, sync).

    Empty set means "no catalogue" — either the provider was never queried
    this session or it exposes no model list. Callers must treat empty as
    "validation impossible", NOT as "everything invalid".
    """
    return {m.id for m in _CACHE.get(provider_name, [])}


def filter_for_budget(models: list[ModelSpec], budget: str) -> list[ModelSpec]:
    """Narrow a catalogue to models matching the user's budget tier.

    `budget` is one of: free-first, low, medium, high. Higher budgets include
    lower tiers (a `high` budget sees everything; `low` excludes medium/high).

    `effectively_free` models (Claude Code via subscription, OpenRouter `:free`
    ids) are ALWAYS kept regardless of nominal tier: they cost the user
    nothing at the margin, so excluding them under `free-first` would lock
    out subscription-grade models for no benefit. Their nominal tier still
    surfaces in Malik's UI so opus vs haiku stays comparable.
    """
    order = ["free", "low", "medium", "high"]
    b = (budget or "medium").lower().strip()
    if b == "free-first":
        max_idx = 0
    elif b in order:
        max_idx = order.index(b)
    else:
        max_idx = 2  # medium default
    return [
        m for m in models
        if m.effectively_free or order.index(m.tier) <= max_idx
    ]
