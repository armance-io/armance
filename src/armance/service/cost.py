"""Price lookup + workflow cost estimator.

Prices come from THREE sources, resolved in order:

  1. **Config override** (`cfg.prices` in `.armance/config.yaml`) — the user's
     own table, always wins. Shape: `{ "<model>": {"input_per_mtok": x,
     "output_per_mtok": y} }`.
  2. **Live OpenRouter discovery** (`providers.model_discovery`) — cached
     per-process. Returns the upstream pricing for any model id that
     comes back from `/models`.
  3. **`:free` heuristic** — anything ending in `:free` (or matching
     `/free` in its slug) is treated as zero-cost.
  4. **None match → returns `None`**. Callers must handle that (typically
     by displaying `?` rather than fabricating a price).

There is no built-in price table. The previous hard-coded list went stale
the moment a provider published a new model. Configuring `prices:` in
`config.yaml` is the supported override path; live discovery covers the
rest.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

ASSUMED_OUTPUT_TOKENS = 600

_FREE_PRICE: dict[str, float] = {"input_per_mtok": 0.0, "output_per_mtok": 0.0}

# Cache for live OpenRouter prices: {model_id: {"input_per_mtok": x, "output_per_mtok": y}}
_LIVE_CACHE: dict[str, dict[str, float]] | None = None


def _live_openrouter_prices() -> dict[str, dict[str, float]]:
    """Best-effort blocking discovery of OpenRouter prices. Cached for the
    lifetime of the process. Returns {} on any failure (offline, no key,
    upstream changed shape) — callers fall through to other sources."""
    global _LIVE_CACHE
    if _LIVE_CACHE is not None:
        return _LIVE_CACHE
    try:
        import httpx
        with httpx.Client(timeout=8.0) as c:
            resp = c.get("https://openrouter.ai/api/v1/models")
            if resp.status_code != 200:
                _LIVE_CACHE = {}
                return _LIVE_CACHE
            data = resp.json().get("data", [])
        out: dict[str, dict[str, float]] = {}
        for m in data:
            mid = m.get("id") or ""
            pricing = m.get("pricing") or {}
            try:
                p_in = float(pricing.get("prompt") or 0.0)
                p_out = float(pricing.get("completion") or 0.0)
            except (TypeError, ValueError):
                continue
            # OpenRouter prices are USD per token; we store per MTok.
            out[mid] = {
                "input_per_mtok": p_in * 1_000_000,
                "output_per_mtok": p_out * 1_000_000,
            }
        _LIVE_CACHE = out
        return out
    except Exception:
        logger.debug("OpenRouter live price discovery failed", exc_info=True)
        _LIVE_CACHE = {}
        return _LIVE_CACHE


def lookup_price(
    model: str,
    prices_override: dict[str, dict[str, float]] | None = None,
) -> dict[str, float] | None:
    """Return `{input_per_mtok, output_per_mtok}` for `model`, or None.

    Resolution order: config override → live OpenRouter → `:free` heuristic
    → None.
    """
    override = prices_override or {}
    if model in override:
        return override[model]
    # Slug match against the override (e.g. user defined a prefix).
    for key, val in override.items():
        if model == key or model.startswith(key):
            return val

    live = _live_openrouter_prices()
    if model in live:
        return live[model]
    short = model.split("/", 1)[-1]
    if short in live:
        return live[short]

    if model.endswith(":free") or "/free" in model.lower():
        return _FREE_PRICE
    return None


def token_cost_usd(
    tokens_in: int,
    tokens_out: int,
    model: str,
    prices_override: dict[str, dict[str, float]] | None = None,
) -> float | None:
    """Cost in USD, or None if no price is known for `model`."""
    p = lookup_price(model, prices_override)
    if p is None:
        return None
    return (tokens_in * p["input_per_mtok"] + tokens_out * p["output_per_mtok"]) / 1_000_000


def estimate_workflow(
    workflow: Any,
    agents: list[Any],
    user_prompt: str,
    context_size_tokens: int = 0,
    prices_override: dict[str, dict[str, float]] | None = None,
    intense: bool = False,
) -> dict[str, Any]:
    """Estimate cost for a workflow before running it. See module docstring
    for price resolution. Steps whose model has no known price contribute 0
    to `total_usd` and `cost_usd=None` in their per-step entry — callers
    should render that as `?` rather than `$0`."""
    agent_map = {a.name: a for a in agents}
    step_estimates: list[dict[str, Any]] = []
    by_provider: dict[str, float] = {}
    boosted_agents_seen: set[str] = set()

    for step in workflow.steps:
        if step.kind in ("human_checkpoint", "deliverable"):
            step_estimates.append(
                {"id": step.id, "model": "n/a", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
            )
            continue

        step_agents = [agent_map[n] for n in step.agents if n in agent_map]
        if not step_agents:
            step_agents = list(agents[:1])
        agent_count = min(3, len(step_agents)) if step.mode == "full" else 1

        for agent in step_agents[:agent_count]:
            if intense and getattr(agent, "boost_model", None):
                model = agent.boost_model
                provider = agent.boost_provider or getattr(agent, "provider", "openrouter")
                boosted_agents_seen.add(agent.name)
            else:
                model = getattr(agent, "model", None) or ""
                provider = getattr(agent, "provider", "openrouter")
            prompt_tokens = max(1, len(user_prompt.split()) * 4 // 3)
            tokens_in = 500 + context_size_tokens + prompt_tokens
            tokens_out = ASSUMED_OUTPUT_TOKENS

            cost = token_cost_usd(tokens_in, tokens_out, model, prices_override)
            if cost is not None:
                by_provider[provider] = by_provider.get(provider, 0.0) + cost
            step_estimates.append({
                "id": step.id,
                "model": model or "?",
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": cost,  # may be None
            })

    return {
        "steps": step_estimates,
        "by_provider": by_provider,
        "total_usd": sum(e["cost_usd"] for e in step_estimates if e["cost_usd"] is not None),
        "boosted_count": len(boosted_agents_seen),
    }
