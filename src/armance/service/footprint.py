"""Environmental footprint estimation for LLM requests.

Single entry point: ``estimate_footprint()``.
Wraps EcoLogits (MPL-2.0, genai-impact/ecologits) via a 6-tier resolution
chain.  No SDK monkey-patching — only the pure ``compute_llm_impacts``
function is called (in ``footprint_resolve._build_footprint``).

Resolution chain
----------------
1. exact        — (provider, model) is in the EcoLogits registry as-is.
2. aliased      — id is in env_model_aliases.yaml; re-key and retry exact.
3. params       — caller supplies active_params / total_params directly.
4. similar      — provider family is known; borrow the family's default model.
5. provider-default — no family match; use a conservative 8B dense bucket.
6. unknown/None — id ends with ':free' and no params; never fabricate.

``estimate=True`` for tiers 4–5 only.  EcoLogits' inherent RangeValue
(MoE / ranged PUE) is not an "estimate" flag — we collapse it to the mean.

Resolution primitives (alias table, family maps, the compute wrapper) live in
``footprint_resolve``; this module owns the public chain only.

Layer rule: only ``armance.core`` imports allowed here.  No client/transport.
"""
from __future__ import annotations

import logging

from armance.core.models.footprint import Footprint
from armance.service.footprint_resolve import (
    FAMILY_DEFAULT,
    PROVIDER_DEFAULT_ACTIVE_PARAMS,
    PROVIDER_DEFAULT_PROXY,
    PROVIDER_DEFAULT_TOTAL_PARAMS,
    _build_footprint,
    _infer_eco_provider,
    _load_aliases,
    eco_models,
)

logger = logging.getLogger(__name__)

__all__ = ["estimate_footprint"]


def estimate_footprint(
    provider: str,
    model: str,
    tokens_out: int,
    latency_s: float,
    zone: str = "WOR",
    active_params: float | None = None,
    total_params: float | None = None,
) -> Footprint | None:
    """Estimate the environmental footprint of a single LLM response.

    Returns ``None`` (tier "unknown") only when the id ends in ``:free`` and
    no param counts are supplied.  All other cases return a Footprint, with
    ``estimate=True`` for tiers 4–5.

    Args:
        provider: Armance provider name ("openrouter", "anthropic", "gemini",
            "claude-code", "custom-openai", …).
        model: Armance model id (e.g. "anthropic/claude-sonnet-4-6",
            "gemini-2.0-flash", or a bare EcoLogits name when provider is
            already a direct EcoLogits family).
        tokens_out: Number of output tokens in the response.
        latency_s: Wall-clock request latency in seconds.
        zone: ISO 3166-1 alpha-3 electricity-mix zone (default "WOR").
        active_params: Active parameter count in billions (tier 3 seam).
        total_params: Total parameter count in billions (tier 3 seam).
    """
    # ------------------------------------------------------------------
    # Tier 6 — unknown (:free with no params → never fabricate)
    # ------------------------------------------------------------------
    if model.endswith(":free") and active_params is None:
        logger.debug("footprint: tier=unknown for :free model %s/%s", provider, model)
        return None

    # ------------------------------------------------------------------
    # Tier 3 — caller-supplied params (before any registry lookup)
    # ------------------------------------------------------------------
    if active_params is not None and total_params is not None:
        eco_prov = _infer_eco_provider(provider, model) or "openai"
        return _build_footprint(
            eco_provider=eco_prov,
            eco_model_name="__params__",  # not used; params override registry
            tokens_out=tokens_out,
            latency_s=latency_s,
            zone=zone,
            tier="params",
            estimate=False,
            proxy_model=None,
            active_params=active_params,
            total_params=total_params,
        )

    # ------------------------------------------------------------------
    # Tier 1 — exact registry match
    # ------------------------------------------------------------------
    exact = eco_models.find_model(provider=provider, model_name=model)
    if exact is not None:
        return _build_footprint(
            eco_provider=provider,
            eco_model_name=model,
            tokens_out=tokens_out,
            latency_s=latency_s,
            zone=zone,
            tier="exact",
            estimate=False,
            proxy_model=None,
        )

    # ------------------------------------------------------------------
    # Tier 2 — alias table
    # ------------------------------------------------------------------
    alias = _load_aliases().get((provider, model))
    if alias is not None:
        eco_prov, eco_model = alias
        result = _build_footprint(
            eco_provider=eco_prov,
            eco_model_name=eco_model,
            tokens_out=tokens_out,
            latency_s=latency_s,
            zone=zone,
            tier="aliased",
            estimate=False,
            proxy_model=None,
        )
        if result is not None:
            return result

    # ------------------------------------------------------------------
    # Tier 4 — similar (known provider family, borrow family default)
    # ------------------------------------------------------------------
    eco_family = _infer_eco_provider(provider, model)
    if eco_family is not None and eco_family in FAMILY_DEFAULT:
        default_eco_prov, default_eco_model = FAMILY_DEFAULT[eco_family]
        logger.warning(
            "footprint: tier=similar for %s/%s — borrowing %s/%s",
            provider, model, default_eco_prov, default_eco_model,
        )
        result = _build_footprint(
            eco_provider=default_eco_prov,
            eco_model_name=default_eco_model,
            tokens_out=tokens_out,
            latency_s=latency_s,
            zone=zone,
            tier="similar",
            estimate=True,
            proxy_model=f"{default_eco_prov}/{default_eco_model}",
        )
        if result is not None:
            return result

    # ------------------------------------------------------------------
    # Tier 5 — provider-default (unknown provider, conservative 8B bucket)
    # ------------------------------------------------------------------
    logger.warning(
        "footprint: tier=provider-default for unknown provider %s/%s", provider, model
    )
    return _build_footprint(
        eco_provider="openai",           # WOR mix + openai PUE/WUE as neutral defaults
        eco_model_name="__params__",
        tokens_out=tokens_out,
        latency_s=latency_s,
        zone=zone,
        tier="provider-default",
        estimate=True,
        proxy_model=PROVIDER_DEFAULT_PROXY,
        active_params=PROVIDER_DEFAULT_ACTIVE_PARAMS,
        total_params=PROVIDER_DEFAULT_TOTAL_PARAMS,
    )
