"""Gemini provider — live model discovery via /v1beta/models.

Falls back to a minimal static catalogue if the API key is missing or
the call fails. Static fallback is intentionally small (just the
currently-known stable models) — the live call is the source of truth.
"""
from __future__ import annotations

import logging
import os
import re

import httpx

from armance.providers.base import BaseProvider, ModelSpec

logger = logging.getLogger(__name__)


# Minimal fallback catalogue. Only used if /v1beta/models cannot be
# reached. Kept short on purpose — maintenance debt should sit on the
# live endpoint, not here.
_FALLBACK_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(
        id="gemini-2.5-flash",
        provider="gemini",
        pricing_in_per_mtok=0.075,
        pricing_out_per_mtok=0.30,
        context_window=1_000_000,
        supports_vision=True,
        supports_search=True,
        search_mode="tool",
        tier="low",
        display_name="Gemini 2.5 Flash (fallback)",
    ),
    ModelSpec(
        id="gemini-2.5-pro",
        provider="gemini",
        pricing_in_per_mtok=1.25,
        pricing_out_per_mtok=5.0,
        context_window=2_000_000,
        supports_vision=True,
        supports_search=True,
        search_mode="tool",
        tier="medium",
        display_name="Gemini 2.5 Pro (fallback)",
    ),
)

# Models we skip even if Google lists them — embeddings, image, deprecated.
_NON_CHAT_PATTERNS = re.compile(
    r"(embed|image|vision-only|aqa|imagen|veo|gecko|tts|chirp)",
    re.IGNORECASE,
)

# Heuristic for the "flash" vs "pro" tier when Google doesn't return pricing.
def _tier_from_id(model_id: str) -> str:
    low = model_id.lower()
    if "flash" in low:
        return "low"
    if "pro" in low:
        return "medium"
    return "low"


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, *, timeout: float = 10.0) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or ""
        self.timeout = timeout
        self._cache: list[ModelSpec] | None = None

    async def list_models(self) -> list[ModelSpec]:
        if self._cache is not None:
            return self._cache
        if not self.api_key:
            logger.info("Gemini: no API key, using fallback catalogue")
            self._cache = list(_FALLBACK_SPECS)
            return self._cache
        try:
            self._cache = await self._fetch()
        except Exception:
            logger.exception("Gemini discovery failed; using fallback")
            self._cache = list(_FALLBACK_SPECS)
        return self._cache

    async def _fetch(self) -> list[ModelSpec]:
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, params={"key": self.api_key})
            resp.raise_for_status()
            data = resp.json().get("models", [])

        out: list[ModelSpec] = []
        for m in data:
            full_name = m.get("name", "")  # e.g. "models/gemini-2.5-flash"
            mid = full_name.split("/", 1)[1] if "/" in full_name else full_name
            if not mid or _NON_CHAT_PATTERNS.search(mid):
                continue
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" not in methods:
                continue
            ctx_in = int(m.get("inputTokenLimit") or 0)
            tier = _tier_from_id(mid)
            # Gemini API doesn't expose per-model pricing — leave None-ish
            # values so the manifest/cost estimator never invents totals.
            out.append(ModelSpec(
                id=mid,
                provider=self.name,
                pricing_in_per_mtok=0.0,
                pricing_out_per_mtok=0.0,
                context_window=ctx_in,
                supports_reasoning=False,
                supports_vision=True,  # 2.5+ are all multimodal
                supports_search=True,  # all 2.5+ support `tools=[google_search]`
                search_mode="tool",
                effectively_free=False,
                tier=tier,
                display_name=m.get("displayName") or mid,
            ))
        # Stable order: shortest id first (puts `gemini-2.5-flash` ahead of
        # variants like `gemini-2.5-flash-preview-09-09`).
        out.sort(key=lambda x: (len(x.id), x.id))
        return out or list(_FALLBACK_SPECS)
