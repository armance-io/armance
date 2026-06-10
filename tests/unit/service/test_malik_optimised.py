"""Task E2 — Malik orders recruitment models by carbon in optimised mode.

Targets the small in-file ordering helper ``_order_for_budget`` which, when
``budget_effort == "optimised"``, builds a ``gco2e_lookup`` closure over
``estimate_footprint`` and routes the candidate list through
``order_models_by_effort`` (greenest first). Other budgets leave the list
untouched.
"""
from __future__ import annotations

from types import SimpleNamespace

import armance.service.chat_handlers.malik as malik_mod
from armance.core.models.footprint import Footprint
from armance.providers.base import ModelSpec


def _fake_estimate(provider, model, tokens_out, latency_s, zone="WOR", **kw):
    """Deterministic, offline gCO2e by model id."""
    g = {"vendor/dirty": 30.0, "vendor/green": 0.5, "vendor/mid": 10.0}.get(model, 10.0)
    return Footprint(
        energy_wh=g,
        gco2e=g,
        water_ml=g,
        embodied_gco2e=0.0,
        estimate=False,
        tier="exact",
        proxy_model=None,
        zone=zone,
    )


def _cfg(budget: str, zone: str = "FRA") -> SimpleNamespace:
    return SimpleNamespace(
        budget_effort=budget,
        footprint=SimpleNamespace(electricity_mix_zone=zone),
    )


def _models() -> list[ModelSpec]:
    # Incoming order is dirtiest-first to prove the helper reorders.
    return [
        ModelSpec(id="vendor/dirty", provider="openrouter", tier="low"),
        ModelSpec(id="vendor/mid", provider="openrouter", tier="low"),
        ModelSpec(id="vendor/green", provider="openrouter", tier="low"),
    ]


class TestMalikCarbonOrdering:
    def test_optimised_orders_greenest_first(self, monkeypatch) -> None:
        monkeypatch.setattr(malik_mod, "estimate_footprint", _fake_estimate, raising=False)

        ordered = malik_mod._order_for_budget(_models(), "optimised", _cfg("optimised"))

        ids = [m.id for m in ordered]
        assert ids == ["vendor/green", "vendor/mid", "vendor/dirty"]

    def test_optimised_uses_configured_zone(self, monkeypatch) -> None:
        seen: list[str] = []

        def spy(provider, model, tokens_out, latency_s, zone="WOR", **kw):
            seen.append(zone)
            return _fake_estimate(provider, model, tokens_out, latency_s, zone=zone)

        monkeypatch.setattr(malik_mod, "estimate_footprint", spy, raising=False)

        malik_mod._order_for_budget(_models(), "optimised", _cfg("optimised", zone="FRA"))

        assert seen and all(z == "FRA" for z in seen)

    def test_non_optimised_budget_left_untouched(self, monkeypatch) -> None:
        def boom(*a, **k):  # pragma: no cover - must not be called
            raise AssertionError("estimate_footprint must not run for non-optimised")

        monkeypatch.setattr(malik_mod, "estimate_footprint", boom, raising=False)

        models = _models()
        ordered = malik_mod._order_for_budget(models, "low", _cfg("low"))

        assert [m.id for m in ordered] == [m.id for m in models]

    def test_footprint_none_sorts_last(self, monkeypatch) -> None:
        def maybe_none(provider, model, tokens_out, latency_s, zone="WOR", **kw):
            if model == "vendor/mid":
                return None  # defensive: unknown → sort LAST, never crash
            return _fake_estimate(provider, model, tokens_out, latency_s, zone=zone)

        monkeypatch.setattr(malik_mod, "estimate_footprint", maybe_none, raising=False)

        ordered = malik_mod._order_for_budget(_models(), "optimised", _cfg("optimised"))

        ids = [m.id for m in ordered]
        assert ids == ["vendor/green", "vendor/dirty", "vendor/mid"]


class TestOptimisedRecruitGuard:
    @staticmethod
    def _recruit(tmp_path, base_model: str):
        from armance.config import Config, ProviderConfig
        from armance.core.models.agent import Agent
        from armance.service.agents.recruiter_agent import RecruiterAgentService

        cfg = Config(
            providers=[ProviderConfig(name="openrouter")],
            default_provider="openrouter",
            default_model="openai/gpt-5.2",
            budget_effort="optimised",
        )
        malik = Agent(
            name="system-hr", domain="meta", character="balanced",
            provider="openrouter", model="openai/gpt-5.2",
            system_prompt="You are Malik.",
        )
        recruiter = RecruiterAgentService(malik, tmp_path, cfg)
        yaml_text = (
            "```yaml\n"
            "agents:\n"
            "  - name: Sarah\n"
            "    role: finance\n"
            "    persona: positivist\n"
            "    provider: openrouter\n"
            f"    model: {base_model}\n"
            "    system_prompt: You are Sarah.\n"
            "```\n"
        )
        return recruiter._parse_agents_yaml(yaml_text, "finance")

    def test_missing_boost_falls_back_to_default_model(self, tmp_path) -> None:
        """Optimised posture: a recruit entry without boost_model gets the
        user's flagship default as deterministic augment fallback."""
        agents = self._recruit(tmp_path, "google/gemma-2-9b-it:free")
        assert agents[0].boost_model == "openai/gpt-5.2"
        assert agents[0].boost_provider == "openrouter"

    def test_no_fallback_when_base_is_default(self, tmp_path) -> None:
        agents = self._recruit(tmp_path, "openai/gpt-5.2")
        assert agents[0].boost_model is None
