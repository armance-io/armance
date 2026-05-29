"""Environmental footprint estimation for LLM requests.

Single entry point: ``estimate_footprint()``.
Wraps EcoLogits (MPL-2.0, genai-impact/ecologits) via a 6-tier resolution
chain.  No SDK monkey-patching — only the pure ``compute_llm_impacts``
function is called.

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
_KNOWN_ECO_PROVIDERS = frozenset(PROVIDER_CONFIG_MAP.keys())

# Tier-4: per-family default model (small, representative, verified in 0.10.1).
_FAMILY_DEFAULT: dict[str, tuple[str, str]] = {
    "anthropic":      ("anthropic",   "claude-haiku-4-5"),
    "openai":         ("openai",      "gpt-4o-mini"),
    "google_genai":   ("google_genai","gemini-2.0-flash-lite"),
    "mistralai":      ("mistralai",   "ministral-8b-2512"),
    "cohere":         ("cohere",      "c4ai-aya-expanse-8b"),
    "huggingface_hub":("huggingface_hub", "databricks/dolly-v2-7b"),
}

# Tier-5: conservative bucket — generic dense 8B, WOR zone, generic PUE/WUE.
_PROVIDER_DEFAULT_ACTIVE_PARAMS: float = 8.0
_PROVIDER_DEFAULT_TOTAL_PARAMS: float = 8.0
_PROVIDER_DEFAULT_PROXY = "generic-dense-8b"


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

def _mean(v: _ValueOrRange) -> float:
    if isinstance(v, RangeValue):
        return (v.min + v.max) / 2
    return float(v)


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

    return Footprint(
        energy_wh=_mean(impacts.energy.value) * 1_000,
        gco2e=_mean(impacts.gwp.value) * 1_000,
        water_ml=_mean(impacts.wcf.value) * 1_000,
        embodied_gco2e=_mean(impacts.embodied.gwp.value) * 1_000,
        estimate=estimate,
        tier=tier,
        proxy_model=proxy_model,
        zone=zone,
    )


def _infer_eco_provider(armance_provider: str, armance_model: str) -> str | None:
    """Guess the EcoLogits provider from armance provider + model vendor prefix.

    OpenRouter ids are "vendor/model"; the vendor maps to an EcoLogits provider.
    """
    if armance_provider in _KNOWN_ECO_PROVIDERS:
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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
    aliases = _load_aliases()
    alias = aliases.get((provider, model))
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
    if eco_family is not None and eco_family in _FAMILY_DEFAULT:
        default_eco_prov, default_eco_model = _FAMILY_DEFAULT[eco_family]
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
        proxy_model=_PROVIDER_DEFAULT_PROXY,
        active_params=_PROVIDER_DEFAULT_ACTIVE_PARAMS,
        total_params=_PROVIDER_DEFAULT_TOTAL_PARAMS,
    )
