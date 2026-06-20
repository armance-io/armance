from __future__ import annotations

import re
import httpx
import logging
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

_M = TypeVar("_M")

# Patterns that identify non-text-chat models — useless for brainstorming
_NON_TEXT_PATTERNS = re.compile(
    r"(ocr|vision|audio|tts|speech|whisper|embed|image|video|multimodal|diffus|sdxl|dall-e|guard|moderat)",
    re.IGNORECASE,
)

# Patterns that identify embedding models
_EMBED_PATTERNS = re.compile(
    r"embed",
    re.IGNORECASE,
)


def _is_text_chat_model(model_id: str) -> bool:
    """Return True only for text/chat models relevant to brainstorming."""
    if not model_id:
        return False
    return not _NON_TEXT_PATTERNS.search(model_id)


def _is_embedding_model(model_id: str, modality: str | None = None) -> bool:
    """Return True if this is an embedding model."""
    if modality and "embedding" in modality.lower():
        return True
    return bool(_EMBED_PATTERNS.search(model_id))


async def discover_openrouter_embedding_models(api_key: str | None = None) -> list[dict]:
    """Query OpenRouter /models and return embedding models.

    Each entry: {"id": str, "name": str, "dim": int | None, "free": bool}
    """
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
            if resp.status_code != 200:
                return []
            data = resp.json().get("data", [])
            results = []
            for m in data:
                id_ = m.get("id", "")
                if not _is_embedding_model(id_):
                    continue
                pricing = m.get("pricing", {})
                cost = float(pricing.get("prompt") or 0.0)
                results.append({
                    "id": id_,
                    "name": m.get("name") or id_,
                    "dim": None,
                    "free": cost == 0.0,
                })
            results.sort(key=lambda x: (not x["free"], x["id"]))
            return results
    except Exception as e:
        logger.warning("openrouter embedding discovery failed: %s", e)
        return []


async def discover_gemini_embedding_models(api_key: str, base_url: str | None = None) -> list[dict]:
    """Query Gemini /models and return embedding models.

    Each entry: {"id": str, "name": str, "dim": int | None, "free": bool}
    Gemini embedding models support embedContent method.
    """
    base = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base}/models", params={"key": api_key})
            if resp.status_code != 200:
                return []
            models = resp.json().get("models", [])
            results = []
            for m in models:
                name = m.get("name", "")  # e.g. "models/text-embedding-004"
                supported = m.get("supportedGenerationMethods", [])
                if "embedContent" not in supported and not _is_embedding_model(name):
                    continue
                model_id = name.removeprefix("models/")
                results.append({
                    "id": model_id,
                    "name": m.get("displayName") or model_id,
                    "dim": None,
                    "free": True,  # Gemini API free within quotas
                })
            results.sort(key=lambda x: x["id"])
            return results
    except Exception as e:
        logger.warning("gemini embedding discovery failed: %s", e)
        return []


# Curated catalogues for non-OpenRouter providers. Tokens count → coarse
# cost proxy (opus ≫ sonnet ≫ haiku for Anthropic; pro ≫ flash for Google).
# When a user has a flat subscription (Claude Code, Gemini API plan), explicit
# USD pricing is unavailable; Malik relies on these family tiers instead.
_CLAUDE_CODE_MODELS = {
    "high": [
        "claude-opus-4-8",
        "claude-opus-4-7",
    ],
    "medium": [
        "claude-sonnet-4-6",
        "claude-sonnet-4-5",
    ],
    "low": [
        "claude-haiku-4-5",
    ],
    "free-first": [],
}

_GEMINI_MODELS = {
    "high": [
        "gemini-2.5-pro",
    ],
    "medium": [
        "gemini-2.5-flash",
    ],
    "low": [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ],
    "free-first": [
        # Gemini API offers a free tier on flash-lite.
        "gemini-2.0-flash-lite",
    ],
}

# Models supporting the OpenAI-style `reasoning: { effort: low|medium|high }`
# parameter, by provider. Malik checks this before proposing an effort setting.
REASONING_SUPPORT: dict[str, set[str]] = {
    "openrouter": {
        # OpenAI reasoning family on OpenRouter
        "openai/o1", "openai/o1-mini", "openai/o3", "openai/o3-mini",
        # DeepSeek r1 family
        "deepseek/deepseek-r1", "deepseek/deepseek-r1:free",
    },
    # Claude Code SDK exposes thinking but not the OpenAI `effort` knob —
    # treat as unsupported for the Malik proposal.
    "claude-code": set(),
    "gemini": set(),
    "custom-openai": set(),  # provider-dependent; user can override
}


def provider_catalogue(provider_name: str) -> dict[str, list[str]] | None:
    """Return a tier→[model] catalogue for a given provider, or None if
    discovery for that provider is asynchronous (e.g. openrouter)."""
    if provider_name == "claude-code":
        return _CLAUDE_CODE_MODELS
    if provider_name == "gemini":
        return _GEMINI_MODELS
    if provider_name == "custom-openai":
        # Caller is expected to override via config. We return an empty
        # scaffold so Malik knows the provider exists but has no canonical
        # list.
        return {"free-first": [], "low": [], "medium": [], "high": []}
    return None


def supports_reasoning(provider: str, model: str) -> bool:
    """True if the provider+model is known to honour `reasoning.effort`."""
    return model in REASONING_SUPPORT.get(provider, set())


def order_models_by_effort(
    models: list[_M], effort: str, gco2e_lookup: Callable[[_M], float],
) -> list[_M]:
    """Order candidate models for a budget_effort tier.

    'optimised' → ascending estimated gCO2e (greenest first), via the injected
    ``gco2e_lookup`` callable (kept out of this leaf layer to avoid importing
    ``service``). Python's ``sorted`` is stable, so equal-gCO2e ties keep their
    incoming order. All other tiers return ``models`` unchanged (the caller has
    already ordered them by cost index).
    """
    if effort == "optimised":
        return sorted(models, key=gco2e_lookup)
    return models


async def discover_openrouter_models() -> dict[str, list[str]]:
    """Discover OpenRouter text/chat models and categorize them by budget tiers."""
    tiers: dict[str, list[dict]] = {
        "free-first": [],
        "low": [],
        "medium": [],
        "high": [],
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            if resp.status_code != 200:
                return {k: [] for k in tiers}
            data = resp.json().get("data", [])
            for m in data:
                id_ = m.get("id", "")
                if not _is_text_chat_model(id_):
                    continue
                pricing = m.get("pricing", {})
                p_prompt = float(pricing.get("prompt") or 0.0)
                p_comp = float(pricing.get("completion") or 0.0)
                cost_index = p_prompt * 1_000_000 + p_comp * 1_000_000

                entry = {"id": id_, "cost": cost_index}
                if cost_index == 0:
                    tiers["free-first"].append(entry)
                elif cost_index < 0.5:
                    tiers["low"].append(entry)
                elif cost_index < 5.0:
                    tiers["medium"].append(entry)
                else:
                    tiers["high"].append(entry)

        # Sort each tier by cost, keep a curated subset to avoid bloating prompts
        result: dict[str, list[str]] = {}
        for t in tiers:
            tiers[t].sort(key=lambda x: x["cost"])
            result[t] = [x["id"] for x in tiers[t][:15]]

        return result

    except Exception as e:
        logger.error(f"Failed to discover models: {e}")
        return {k: [] for k in tiers}
