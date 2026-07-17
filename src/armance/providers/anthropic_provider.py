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

# Last-resort context window when the live `/v1/models/{id}` capability lookup
# can't be reached or omits the field. Never the primary source — the real
# window is read live in `_fetch`; this is the written-in-stone fallback only.
_FALLBACK_CONTEXT_WINDOW = 200_000


# Tier heuristic: family → cost weight (subscription users don't see this
# as money, but it's still useful to flag opus ≫ sonnet ≫ haiku for budget
# semantics).
def _tier_from_family(model_id: str) -> str:
    low = model_id.lower()
    # Mythos-class (Fable/Mythos 5) sits above Opus — still "high" on this
    # 3-level scale, listed first so the intent is explicit.
    if "fable" in low or "mythos" in low or "opus" in low:
        return "high"
    if "sonnet" in low:
        return "medium"
    return "low"  # haiku and unknowns


# Curated catalogue used when /v1/models can't be reached. Subscription
# (`claude-code`) users authenticate through the SDK and have no
# ANTHROPIC_API_KEY, so the live `/v1/models` call never runs for them —
# this list is their real catalogue, not a rare degraded path. Keep the
# model IDs current (latest Opus/Sonnet/Haiku); no "(fallback)" suffix in
# the display name — it surfaces verbatim in the setup UI.
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
        display_name="Claude Haiku 4.5",
    ),
    ModelSpec(
        id="claude-sonnet-4-6",
        provider="claude-code",
        pricing_in_per_mtok=0.0,
        pricing_out_per_mtok=0.0,
        context_window=1_000_000,
        supports_vision=True,
        supports_search=True,
        search_mode="tool",
        effectively_free=True,
        tier="medium",
        display_name="Claude Sonnet 4.6",
    ),
    ModelSpec(
        id="claude-opus-4-8",
        provider="claude-code",
        pricing_in_per_mtok=0.0,
        pricing_out_per_mtok=0.0,
        context_window=1_000_000,
        supports_vision=True,
        supports_search=True,
        search_mode="tool",
        effectively_free=True,
        tier="high",
        display_name="Claude Opus 4.8",
    ),
    ModelSpec(
        id="claude-sonnet-5",
        provider="claude-code",
        pricing_in_per_mtok=0.0,
        pricing_out_per_mtok=0.0,
        # Conservative floor — bump when the official window is confirmed.
        context_window=200_000,
        supports_vision=True,
        supports_search=True,
        search_mode="tool",
        effectively_free=True,
        tier="medium",
        display_name="Claude Sonnet 5",
    ),
    ModelSpec(
        id="claude-fable-5",
        provider="claude-code",
        pricing_in_per_mtok=0.0,
        pricing_out_per_mtok=0.0,
        # Conservative floor — bump when the official window is confirmed.
        context_window=200_000,
        supports_vision=True,
        supports_search=True,
        search_mode="tool",
        effectively_free=True,
        tier="high",
        display_name="Claude Fable 5",
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
                # Context window is read live from the per-model capability
                # endpoint; the constant is the last-resort fallback only.
                ctx = await self._context_window(client, headers, mid)
                # Anthropic API doesn't expose pricing here — subscription users
                # see it as zero, API-only users compute from family tier.
                out.append(ModelSpec(
                    id=mid,
                    provider=self.name,
                    pricing_in_per_mtok=0.0,
                    pricing_out_per_mtok=0.0,
                    context_window=ctx,
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

    async def _context_window(
        self, client: httpx.AsyncClient, headers: dict[str, str], model_id: str,
    ) -> int:
        """Live context window from `/v1/models/{id}`.

        The list endpoint doesn't carry capability data — only the per-model
        retrieve does. Falls back to `_FALLBACK_CONTEXT_WINDOW` if the call
        fails or the field is missing; a single model's lookup failing must
        not sink the whole catalogue.
        """
        try:
            resp = await client.get(
                f"https://api.anthropic.com/v1/models/{model_id}", headers=headers,
            )
            resp.raise_for_status()
            ctx = resp.json().get("max_input_tokens")
            if isinstance(ctx, int) and ctx > 0:
                return ctx
        except Exception:
            logger.debug("context-window lookup failed for %s; using fallback", model_id)
        return _FALLBACK_CONTEXT_WINDOW
