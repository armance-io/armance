"""Dynamic best/worst-case footprint bounding — the final resolution tier.

Used only when no registry/alias/param/family tier resolved a model (e.g. a
':free' OpenRouter community model with zero metadata). Rather than fabricating
a single number or showing nothing, we bound the request between two physically
defensible extremes from the literature and convert to gCO2e via the zone's
grid carbon factor. Always returns a non-None Footprint with estimate=True.

Energy bounds (per request), from Jegham et al. 2025, "How Hungry is AI?"
(arXiv:2505.09598) and the ecoconception-IA matrix:
  - best  : nano model (~1-3B) on H100, optimal batch  ~= 0.1 Wh/req
  - worst : dense/MoE >400B on A100, low batch          ~= 33  Wh/req
Scaled by output tokens as a compute proxy.

Layer rule: only ``armance.core`` imports allowed here.

EcoLogits electricity-mix attributes (verified at import time):
  - ``gwp``  : kgCO2e per kWh (FRA ≈ 0.044, WOR ≈ 0.473)
  - ``wue``  : L water per kWh (FRA ≈ 3.67, WOR ≈ 3.91)
"""
from __future__ import annotations

import logging

from ecologits.electricity_mix_repository import electricity_mixes

from armance.core.models.footprint import Footprint

logger = logging.getLogger(__name__)

# Sourced energy envelope (Wh per request) — see module docstring.
_BEST_WH_PER_REQ = 0.1
_WORST_WH_PER_REQ = 33.0
# Reference output-token count the envelope was measured against (Jegham long case).
_REF_TOKENS_OUT = 1500
# Embodied-share fraction folded into the carbon figure (conservative, usage-led).
_EMBODIED_SHARE = 0.10
# WOR world-average (EcoLogits bundled data); used only when a zone code is unknown.
_UNKNOWN_ZONE_GWP_FALLBACK = 0.473
# WOR world-average WUE (EcoLogits); used only when a zone has no WUE.
_WUE_FALLBACK = 3.91


def bounded_footprint(tokens_out: int, latency_s: float, zone: str) -> Footprint:
    """Return a best/worst-case Footprint for a fully unknown model."""
    # latency_s is part of the chain's call signature but unused here: the bounding
    # envelope is token-scaled, not latency-scaled (HTTP latency is an unreliable
    # compute proxy for a fully-unknown model). Kept for signature parity.
    logger.debug(
        "bounded fp: tokens=%d latency=%.2fs zone=%s", tokens_out, latency_s, zone
    )
    mix = electricity_mixes.find_electricity_mix(zone=zone)
    # Attribute names verified via probe: mix.gwp (kgCO2e/kWh), mix.wue (L/kWh).
    gwp_per_kwh = getattr(mix, "gwp", None) if mix is not None else None
    gwp_per_kwh = _UNKNOWN_ZONE_GWP_FALLBACK if gwp_per_kwh is None else gwp_per_kwh
    wue = getattr(mix, "wue", None) if mix is not None else None
    wue = _WUE_FALLBACK if wue is None else wue

    # Token scaling: a short reply costs proportionally less than the reference.
    scale = max(tokens_out, 1) / _REF_TOKENS_OUT
    e_min_wh = _BEST_WH_PER_REQ * scale
    e_max_wh = _WORST_WH_PER_REQ * scale
    e_mid_wh = (e_min_wh + e_max_wh) / 2

    def _g(wh: float) -> float:
        kwh = wh / 1_000
        return kwh * gwp_per_kwh * 1_000 * (1 + _EMBODIED_SHARE)  # gCO2e

    def _w(wh: float) -> float:
        kwh = wh / 1_000
        return kwh * wue * 1_000  # mL (L -> mL)

    return Footprint(
        energy_wh=e_mid_wh,
        gco2e=_g(e_mid_wh),
        water_ml=_w(e_mid_wh),
        # _g already folds in embodied; pull the embodied portion back out: total * S/(1+S).
        embodied_gco2e=_g(e_mid_wh) * _EMBODIED_SHARE / (1 + _EMBODIED_SHARE),
        estimate=True,
        tier="bounded",
        proxy_model=None,
        zone=zone,
        energy_wh_min=e_min_wh,
        energy_wh_max=e_max_wh,
        gco2e_min=_g(e_min_wh),
        gco2e_max=_g(e_max_wh),
        water_ml_min=_w(e_min_wh),
        water_ml_max=_w(e_max_wh),
    )
