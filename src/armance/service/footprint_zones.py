"""Available EcoLogits electricity-mix zones for the footprint feature.

Lets the user pick the country/zone whose grid carbon intensity scales their
estimated footprint. Codes are ISO 3166-1 alpha-3 (plus the synthetic ``WOR``
world-average). Carbon intensity (gCO2e/kWh) is surfaced so the UI can sort and
explain the choice. Pure read of the embedded EcoLogits repository — offline.

Layer rule: imports ``armance.core`` and EcoLogits only.
"""
from __future__ import annotations

from functools import lru_cache

from ecologits.electricity_mix_repository import electricity_mixes


@lru_cache(maxsize=1)
def list_zones() -> list[dict[str, float | str]]:
    """Return [{code, gco2e_per_kwh}], sorted with WOR first then by code.

    ``gco2e_per_kwh`` is the zone's grid carbon intensity (the EcoLogits ``gwp``
    factor, kgCO2e/kWh, surfaced as gCO2e/kWh for readability).
    """
    seen: dict[str, float] = {}
    for mix in electricity_mixes.list_electricity_mixes():
        # gwp is kgCO2e per kWh; expose grams for a friendlier scale.
        seen.setdefault(mix.zone, round(float(mix.gwp) * 1000, 1))
    rows = [{"code": code, "gco2e_per_kwh": g} for code, g in seen.items()]
    rows.sort(key=lambda r: (r["code"] != "WOR", r["code"]))
    return rows


def is_valid_zone(code: str) -> bool:
    """True when *code* is a known electricity-mix zone."""
    return any(z["code"] == code for z in list_zones())
