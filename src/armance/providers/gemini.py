"""Google Gemini provider via REST API."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from armance.config import ProviderConfig
from armance.core.protocols.llm import FinishReason, LLMClient, LLMResponse

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_TIMEOUT = 120.0


class GeminiHTTPError(RuntimeError):
    """Raised on non-2xx responses."""


class GeminiClient(LLMClient):
    def __init__(
        self,
        provider: ProviderConfig,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._provider = provider
        self._timeout = timeout
        self._owned_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    @property
    def base_url(self) -> str:
        return self._provider.base_url or DEFAULT_BASE_URL

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        **params: Any,
    ) -> LLMResponse:
        url = f"{self.base_url}/models/{model}:generateContent"
        params_with_key = dict(params)
        if self._provider.api_key:
            params_with_key["key"] = self._provider.api_key

        contents = _messages_to_contents(messages)
        payload = {"contents": contents, "stream": False, **params_with_key}

        response = await self._client.post(url, json=payload)
        if response.status_code >= 400:
            raise GeminiHTTPError(
                f"gemini call failed: {response.status_code} {response.text}"
            )

        data = response.json()
        return _parse_generate_content(data)

    async def embed(
        self,
        text: str,
        model: str,
    ) -> list[float]:
        url = f"{self.base_url}/models/{model}:embedContent"
        params_with_key = {}
        if self._provider.api_key:
            params_with_key["key"] = self._provider.api_key

        payload = {
            "content": {"parts": [{"text": text}]},
        }

        response = await self._client.post(url, params=params_with_key, json=payload)
        if response.status_code >= 400:
            raise GeminiHTTPError(
                f"gemini embeddings failed: {response.status_code} {response.text}"
            )

        data = response.json()
        # Format: {"embedding": {"values": [...]}}
        return data["embedding"]["values"]

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        on_token: Any,
        **params: Any,
    ) -> LLMResponse:
        """Gemini streaming via generateContent with stream=true."""
        url = f"{self.base_url}/models/{model}:generateContent"
        params_with_key = dict(params)
        if self._provider.api_key:
            params_with_key["key"] = self._provider.api_key

        contents = _messages_to_contents(messages)
        payload = {"contents": contents, "stream": True, **params_with_key}

        response = await self._client.post(url, json=payload, stream=True)
        if response.status_code >= 400:
            raise GeminiHTTPError(
                f"gemini call failed: {response.status_code} {response.text}"
            )

        text_parts: list[str] = []
        tokens_in = 0
        tokens_out = 0
        finish_reason: FinishReason = "stop"

        async for line in response.aiter_lines():
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            candidates = chunk.get("candidates", [])
            for candidate in candidates:
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                for part in parts:
                    text = part.get("text")
                    if text:
                        text_parts.append(text)
                        on_token(text)
                raw_fr = candidate.get("finishReason")
                if raw_fr:
                    finish_reason = _normalize_gemini_finish(raw_fr)
            usage = chunk.get("usageMetadata", {})
            if usage:
                tokens_in = int(usage.get("promptTokenCount", 0))
                tokens_out = int(usage.get("candidatesTokenCount", 0))

        return LLMResponse(
            text="".join(text_parts),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            finish_reason=finish_reason,
            cost_usd=None,
        )

    async def aclose(self) -> None:
        if self._owned_client:
            await self._client.aclose()


def _messages_to_contents(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Map OpenAI messages to Gemini contents format.

    role "system" -> treated as "user" (Gemini doesn't have system role)
    role "assistant" -> "model"
    role "user" -> "user"
    """
    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "system":
            role = "user"
        elif role == "assistant":
            role = "model"
        text = msg.get("content", "") or ""
        if text:
            contents.append({
                "role": role,
                "parts": [{"text": text}],
            })
    return contents


def _parse_generate_content(data: dict[str, Any]) -> LLMResponse:
    """Parse Gemini generateContent response format."""
    candidates = data.get("candidates", [])
    if not candidates:
        return LLMResponse(
            text="",
            tokens_in=0,
            tokens_out=0,
            finish_reason="other",
        )

    candidate = candidates[0]
    content = candidate.get("content", {})
    parts = content.get("parts", [])

    text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
    text = "\n".join(text_parts)

    raw_finish = candidate.get("finish_reason", "STOP")
    finish_reason = _normalize_gemini_finish(raw_finish)

    usage = data.get("usageMetadata", {})
    tokens_in = int(usage.get("promptTokenCount", 0))
    tokens_out = int(usage.get("candidatesTokenCount", 0))

    return LLMResponse(
        text=text,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        finish_reason=finish_reason,
        cost_usd=None,
    )


def _normalize_gemini_finish(raw: Any) -> FinishReason:
    """Map Gemini finish reasons to our FinishReason type."""
    if raw == "STOP":
        return "stop"
    if raw in ("MAX_TOKENS", "OVER_TOKEN_LIMIT"):
        return "length"
    if raw in ("SAFETY", "RECITATION", "LANGUAGE", "OTHER", "FINISH_REASON_UNSPECIFIED"):
        return "other"
    return "other"
