"""OpenRouter / OpenAI-compatible HTTP provider via httpx."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from armance.config import ProviderConfig
from armance.core.protocols.llm import FinishReason, LLMClient, LLMResponse, RerankHit

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT = 120.0


class LLMHTTPError(RuntimeError):
    """Raised on non-2xx responses from the upstream LLM API.

    ``status_code`` lets callers special-case retryable statuses (429);
    ``retry_after`` carries the provider's Retry-After hint in seconds,
    when present.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


def _retry_after_seconds(response: Any) -> float | None:
    """Numeric Retry-After response header in seconds, if present."""
    try:
        raw = response.headers.get("retry-after")
        return float(raw) if raw else None
    except Exception:
        return None


class OpenRouterClient(LLMClient):
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
        ssl_verify = getattr(provider, "ssl_verify", True)
        self._client = client or httpx.AsyncClient(timeout=timeout, verify=ssl_verify)

    @property
    def base_url(self) -> str:
        return self._provider.base_url or DEFAULT_BASE_URL

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        **params: Any,
    ) -> LLMResponse:
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._provider.api_key:
            headers["Authorization"] = f"Bearer {self._provider.api_key}"

        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False, **params}
        response = await self._client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise LLMHTTPError(
                f"openrouter call failed: {response.status_code} {response.text}",
                status_code=response.status_code,
                retry_after=_retry_after_seconds(response),
            )

        data = response.json()
        return _parse_chat_completion(data)

    async def embed(
        self,
        text: str,
        model: str,
    ) -> list[float]:
        """Async embed (used at query time for top-k retrieval). Logs to the
        exchange log and the global ledger so retrieval cost is tracked."""
        from armance.service.llm_service import (
            get_ledger,
            log_failure,
            log_request,
            log_response,
        )

        log_request("embedding", model, [{"role": "user", "content": text[:200]}])
        url = self.base_url.rstrip("/") + "/embeddings"
        headers = {"Content-Type": "application/json"}
        if self._provider.api_key:
            headers["Authorization"] = f"Bearer {self._provider.api_key}"
        try:
            response = await self._client.post(
                url, headers=headers, json={"model": model, "input": text}
            )
            if response.status_code >= 400:
                raise LLMHTTPError(
                    f"openrouter embeddings failed: {response.status_code} {response.text}",
                    status_code=response.status_code,
                    retry_after=_retry_after_seconds(response),
                )
            data = response.json()
            usage = data.get("usage") or {}
            tokens_in = int(usage.get("prompt_tokens") or usage.get("total_tokens") or 0)
            log_response("embedding", model, LLMResponse(
                text=f"<embedding dim={len(data['data'][0]['embedding'])}>",
                tokens_in=tokens_in,
                tokens_out=0,
                finish_reason="stop",
                cost_usd=None,
            ))
            try:
                get_ledger().record("embedding", tokens_in, 0, None)
            except Exception:
                pass
            return data["data"][0]["embedding"]
        except Exception as exc:
            log_failure("embedding", model, exc, attempt=1, max_retries=1)
            raise

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        *,
        top_n: int | None = None,
    ) -> list[RerankHit]:
        """Cross-encoder rerank via POST /rerank (Cohere-style wire format).

        Serves both `openrouter` and `custom-openai` (same client class),
        BUT openrouter.ai itself exposes no /rerank route: without a
        base_url override pointing at a proxy that does (TEI, Infinity,
        LiteLLM), this 404s and the service layer degrades to vector
        order. `custom-openai` against such an endpoint is the supported
        path. Logs to the exchange log + ledger like embed."""
        from armance.service.llm_service import (
            get_ledger,
            log_failure,
            log_request,
            log_response,
        )

        log_request("rerank", model, [{"role": "user", "content": query[:200]}])
        url = self.base_url.rstrip("/") + "/rerank"
        headers = {"Content-Type": "application/json"}
        if self._provider.api_key:
            headers["Authorization"] = f"Bearer {self._provider.api_key}"
        body: dict[str, Any] = {"model": model, "query": query, "documents": documents}
        if top_n is not None:
            body["top_n"] = top_n
        try:
            response = await self._client.post(url, headers=headers, json=body)
            if response.status_code >= 400:
                raise LLMHTTPError(
                    f"openrouter rerank failed: {response.status_code} {response.text}",
                    status_code=response.status_code,
                    retry_after=_retry_after_seconds(response),
                )
            data = response.json()
            results = data.get("results") or []
            hits = [
                RerankHit(index=int(r["index"]), score=float(r.get("relevance_score", 0.0)))
                for r in results
            ]
            hits.sort(key=lambda h: h.score, reverse=True)
            usage = data.get("usage") or {}
            tokens_in = int(usage.get("total_tokens") or 0)
            log_response("rerank", model, LLMResponse(
                text=f"<rerank results={len(hits)}>",
                tokens_in=tokens_in, tokens_out=0,
                finish_reason="stop", cost_usd=None,
            ))
            try:
                get_ledger().record("rerank", tokens_in, 0, None)
            except Exception:
                pass
            return hits
        except Exception as exc:
            log_failure("rerank", model, exc, attempt=1, max_retries=1)
            raise

    def embed_sync(self, text: str, model: str, timeout: float = 60.0) -> list[float]:
        """Blocking embed used from sync code (ingestion.sync_docs).

        Avoids the asyncio.run / run_coroutine_threadsafe dance — which
        deadlocks when sync_docs is called from a worker thread launched by
        asyncio.to_thread (no event loop to schedule on, then httpx tries to
        own its own one).

        Logs the request/response to .armance/logs/llm_exchanges.jsonl and
        records token usage in the global ledger so embedding cost flows
        into the TUI total like any chat call.
        """
        from armance.service.llm_service import (
            get_ledger,
            log_failure,
            log_request,
            log_response,
        )
        from armance.core.protocols.llm import LLMResponse

        log_request("embedding", model, [{"role": "user", "content": text[:200]}])
        url = self.base_url.rstrip("/") + "/embeddings"
        headers = {"Content-Type": "application/json"}
        if self._provider.api_key:
            headers["Authorization"] = f"Bearer {self._provider.api_key}"
        try:
            ssl_verify = getattr(self._provider, "ssl_verify", True)
            with httpx.Client(timeout=timeout, verify=ssl_verify) as client:
                response = client.post(url, headers=headers, json={"model": model, "input": text})
            if response.status_code >= 400:
                raise LLMHTTPError(
                    f"openrouter embeddings failed: {response.status_code} {response.text}",
                    status_code=response.status_code,
                    retry_after=_retry_after_seconds(response),
                )
            data = response.json()
            usage = data.get("usage") or {}
            tokens_in = int(usage.get("prompt_tokens") or usage.get("total_tokens") or 0)
            log_response("embedding", model, LLMResponse(
                text=f"<embedding dim={len(data['data'][0]['embedding'])}>",
                tokens_in=tokens_in,
                tokens_out=0,
                finish_reason="stop",
                cost_usd=None,
            ))
            try:
                get_ledger().record("embedding", tokens_in, 0, None)
            except Exception:
                pass
            return data["data"][0]["embedding"]
        except Exception as exc:
            log_failure("embedding", model, exc, attempt=1, max_retries=1)
            raise

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        on_token: Any,
        **params: Any,
    ) -> LLMResponse:
        """Stream via SSE, yield tokens via on_token callback."""
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._provider.api_key:
            headers["Authorization"] = f"Bearer {self._provider.api_key}"

        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True, **params}

        text_parts: list[str] = []
        tokens_in = 0
        tokens_out = 0
        finish_reason: FinishReason = "stop"
        cost_usd: float | None = None

        # httpx streams via `client.stream("POST", ...)`, NOT a `stream=`
        # kwarg on `.post()` — that signature is from `requests` and raises
        # TypeError on AsyncClient. Use the proper context-manager API.
        async with self._client.stream("POST", url, headers=headers, json=payload) as response:
            if response.status_code >= 400:
                body = (await response.aread()).decode("utf-8", errors="replace")
                raise LLMHTTPError(
                    f"openrouter call failed: {response.status_code} {body}",
                    status_code=response.status_code,
                    retry_after=_retry_after_seconds(response),
                )

            async for line in response.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]  # strip "data: " prefix
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                for choice in choices:
                    delta = choice.get("delta", {})
                    content = _coerce_content(delta.get("content"))
                    if content:
                        text_parts.append(content)
                        on_token(content)
                    fr = choice.get("finish_reason")
                    if fr:
                        finish_reason = _normalize_finish_reason(fr)
                usage = chunk.get("usage")
                if usage:
                    tokens_in = int(usage.get("prompt_tokens", 0))
                    tokens_out = int(usage.get("completion_tokens", 0))
                    cost_usd = float(usage.get("cost", 0) or 0)

        return LLMResponse(
            text=_strip_thinking("".join(text_parts)),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            finish_reason=finish_reason,
            cost_usd=cost_usd,
        )

    async def aclose(self) -> None:
        if self._owned_client:
            await self._client.aclose()


