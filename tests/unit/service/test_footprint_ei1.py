"""EI.1 — Footprint model + estimate_footprint exact-tier tests.

Note: the epic spec mentions "claude-3-5-sonnet" as an example; that id is
not in the EcoLogits 0.10.1 registry.  We use "claude-sonnet-4-6" which is
verified present and returns tier="exact".
"""
from __future__ import annotations

import pytest

from armance.core.models.footprint import Footprint
from armance.service.footprint import estimate_footprint


class TestFootprintModel:
    def test_footprint_is_dataclass(self) -> None:
        f = Footprint(
            energy_wh=1.0,
            gco2e=0.5,
            water_ml=2.0,
            embodied_gco2e=0.1,
            estimate=False,
            tier="exact",
            proxy_model=None,
            zone="WOR",
        )
        assert f.energy_wh == 1.0
        assert f.gco2e == 0.5
        assert f.estimate is False
        assert f.tier == "exact"
        assert f.proxy_model is None
        assert f.zone == "WOR"

    def test_footprint_fields_present(self) -> None:
        import dataclasses
        fields = {f.name for f in dataclasses.fields(Footprint)}
        assert "energy_wh" in fields
        assert "gco2e" in fields
        assert "water_ml" in fields
        assert "embodied_gco2e" in fields
        assert "estimate" in fields
        assert "tier" in fields
        assert "proxy_model" in fields
        assert "zone" in fields


class TestEstimateFootprintExactTier:
    """EI.1: exact-tier match via EcoLogits registry."""

    def test_exact_tier_returns_footprint(self) -> None:
        result = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        assert isinstance(result, Footprint)

    def test_exact_tier_flag(self) -> None:
        result = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        assert result.tier == "exact"
        assert result.estimate is False

    def test_exact_tier_positive_gco2e(self) -> None:
        result = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        assert result.gco2e > 0.0

    def test_exact_tier_positive_energy_wh(self) -> None:
        result = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        assert result.energy_wh > 0.0

    def test_exact_tier_positive_water_ml(self) -> None:
        result = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        assert result.water_ml > 0.0

    def test_exact_tier_zone_recorded(self) -> None:
        result = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        assert result.zone == "WOR"

    def test_exact_tier_no_proxy_model(self) -> None:
        result = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        assert result.proxy_model is None

    def test_free_model_returns_bounded_not_none(self) -> None:
        # NEW contract: :free with no params no longer returns None; it returns
        # a dynamic-bounded estimate so the UI never shows "🌱?".
        from armance.service.footprint import estimate_footprint
        fp = estimate_footprint(
            "openrouter", "some/unknown-model:free",
            tokens_out=300, latency_s=4.0, zone="WOR",
        )
        assert fp is not None
        assert fp.tier == "bounded"
        assert fp.estimate is True
        assert fp.gco2e_min is not None and fp.gco2e_max is not None

    def test_units_are_wh_g_ml(self) -> None:
        """energy in Wh (not kWh), CO2 in g (not kg), water in mL (not L)."""
        result = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        # Sanity: a 600-token response should be well under 1 kWh, but in Wh
        # it should be positive and non-trivial (> 0.1 Wh is unrealistic; just > 0)
        assert 0 < result.energy_wh < 10_000
        # gCO2e: not negative, and sanity < 10 000 g for a normal request
        assert 0 < result.gco2e < 10_000
        # water_ml: positive
        assert result.water_ml > 0

    @pytest.mark.parametrize("tokens_out", [100, 600, 2000])
    def test_scales_with_tokens(self, tokens_out: int) -> None:
        r = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=tokens_out,
            latency_s=4.0,
            zone="WOR",
        )
        assert r is not None
        assert r.gco2e > 0.0


class TestFootprintRangeFields:
    def test_min_max_fields_default_to_none(self) -> None:
        from armance.core.models.footprint import Footprint
        fp = Footprint(
            energy_wh=1.0, gco2e=2.0, water_ml=3.0, embodied_gco2e=0.5,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        assert fp.gco2e_min is None
        assert fp.gco2e_max is None
        assert fp.water_ml_min is None
        assert fp.water_ml_max is None
        assert fp.energy_wh_min is None
        assert fp.energy_wh_max is None

    def test_min_max_fields_accepted(self) -> None:
        from armance.core.models.footprint import Footprint
        fp = Footprint(
            energy_wh=1.0, gco2e=2.0, water_ml=3.0, embodied_gco2e=0.5,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
            gco2e_min=1.5, gco2e_max=2.5,
        )
        assert fp.gco2e_min == 1.5 and fp.gco2e_max == 2.5
