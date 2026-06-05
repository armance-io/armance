from __future__ import annotations


class TestEquivalences:
    def test_one_phone_charge(self) -> None:
        from armance.service.equivalences import humanise
        eq = humanise(gco2e=8.3, water_ml=0.0)
        assert 0.9 <= eq.phone_charges <= 1.1

    def test_one_water_glass(self) -> None:
        from armance.service.equivalences import humanise
        eq = humanise(gco2e=0.0, water_ml=250.0)
        assert 0.9 <= eq.water_glasses <= 1.1

    def test_car_km_present(self) -> None:
        from armance.service.equivalences import humanise
        eq = humanise(gco2e=218.0, water_ml=0.0)
        assert 0.9 <= eq.car_km <= 1.1

    def test_constants_come_from_yaml(self) -> None:
        # Changing the YAML must change the result (no hardcode).
        from armance.service import equivalences
        equivalences._load_factors.cache_clear()
        eq = equivalences.humanise(gco2e=16.6, water_ml=0.0)
        assert 1.9 <= eq.phone_charges <= 2.1  # 16.6 / 8.3 ≈ 2
