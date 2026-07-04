"""Catch-all for providers that don't expose a canonical model list.

Gemini and Claude have moved to dedicated live-discovery modules
(`gemini_provider.py`, `anthropic_provider.py`). This module is reduced
to `custom-openai` (any OpenAI-compatible endpoint configured by the
user), whose discovery is best-effort against the standard `/models`
route.
"""
from __future__ import annotations

import logging
import os

import httpx

from armance.providers.base import BaseProvider, ModelSpec

logger = logging.getLogger(__name__)


class CustomOpenAIProvider(BaseProvider):
    """OpenAI-compatible endpoint. Discovery is best-effort: most such
    servers (litellm, vLLM, Ollama, OpenAI itself) expose the standard
    `GET /models` route — runtime2's proxy even answered its 400s with
    "Call `/v1/models` to view available models for your key". When the
    route is missing or the schema unexpected, return an empty list and
    the caller falls back to the configured default model.

    Without this, Malik's catalogue held ONE model and he recruited on
    user-pasted ids with no ground truth (the 400 cascade of 2026-07-03).
    """

    name = "custom-openai"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("CUSTOM_OPENAI_API_KEY") or ""
        self.base_url = (
            base_url or os.environ.get("CUSTOM_OPENAI_BASE_URL") or ""
        ).rstrip("/")
        self.timeout = timeout
        self._cache: list[ModelSpec] | None = None

    async def list_models(self) -> list[ModelSpec]:
        if self._cache is not None:
            return self._cache
        self._cache = await self._fetch()
        return self._cache

    async def _fetch(self) -> list[ModelSpec]:
        if not self.base_url:
            return []
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        url = f"{self.base_url}/models"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(
                        "custom-openai %s returned %s — no catalogue",
                        url, resp.status_code,
                    )
                    return []
                raw = resp.json().get("data", [])
        except Exception:
            logger.warning("custom-openai model discovery failed on %s", url, exc_info=True)
            return []

        out: list[ModelSpec] = []
        for m in raw:
            mid = str(m.get("id", "")).strip() if isinstance(m, dict) else ""
            if not mid:
                continue
            # No pricing/capability contract on custom endpoints: everything
            # lands in "low" so budget filters never hide the user's own
            # models. The endpoint bills the user directly — Armance can't
            # know the tier.
            out.append(ModelSpec(
                id=mid,
                provider=self.name,
                tier="low",
                effectively_free=False,
            ))
        logger.info("custom-openai discovery: %d model(s) from %s", len(out), url)
        return out
