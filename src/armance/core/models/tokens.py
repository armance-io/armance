"""Token counting utilities.

Provides provider-agnostic token counting for LLM requests.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# Model-to-encoding mapping
_MODEL_ENCODING: dict[str, str] = {
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4-turbo": "o200k_base",
    "gpt-3.5-turbo": "o200k_base",
    "claude": "r50k_base",
    "gemini": "r50k_base",
    "openai/": "o200k_base",
}

_TIKTOKEN_PROVIDERS = {"openrouter", "custom-openai"}

_DEFAULT_ENCODING = "cl100k_base"


@lru_cache(maxsize=32)
def _get_tiktoken_encoding(encoding_name: str) -> Any:
    import tiktoken
    return tiktoken.get_encoding(encoding_name)


def _resolve_encoding(model: str) -> str:
    if model in _MODEL_ENCODING:
        return _MODEL_ENCODING[model]
    # Prefix match for openrouter model IDs like "openai/gpt-4o-2024-08-06"
    for prefix, enc in _MODEL_ENCODING.items():
        if model.startswith(prefix):
            return enc
    return _DEFAULT_ENCODING


def count_tokens(text: str, provider: str, model: str) -> int:
    """Count tokens in text for the given provider/model.

    openrouter + custom-openai: tiktoken.
    claude-code + gemini: len(text) // 4 heuristic.
    Unknown provider: heuristic fallback with a warning.
    """
    if provider in _TIKTOKEN_PROVIDERS:
        try:
            enc = _get_tiktoken_encoding(_resolve_encoding(model))
            return len(enc.encode(text))
        except Exception:
            logger.warning("tiktoken failed; falling back to char heuristic")
            return len(text) // 4
    # Heuristic for providers without tiktoken support
    return len(text) // 4


def truncate_to_max_tokens(
    text: str,
    provider: str,
    model: str,
    max_tokens: int,
) -> str:
    """Truncate text to fit within max_tokens."""
    current_tokens = count_tokens(text, provider, model)
    if current_tokens <= max_tokens:
        return text
    # Rough character estimate: 4 chars per token
    ratio = max_tokens / current_tokens
    return text[: int(len(text) * ratio)]


def estimate_cost(
    tokens_in: int,
    tokens_out: int,
    provider: str,
    model: str,
    prices: dict[str, dict[str, float]],
) -> float:
    """Estimate cost in USD for a request."""
    price_in = prices.get(provider, {}).get(model, {}).get("input", 0.0)
    price_out = prices.get(provider, {}).get(model, {}).get("output", 0.0)
    if price_in == 0.0 and price_out == 0.0:
        # Default prices (per million tokens)
        price_in = 0.000003
        price_out = 0.000015
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000
