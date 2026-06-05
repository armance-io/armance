from __future__ import annotations


class TestBoundedFootprint:
    def test_returns_non_none_range(self) -> None:
        from armance.service.footprint_bounds import bounded_footprint
        fp = bounded_footprint(tokens_out=300, latency_s=4.0, zone="WOR")
        assert fp is not None
        assert fp.tier == "bounded"
        assert fp.estimate is True
        assert fp.gco2e_min is not None and fp.gco2e_max is not None
        assert 0 < fp.gco2e_min < fp.gco2e_max
        # the scalar midpoint sits inside the interval
        assert fp.gco2e_min <= fp.gco2e <= fp.gco2e_max

    def test_fra_zone_lower_than_wor(self) -> None:
        from armance.service.footprint_bounds import bounded_footprint
        wor = bounded_footprint(tokens_out=300, latency_s=4.0, zone="WOR")
        fra = bounded_footprint(tokens_out=300, latency_s=4.0, zone="FRA")
        assert fra.gco2e_max < wor.gco2e_max  # France grid is cleaner

    def test_more_tokens_means_more_gco2e(self) -> None:
        from armance.service.footprint_bounds import bounded_footprint
        small = bounded_footprint(tokens_out=300, latency_s=4.0, zone="WOR")
        big = bounded_footprint(tokens_out=600, latency_s=4.0, zone="WOR")
        assert big.gco2e > small.gco2e
        assert big.gco2e_max > small.gco2e_max

    def test_water_bounds_ordered(self) -> None:
        from armance.service.footprint_bounds import bounded_footprint
        fp = bounded_footprint(tokens_out=300, latency_s=4.0, zone="WOR")
        assert fp.water_ml_min < fp.water_ml_max
        assert fp.water_ml_min <= fp.water_ml <= fp.water_ml_max
