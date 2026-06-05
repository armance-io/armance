from __future__ import annotations


class TestCarbonOrdering:
    def test_optimised_orders_by_gco2e_ascending(self) -> None:
        from armance.providers.model_discovery import order_models_by_effort
        models = [
            {"id": "vendor/big-model", "cost": 0.0},
            {"id": "vendor/tiny-model", "cost": 5.0},
        ]
        gco2e = {"vendor/big-model": 30.0, "vendor/tiny-model": 0.3}
        ordered = order_models_by_effort(
            models, effort="optimised", gco2e_lookup=lambda m: gco2e[m["id"]],
        )
        assert ordered[0]["id"] == "vendor/tiny-model"

    def test_free_first_unchanged(self) -> None:
        from armance.providers.model_discovery import order_models_by_effort
        models = [{"id": "a", "cost": 0.0}, {"id": "b", "cost": 5.0}]
        ordered = order_models_by_effort(
            models, effort="free-first", gco2e_lookup=lambda m: 0.0,
        )
        assert [m["id"] for m in ordered] == ["a", "b"]  # original order preserved

    def test_optimised_is_stable_for_equal_gco2e(self) -> None:
        from armance.providers.model_discovery import order_models_by_effort
        models = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        ordered = order_models_by_effort(
            models, effort="optimised", gco2e_lookup=lambda m: 1.0,
        )
        assert [m["id"] for m in ordered] == ["a", "b", "c"]  # stable sort
