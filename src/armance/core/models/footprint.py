from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Footprint:
    """Environmental footprint of a single LLM request.

    Units: energy_wh (Wh), gco2e (gCO2eq), water_ml (mL), embodied_gco2e (gCO2eq).
    All values are the mean of EcoLogits' confidence interval when a RangeValue
    is returned (MoE models and ranged datacenter PUE/WUE).

    ``estimate`` is True only for tiers 4–5 (similar-model / provider-default
    fallback).  EcoLogits' inherent RangeValue uncertainty does NOT set this flag.
    ``proxy_model`` names the borrowed registry entry for tiers 4–5; None otherwise.
    ``zone`` records the electricity-mix zone used (EcoLogits ISO 3166-1 alpha-3).
    """

    energy_wh: float
    gco2e: float
    water_ml: float
    embodied_gco2e: float
    estimate: bool
    tier: str
    proxy_model: str | None
    zone: str