_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning blocks emitted by some models."""
    if not text:
        return text
    cleaned = _THINK_RE.sub("", text)
    # Some models leave a stray "</think>" without an opener
    cleaned = re.sub(r"^\s*</think>\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.lstrip()


def _coerce_content(raw: Any) -> str:
    """Normalise message.content into a plain string.

    Some models return a list of blocks like [{"type":"text","text":"..."}]
    or [{"type":"output_text","text":"..."}]. Concatenate the text fields.
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts: list[str] = []
        for block in raw:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                t = block.get("text") or block.get("content") or ""
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts)
    if isinstance(raw, dict):
        t = raw.get("text") or raw.get("content") or ""
        return t if isinstance(t, str) else ""
    return str(raw)


def _parse_chat_completion(data: dict[str, Any]) -> LLMResponse:
    choice = data["choices"][0]
    message = choice.get("message", {})
    text = _strip_thinking(_coerce_content(message.get("content")))
    finish_reason = _normalize_finish_reason(choice.get("finish_reason"))
    usage = data.get("usage") or {}
    tokens_in = int(usage.get("prompt_tokens", 0))
    tokens_out = int(usage.get("completion_tokens", 0))
    cost = usage.get("cost")
    cost_usd = float(cost) if cost is not None else None
    return LLMResponse(
        text=text,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        finish_reason=finish_reason,
        cost_usd=cost_usd,
    )


def _normalize_finish_reason(raw: Any) -> FinishReason:
    if raw == "stop":
        return "stop"
    if raw == "length":
        return "length"
    if raw in ("content_filter", "tool_calls", None):
        return "other"
    return "other"
