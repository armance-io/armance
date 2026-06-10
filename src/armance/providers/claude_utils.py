from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


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

    # Hermetic by default: without an explicit (even empty) value the SDK
    # omits --setting-sources and the CLI then loads the HOST user's Claude
    # Code settings — CLAUDE.md, plugins and hooks — into every Armance
    # agent call. A user-level "caveman" plugin hook is exactly how
    # telegraphic replies kept leaking into A2H turns.
    setting_sources = params.pop("setting_sources", [])

    options_kwargs = {
        "model": model,
        "system_prompt": system_prompt,
    }
    if allowed_keys is None or "setting_sources" in allowed_keys:
        options_kwargs["setting_sources"] = setting_sources
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
