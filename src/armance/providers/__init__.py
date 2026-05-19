"""Armance providers layer.

Concrete LLMClient implementations live here. On package import, each
provider registers itself with the core registry via
`core.protocols.llm.register_client`. Callers should never import the
concrete classes directly — go through `core.protocols.llm.get_client`.
"""
from __future__ import annotations

import logging

from armance.core.protocols.llm import register_client
from armance.providers.openrouter import OpenRouterClient
from armance.providers.claude_code import ClaudeCodeClient, _INSTALL_HINT
from armance.providers.gemini import GeminiClient

logger = logging.getLogger(__name__)

# Warn early if claude-agent-sdk is missing so users see the hint at startup,
# not buried inside a failure log after the first LLM call.
try:
    import claude_agent_sdk as _  # noqa: F401
except ImportError:
    logger.warning(
        "claude-code provider registered but sdk is missing.\n%s", _INSTALL_HINT
    )

# OpenRouter client also serves the OpenAI-compatible 'custom-openai'
# provider type (same wire format, different base_url).
register_client("openrouter", lambda cfg: OpenRouterClient(cfg))
register_client("custom-openai", lambda cfg: OpenRouterClient(cfg))
register_client("claude-code", lambda cfg: ClaudeCodeClient(cfg))
register_client("gemini", lambda cfg: GeminiClient(cfg))
