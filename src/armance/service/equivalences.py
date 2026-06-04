"""ADEME human-scale equivalences for footprint figures.

gCO2e -> phone charges / car-km ; water mL -> drinking glasses. All factors are
read from ``ademe_equivalences.yaml`` (sourced) -- never hardcoded here.

Layer rule: only ``armance.core`` imports allowed here.
"""
from __future__ import annotations

import dataclasses
import os
from functools import lru_cache

import yaml


@dataclasses.dataclass(frozen=True)
class Equivalences:
    phone_charges: float
    car_km: float
    water_glasses: float


@lru_cache(maxsize=1)
def _load_factors() -> dict[str, float]:
    path = os.path.join(os.path.dirname(__file__), "ademe_equivalences.yaml")
    with open(path) as fh:
        return yaml.safe_load(fh)


def humanise(gco2e: float, water_ml: float) -> Equivalences:
    f = _load_factors()
    return Equivalences(
        phone_charges=gco2e / f["phone_charge_gco2e"],
        car_km=gco2e / f["car_km_gco2e"],
        water_glasses=water_ml / f["water_glass_ml"],
    )
