"""Environmental footprint estimation for LLM requests.

Single entry point: ``estimate_footprint()``.
Wraps EcoLogits (MPL-2.0, genai-impact/ecologits) via a 6-tier resolution
chain.  Tiers 2–6 (alias, params, similar, provider-default, unknown) are
implemented in subsequent tasks (EI.2+).  This module covers tier 1 (exact
registry match).

EcoLogits is called as a pure function — no SDK monkey-patching.
The ``EcoLogits.init()`` zone override (EI.5) is deferred; zone is passed
explicitly per-call for now.

Layer rule: this module imports from ``armance.core`` only.  No client or
transport imports.
"""
from __future__ import annotations

import logging
from typing import Union

from ecologits.electricity_mix_repository import electricity_mixes
from ecologits.impacts.llm import compute_llm_impacts
from ecologits.model_repository import ParametersMoE, models
from ecologits.tracers.utils import PROVIDER_CONFIG_MAP
from ecologits.utils.range_value import RangeValue

from armance.core.models.footprint import Footprint

logger = logging.getLogger(__name__)

_ValueOrRange = Union[float, RangeValue]


def _mean(v: _ValueOrRange) -> float:
    """Collapse a RangeValue to its mean; pass through a plain float."""
    if isinstance(v, RangeValue):
        return (v.min + v.max) / 2
    return float(v)


def estimate_footprint(
    provider: str,
    model: str,
    tokens_out: int,
    latency_s: float,
    zone: str = "WOR",
) -> Footprint | None:
    """Estimate the environmental footprint of a single LLM response.

    Returns ``None`` (tier "unknown") when no registry match is found and no
    fallback tier applies.  Tiers 2–6 are not yet implemented.

    Args:
        provider: EcoLogits provider name (e.g. "anthropic", "openai").
        model: EcoLogits model name (exact registry key, e.g. "claude-sonnet-4-6").
        tokens_out: Number of output tokens in the response.
        latency_s: Wall-clock request latency in seconds.
        zone: ISO 3166-1 alpha-3 electricity-mix zone (default "WOR").
    """
    registry_entry = models.find_model(provider=provider, model_name=model)
    if registry_entry is None:
        logger.debug("footprint: no registry entry for %s/%s — returning None (tier=unknown)", provider, model)
        return None

    params = registry_entry.architecture.parameters
    if isinstance(params, ParametersMoE):
        p_active: _ValueOrRange = params.active
        p_total: _ValueOrRange = params.total
    else:
        p_active = p_total = params

    mix = electricity_mixes.find_electricity_mix(zone=zone)
    if mix is None:
        logger.warning("footprint: unknown electricity mix zone %r — returning None", zone)
        return None

    provider_cfg = PROVIDER_CONFIG_MAP.get(provider)
    if provider_cfg is None:
        datacenter_pue: _ValueOrRange = 1.2
        datacenter_wue: _ValueOrRange = 0.2
    else:
        datacenter_pue = provider_cfg.datacenter_pue
        datacenter_wue = provider_cfg.datacenter_wue

    deployment = registry_entry.deployment
    impacts = compute_llm_impacts(
        model_active_parameter_count=p_active,
        model_total_parameter_count=p_total,
        output_token_count=float(tokens_out),
        request_latency=latency_s,
        if_electricity_mix_adpe=mix.adpe,
        if_electricity_mix_pe=mix.pe,
        if_electricity_mix_gwp=mix.gwp,
        if_electricity_mix_wue=mix.wue,
        datacenter_pue=datacenter_pue,
        datacenter_wue=datacenter_wue,
        tps=deployment.tps if deployment else None,
        ttft=deployment.ttft if deployment else None,
    )

    energy_wh = _mean(impacts.energy.value) * 1_000       # kWh → Wh
    gco2e = _mean(impacts.gwp.value) * 1_000               # kgCO2eq → gCO2eq
    water_ml = _mean(impacts.wcf.value) * 1_000            # L → mL
    embodied_gco2e = _mean(impacts.embodied.gwp.value) * 1_000

    return Footprint(
        energy_wh=energy_wh,
        gco2e=gco2e,
        water_ml=water_ml,
        embodied_gco2e=embodied_gco2e,
        estimate=False,
        tier="exact",
        proxy_model=None,
        zone=zone,
    )
