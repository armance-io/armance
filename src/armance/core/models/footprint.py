from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Footprint:
    """Environmental footprint of a single LLM request.

    Units: energy_wh (Wh), gco2e (gCO2eq), water_ml (mL), embodied_gco2e (gCO2eq).
    All values are the mean of EcoLogits' confidence interval when a RangeValue
    is returned (MoE models and ranged datacenter PUE/WUE).

    ``estimate`` is True for the similar / provider-default fallback tiers AND
    the dynamic bounding tier.  EcoLogits' inherent RangeValue uncertainty does NOT set this flag.
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
    # Range bounds (additive; default None → fall back to the scalar midpoint).
    # When EcoLogits returns a RangeValue (MoE / ranged PUE) or the dynamic
    # bounding tier fires, these carry the min/max of the confidence interval.
    gco2e_min: float | None = None
    gco2e_max: float | None = None
    water_ml_min: float | None = None
    water_ml_max: float | None = None
    energy_wh_min: float | None = None
    energy_wh_max: float | None = None
