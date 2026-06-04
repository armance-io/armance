"""EcoLogits resolution primitives for the footprint feature.

Holds the alias table, provider-family maps, and the single ``compute_llm_impacts``
wrapper.  Split out of ``footprint.py`` to keep that file under the 300-LOC cap;
``footprint.py`` owns the public ``estimate_footprint`` 6-tier chain and imports
the primitives below.

Layer rule: only ``armance.core`` imports allowed here.  No client/transport.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Union

import yaml
from ecologits.electricity_mix_repository import electricity_mixes
from ecologits.impacts.llm import compute_llm_impacts
from ecologits.model_repository import ParametersMoE, models as eco_models
from ecologits.tracers.utils import PROVIDER_CONFIG_MAP
from ecologits.utils.range_value import RangeValue

from armance.core.models.footprint import Footprint

logger = logging.getLogger(__name__)

_ValueOrRange = Union[float, RangeValue]

# ---------------------------------------------------------------------------
# EcoLogits provider families recognised by the PROVIDER_CONFIG_MAP.
# Used for tier-4 (similar) detection.
# ---------------------------------------------------------------------------
KNOWN_ECO_PROVIDERS = frozenset(PROVIDER_CONFIG_MAP.keys())

# Tier-4: per-family default model (small, representative, verified in 0.10.1).
FAMILY_DEFAULT: dict[str, tuple[str, str]] = {
    "anthropic":      ("anthropic",   "claude-haiku-4-5"),
    "openai":         ("openai",      "gpt-4o-mini"),
    "google_genai":   ("google_genai","gemini-2.0-flash-lite"),
    "mistralai":      ("mistralai",   "ministral-8b-2512"),
    "cohere":         ("cohere",      "c4ai-aya-expanse-8b"),
    "huggingface_hub":("huggingface_hub", "databricks/dolly-v2-7b"),
}

# Tier-5: conservative bucket — generic dense 8B, WOR zone, generic PUE/WUE.
PROVIDER_DEFAULT_ACTIVE_PARAMS: float = 8.0
PROVIDER_DEFAULT_TOTAL_PARAMS: float = 8.0
PROVIDER_DEFAULT_PROXY = "generic-dense-8b"


# ---------------------------------------------------------------------------
# Alias table
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_aliases() -> dict[tuple[str, str], tuple[str, str]]:
    """Return {(armance_provider, armance_model): (eco_provider, eco_model)}."""
    yaml_path = os.path.join(os.path.dirname(__file__), "env_model_aliases.yaml")
    with open(yaml_path) as fh:
        entries = yaml.safe_load(fh)
    result: dict[tuple[str, str], tuple[str, str]] = {}
    for e in entries:
        key = (e["armance_provider"], e["armance_model"])
        result[key] = (e["ecologits_provider"], e["ecologits_model"])
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bounds(v: _ValueOrRange) -> tuple[float, float, float]:
    """Return (min, mid, max). Scalars collapse to three equal values."""
    if isinstance(v, RangeValue):
        return (float(v.min), (v.min + v.max) / 2, float(v.max))
    f = float(v)
    return (f, f, f)


def _build_footprint(
    eco_provider: str,
    eco_model_name: str,
    tokens_out: int,
    latency_s: float,
    zone: str,
    tier: str,
    estimate: bool,
    proxy_model: str | None,
    active_params: float | None = None,
    total_params: float | None = None,
) -> Footprint | None:
    """Run compute_llm_impacts and return a Footprint.  Returns None on mix miss."""
    registry_entry = eco_models.find_model(
        provider=eco_provider, model_name=eco_model_name
    )

    if active_params is not None and total_params is not None:
        p_active: _ValueOrRange = active_params
        p_total: _ValueOrRange = total_params
        deployment_tps = None
        deployment_ttft = None
    elif registry_entry is not None:
        params = registry_entry.architecture.parameters
        if isinstance(params, ParametersMoE):
            p_active = params.active
            p_total = params.total
        else:
            p_active = p_total = params
        dep = registry_entry.deployment
        deployment_tps = dep.tps if dep else None
        deployment_ttft = dep.ttft if dep else None
    else:
        logger.debug("footprint: registry miss for %s/%s in _build_footprint", eco_provider, eco_model_name)
        return None

    mix = electricity_mixes.find_electricity_mix(zone=zone)
    if mix is None:
        logger.warning("footprint: unknown electricity mix zone %r", zone)
        return None

    provider_cfg = PROVIDER_CONFIG_MAP.get(eco_provider)
    if provider_cfg is not None:
        datacenter_pue: _ValueOrRange = provider_cfg.datacenter_pue
        datacenter_wue: _ValueOrRange = provider_cfg.datacenter_wue
    else:
        datacenter_pue = 1.2
        datacenter_wue = 0.2

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
        tps=deployment_tps if active_params is None else None,
        ttft=deployment_ttft if active_params is None else None,
    )

    e_min, e_mid, e_max = _bounds(impacts.energy.value)
    g_min, g_mid, g_max = _bounds(impacts.gwp.value)
    w_min, w_mid, w_max = _bounds(impacts.wcf.value)
    emb_mid = _bounds(impacts.embodied.gwp.value)[1]

    return Footprint(
        energy_wh=e_mid * 1_000,
        gco2e=g_mid * 1_000,
        water_ml=w_mid * 1_000,
        embodied_gco2e=emb_mid * 1_000,
        estimate=estimate,
        tier=tier,
        proxy_model=proxy_model,
        zone=zone,
        energy_wh_min=e_min * 1_000, energy_wh_max=e_max * 1_000,
        gco2e_min=g_min * 1_000, gco2e_max=g_max * 1_000,
        water_ml_min=w_min * 1_000, water_ml_max=w_max * 1_000,
    )


def _infer_eco_provider(armance_provider: str, armance_model: str) -> str | None:
    """Guess the EcoLogits provider from armance provider + model vendor prefix.

    OpenRouter ids are "vendor/model"; the vendor maps to an EcoLogits provider.
    """
    if armance_provider in KNOWN_ECO_PROVIDERS:
        return armance_provider
    if armance_provider in ("gemini",):
        return "google_genai"
    if armance_provider == "openrouter":
        vendor = armance_model.split("/")[0].lower() if "/" in armance_model else ""
        _vendor_map = {
            "anthropic":  "anthropic",
            "openai":     "openai",
            "google":     "google_genai",
            "mistralai":  "mistralai",
            "cohere":     "cohere",
        }
        return _vendor_map.get(vendor)
    return None
