"""OpenRouter provider — live model discovery via /api/v1/models.

Parses pricing, context window, modality. Filters out non-chat models
(embeddings, vision-only, audio, etc.). Session-cached.
"""
from __future__ import annotations

import logging
import os
import re

import httpx

from armance.providers.base import BaseProvider, ModelSpec, derive_tier

logger = logging.getLogger(__name__)

_NON_TEXT_PATTERNS = re.compile(
    r"(ocr|vision|audio|tts|speech|whisper|embed|image|video|"
    r"diffus|sdxl|dall-e|guard|moderat)",
    re.IGNORECASE,
)

# Models that ship with web search baked in (Perplexity Sonar family,
# OpenRouter `:online` variants, GPT-4o search-preview).
_BUILTIN_SEARCH_PATTERNS = re.compile(
    r"(perplexity/sonar|:online$|gpt-4o-search|search-preview)",
    re.IGNORECASE,
)

# Reasoning-effort families on OpenRouter (best-effort heuristic — used for
# the `supports_reasoning` flag; orthogonal to whether the chat call accepts
# a `reasoning` field).
_REASONING_PATTERNS = re.compile(
    r"(o1|o3|o4|deepseek-r1|deepseek-v3.*reasoning|nemotron.*reasoning|qwen.*thinking)",
    re.IGNORECASE,
)


class OpenRouterProvider(BaseProvider):
    name = "openrouter"

    def __init__(self, api_key: str | None = None, *, timeout: float = 10.0) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY") or ""
        self.timeout = timeout
        self._cache: list[ModelSpec] | None = None

    async def list_models(self) -> list[ModelSpec]:
        if self._cache is not None:
            return self._cache
        self._cache = await self._fetch()
        return self._cache

    async def _fetch(self) -> list[ModelSpec]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/models", headers=headers,
                )
                if resp.status_code != 200:
                    logger.warning("OpenRouter /models returned %s", resp.status_code)
                    return []
                raw = resp.json().get("data", [])
        except Exception:
            logger.exception("OpenRouter model discovery failed")
            return []

        out: list[ModelSpec] = []
        for m in raw:
            mid = m.get("id", "") or ""
            if not mid or _NON_TEXT_PATTERNS.search(mid):
                continue
            pricing = m.get("pricing") or {}
            p_in_per_tok = float(pricing.get("prompt") or 0.0)
            p_out_per_tok = float(pricing.get("completion") or 0.0)
            # OpenRouter prices are per token; convert to per-million.
            p_in_mtok = p_in_per_tok * 1_000_000
            p_out_mtok = p_out_per_tok * 1_000_000
            ctx_window = int((m.get("context_length") or 0) or 0)
            modality = (m.get("architecture") or {}).get("modality") or ""
            supports_vision = "image" in modality.lower()
            supports_reasoning = bool(_REASONING_PATTERNS.search(mid))
            supports_search = bool(_BUILTIN_SEARCH_PATTERNS.search(mid))
            search_mode = "builtin" if supports_search else ""
            is_free_id = ":free" in mid or (p_in_mtok == 0 and p_out_mtok == 0)
            out.append(ModelSpec(
                id=mid,
                provider=self.name,
                pricing_in_per_mtok=p_in_mtok,
                pricing_out_per_mtok=p_out_mtok,
                context_window=ctx_window,
                supports_reasoning=supports_reasoning,
                supports_vision=supports_vision,
                supports_search=supports_search,
                search_mode=search_mode,
                effectively_free=is_free_id,
                tier=derive_tier(p_in_mtok, p_out_mtok),
                display_name=m.get("name") or mid,
            ))
        # Sort: free first, then by cost ascending.
        out.sort(key=lambda x: (x.pricing_in_per_mtok + x.pricing_out_per_mtok, x.id))
        return out
