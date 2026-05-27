"""claude-code provider via claude-agent-sdk.

The SDK's `query(prompt, options)` returns an async iterator of Message
objects. We collect AssistantMessage text blocks and read token totals
from the terminal ResultMessage when available, falling back to
tiktoken estimation for either tokens_in or tokens_out when telemetry
is missing.
"""
from __future__ import annotations

import logging
from typing import Any

from armance.config import ProviderConfig
from armance.core.protocols.llm import FinishReason, LLMClient, LLMResponse

logger = logging.getLogger(__name__)

_INSTALL_HINT = (
    "claude-agent-sdk not installed.\n"
    "  Install: pip install 'armance[claude]'  (or: uv pip install 'armance[claude]')\n"
    "  Docs: see 'Optional extras' section in README.md"
)


class ClaudeCodeClient(LLMClient):
    def __init__(self, provider: ProviderConfig) -> None:
        self._provider = provider

    async def embed(
        self,
        text: str,
        model: str,
    ) -> list[float]:
        """Anthropic does not provide an embeddings endpoint."""
        raise NotImplementedError("Anthropic/Claude does not support embeddings.")

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        **params: Any,
    ) -> LLMResponse:
        try:
            import os
            from pathlib import Path
            home_path = Path.home()
            local_path = home_path / ".local"
            try:
                local_path.mkdir(parents=True, exist_ok=True)
                dummy = local_path / ".armance_write_test"
                dummy.write_text("ok", encoding="utf-8")
                dummy.unlink(missing_ok=True)
            except OSError:
                workspace_home = Path.cwd() / "tmp" / "home"
                workspace_home.mkdir(parents=True, exist_ok=True)
                os.environ["HOME"] = str(workspace_home)

            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeAgentOptions,
                ResultMessage,
                TextBlock,
                query,
            )
        except ImportError as exc:
            raise ImportError(_INSTALL_HINT) from exc

        system_prompt = "\n\n".join(
            _content_to_str(m.get("content", "")) for m in messages if m.get("role") == "system"
        ) or None
        prompt = _serialize_user_prompt(messages)

        options = _build_claude_options(
            ClaudeAgentOptions=ClaudeAgentOptions,
            model=model,
            system_prompt=system_prompt,
            params=dict(params),
        )

        text_parts: list[str] = []
        tokens_in = 0
        tokens_out = 0
        cost: float | None = None
        finish_reason: FinishReason = "stop"

        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text_parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    usage = getattr(message, "usage", None) or {}
                    tokens_in = int(usage.get("input_tokens", 0) or 0)
                    tokens_out = int(usage.get("output_tokens", 0) or 0)
                    cost = getattr(message, "total_cost_usd", None)
                    if getattr(message, "is_error", False):
                        finish_reason = "error"
                    stop_reason = getattr(message, "stop_reason", None)
                    if stop_reason == "max_tokens":
                        finish_reason = "length"
        except TypeError as exc:
            if "sequence item 0: expected str instance, dict found" in str(exc):
                raise RuntimeError(
                    "Claude SDK crash : l'outil CLI 'claude-code' a renvoyé une erreur (ex: pb d'authentification ou quota) "
                    "qui fait planter le SDK officiel. Lancez 'claude login' ou vérifiez votre compte Anthropic."
                ) from exc
            raise

        text = "".join(text_parts)
        if tokens_in == 0:
            tokens_in = _estimate_tokens(prompt) + (
                _estimate_tokens(system_prompt) if system_prompt else 0
            )
        if tokens_out == 0:
            tokens_out = _estimate_tokens(text)

        # cost intentionally suppressed: claude-code users are billed via
        # subscription (or have separate API tracking). Showing
        # `total_cost_usd` from the SDK misleads subscription users into
        # thinking they pay for this session. When in doubt, don't show.
        _ = cost
        return LLMResponse(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            finish_reason=finish_reason,
            cost_usd=None,
        )

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        on_token: Any,
        **params: Any,
    ) -> LLMResponse:
        """Claude Agent SDK already streams — yield text as it arrives."""
        try:
            import os
            from pathlib import Path
            home_path = Path.home()
            local_path = home_path / ".local"
            try:
                local_path.mkdir(parents=True, exist_ok=True)
                dummy = local_path / ".armance_write_test"
                dummy.write_text("ok", encoding="utf-8")
                dummy.unlink(missing_ok=True)
            except OSError:
                workspace_home = Path.cwd() / "tmp" / "home"
                workspace_home.mkdir(parents=True, exist_ok=True)
                os.environ["HOME"] = str(workspace_home)

            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeAgentOptions,
                ResultMessage,
                TextBlock,
                query,
            )
        except ImportError as exc:
            raise ImportError(_INSTALL_HINT) from exc

        system_prompt = "\n\n".join(
            _content_to_str(m.get("content", "")) for m in messages if m.get("role") == "system"
        ) or None
        prompt = _serialize_user_prompt(messages)

        options = _build_claude_options(
            ClaudeAgentOptions=ClaudeAgentOptions,
            model=model,
            system_prompt=system_prompt,
            params=dict(params),
        )

        text_parts: list[str] = []
        tokens_in = 0
        tokens_out = 0
        cost: float | None = None
        finish_reason: FinishReason = "stop"

        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text_parts.append(block.text)
                            on_token(block.text)
                elif isinstance(message, ResultMessage):
                    usage = getattr(message, "usage", None) or {}
                    tokens_in = int(usage.get("input_tokens", 0) or 0)
                    tokens_out = int(usage.get("output_tokens", 0) or 0)
                    cost = getattr(message, "total_cost_usd", None)
                    if getattr(message, "is_error", False):
                        finish_reason = "error"
                    stop_reason = getattr(message, "stop_reason", None)
                    if stop_reason == "max_tokens":
                        finish_reason = "length"
        except TypeError as exc:
            if "sequence item 0: expected str instance, dict found" in str(exc):
                raise RuntimeError(
                    "Claude SDK crash : l'outil CLI 'claude-code' a renvoyé une erreur (ex: pb d'authentification ou quota) "
                    "qui fait planter le SDK officiel. Lancez 'claude login' ou vérifiez votre compte Anthropic."
                ) from exc
            raise

        text = "".join(text_parts)
        if tokens_in == 0:
            tokens_in = _estimate_tokens(prompt) + (
                _estimate_tokens(system_prompt) if system_prompt else 0
            )
        if tokens_out == 0:
            tokens_out = _estimate_tokens(text)

        # See note above — cost suppressed for claude-code provider.
        _ = cost
        return LLMResponse(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            finish_reason=finish_reason,
            cost_usd=None,
        )


