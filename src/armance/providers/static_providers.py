"""Catch-all for providers that don't expose a discoverable model list.

Gemini and Claude have moved to dedicated live-discovery modules
(`gemini_provider.py`, `anthropic_provider.py`). This module is reduced
to the one provider that genuinely has no canonical catalogue:
`custom-openai` (any OpenAI-compatible endpoint configured by the user).
"""
from __future__ import annotations

import logging

from armance.providers.base import BaseProvider, ModelSpec

logger = logging.getLogger(__name__)


class CustomOpenAIProvider(BaseProvider):
    """OpenAI-compatible endpoint. Discovery is best-effort: many such
    servers expose a `/v1/models` route, but we cannot rely on it being
    available or on the response schema being stable. Returns an empty
    list by default — the user provides model ids manually via config or
    via Malik's chat.
    """

    name = "custom-openai"

    async def list_models(self) -> list[ModelSpec]:
        return []
