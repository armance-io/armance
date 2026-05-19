"""Claude Code / Anthropic provider — live model discovery.

The Claude Code SDK doesn't expose a `/models` endpoint of its own, but
the Anthropic Messages API does (`GET /v1/models`). If an ANTHROPIC_API_KEY
is available in the environment we use that; otherwise we fall back to a
minimal static catalogue.

Subscription users (the typical `claude-code` provider case) treat these
models as "effectively free" — no per-token cost, the cost lives in the
monthly subscription fee.
"""
from __future__ import annotations

import logging
import os

import httpx

from armance.providers.base import BaseProvider, ModelSpec

logger = logging.getLogger(__name__)


# Tier heuristic: family → cost weight (subscription users don't see this
# as money, but it's still useful to flag opus ≫ sonnet ≫ haiku for budget
# semantics).
def _tier_from_family(model_id: str) -> str:
    low = model_id.lower()
    if "opus" in low:
        return "high"
    if "sonnet" in low:
        return "medium"
    return "low"  # haiku and unknowns


# Fallback if /v1/models can't be reached. Kept to three entries — the
# Anthropic Messages API is stable enough that the live call almost always
# works when the key is set.
_FALLBACK_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(
        id="claude-haiku-4-5",
        provider="claude-code",
        pricing_in_per_mtok=0.0,
        pricing_out_per_mtok=0.0,
        context_window=200_000,
        supports_vision=True,
        supports_search=True,
        search_mode="tool",
        effectively_free=True,
        tier="low",
        display_name="Claude Haiku 4.5 (fallback)",
    ),
    ModelSpec(
        id="claude-sonnet-4-6",
        provider="claude-code",
        pricing_in_per_mtok=0.0,
        pricing_out_per_mtok=0.0,
        context_window=200_000,
        supports_vision=True,
        supports_search=True,
        search_mode="tool",
        effectively_free=True,
        tier="medium",
        display_name="Claude Sonnet 4.6 (fallback)",
    ),
    ModelSpec(
        id="claude-opus-4-7",
        provider="claude-code",
        pricing_in_per_mtok=0.0,
        pricing_out_per_mtok=0.0,
        context_window=200_000,
        supports_vision=True,
        supports_search=True,
        search_mode="tool",
        effectively_free=True,
        tier="high",
        display_name="Claude Opus 4.7 (fallback)",
    ),
)


class ClaudeCodeProvider(BaseProvider):
    name = "claude-code"

    def __init__(self, api_key: str | None = None, *, timeout: float = 10.0) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or ""
        self.timeout = timeout
        self._cache: list[ModelSpec] | None = None

    async def list_models(self) -> list[ModelSpec]:
        if self._cache is not None:
            return self._cache
        if not self.api_key:
            logger.info("Anthropic: no API key, using fallback catalogue")
            self._cache = list(_FALLBACK_SPECS)
            return self._cache
        try:
            self._cache = await self._fetch()
        except Exception:
            logger.exception("Anthropic discovery failed; using fallback")
            self._cache = list(_FALLBACK_SPECS)
        return self._cache

    async def _fetch(self) -> list[ModelSpec]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                "https://api.anthropic.com/v1/models", headers=headers,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])

        out: list[ModelSpec] = []
        for m in data:
            mid = m.get("id", "")
            if not mid or not mid.startswith("claude-"):
                continue
            # Anthropic API doesn't expose pricing here — subscription users
            # see it as zero, API-only users compute from family tier.
            out.append(ModelSpec(
                id=mid,
                provider=self.name,
                pricing_in_per_mtok=0.0,
                pricing_out_per_mtok=0.0,
                context_window=200_000,  # all current Claude models
                supports_reasoning=False,
                supports_vision=True,
                supports_search=True,
                search_mode="tool",
                effectively_free=True,
                tier=_tier_from_family(mid),
                display_name=m.get("display_name") or mid,
            ))
        # Sort: tier high→low so opus surfaces first under `budget=high`.
        order = {"high": 0, "medium": 1, "low": 2, "free": 3}
        out.sort(key=lambda x: (order.get(x.tier, 99), x.id))
        return out or list(_FALLBACK_SPECS)