def _build_claude_options(
    ClaudeAgentOptions: Any,
    model: str,
    system_prompt: str | None,
    params: dict[str, Any],
) -> Any:
    # 1. Map generic tools parameter to allowed_tools
    allowed_tools = list(params.pop("allowed_tools", None) or [])
    tools = params.pop("tools", None)
    if tools:
        for tool in tools:
            if isinstance(tool, dict) and tool.get("name") == "web_search":
                if "WebSearch" not in allowed_tools:
                    allowed_tools.append("WebSearch")
            elif isinstance(tool, str) and tool.lower() == "web_search":
                if "WebSearch" not in allowed_tools:
                    allowed_tools.append("WebSearch")
    if allowed_tools:
        params["allowed_tools"] = allowed_tools

    # 2. Inspect signature to avoid TypeError on unsupported kwargs
    import inspect
    try:
        sig = inspect.signature(ClaudeAgentOptions)
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        if has_var_keyword:
            allowed_keys = None
        else:
            allowed_keys = set(sig.parameters.keys())
    except Exception:
        allowed_keys = {
            "model", "system_prompt", "allowed_tools", "disallowed_tools",
            "permission_mode", "max_turns", "cwd", "max_thinking_tokens",
        }

    options_kwargs = {
        "model": model,
        "system_prompt": system_prompt,
    }
    for k, v in params.items():
        if v is not None:
            if allowed_keys is None or k in allowed_keys:
                options_kwargs[k] = v

    return ClaudeAgentOptions(**options_kwargs)


def _content_to_str(content: Any) -> str:
    """Coerce a message `content` field to a plain string.

    Anthropic-style multipart content arrives as `list[{"type": "text", "text": ...}]`.
    Plain providers send a `str`. Anything else falls back to `str(content)`.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            if isinstance(block, str):
                out.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or block.get("content") or ""
                if isinstance(text, str):
                    out.append(text)
                else:
                    out.append(str(text))
        return "".join(out)
    return str(content) if content is not None else ""


def _serialize_user_prompt(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role")
        content = _content_to_str(msg.get("content", ""))
        if role in (None, "system"):
            continue
        if role == "user":
            parts.append(content)
        else:
            parts.append(f"[{role}] {content}")
    return "\n\n".join(parts)


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:  # pragma: no cover - tiktoken always available per pyproject
        logger.warning("tiktoken unavailable; using rough char/4 estimate")
        return max(1, len(text) // 4)
