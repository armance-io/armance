from __future__ import annotations


class TestFootprintZones:
    def test_lists_common_zones_with_intensity(self) -> None:
        from armance.service.footprint_zones import list_zones
        zones = list_zones()
        codes = {z["code"] for z in zones}
        for c in ("WOR", "FRA", "USA", "DEU", "CHN"):
            assert c in codes
        # every row carries a positive carbon intensity
        for z in zones:
            assert isinstance(z["gco2e_per_kwh"], float)
            assert z["gco2e_per_kwh"] > 0

    def test_world_average_listed_first(self) -> None:
        from armance.service.footprint_zones import list_zones
        assert list_zones()[0]["code"] == "WOR"

    def test_france_cleaner_than_world(self) -> None:
        from armance.service.footprint_zones import list_zones
        by = {z["code"]: z["gco2e_per_kwh"] for z in list_zones()}
        assert by["FRA"] < by["WOR"]  # nuclear-heavy grid

    def test_is_valid_zone(self) -> None:
        from armance.service.footprint_zones import is_valid_zone
        assert is_valid_zone("FRA") is True
        assert is_valid_zone("ZZZ") is False
