"""EI.2 — alias + param + similar + provider-default + unknown tiers.

One representative model id per tier 2–6 (spec requirement).

Tier boundaries:
  2 aliased      — id is in env_model_aliases.yaml; exact registry hit after mapping.
  3 params       — active_params/total_params supplied directly via kwarg seam.
  4 similar      — provider family known in EcoLogits but model not in alias table;
                   borrows the family's default registry model, estimate=True.
  5 provider-default — armance router provider (e.g. "custom-openai") unknown to
                   EcoLogits; uses conservative 8B dense bucket, estimate=True.
  6 unknown / None — id ends with ':free' and no params supplied; never fabricate.

Tier 1 (exact) is covered in test_footprint_ei1.py.
"""
from __future__ import annotations

import pytest

from armance.core.models.footprint import Footprint
from armance.service.footprint import estimate_footprint


# ---------------------------------------------------------------------------
# Tier 2 — aliased
# ---------------------------------------------------------------------------

class TestTier2Aliased:
    """OpenRouter-style ids (anthropic/model-name) resolved via alias table."""

    def test_openrouter_claude_sonnet_resolves(self) -> None:
        result = estimate_footprint(
            provider="openrouter",
            model="anthropic/claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        assert result.tier == "aliased"
        assert result.estimate is False
        assert result.gco2e > 0.0

    def test_openrouter_gemini_flash_resolves(self) -> None:
        result = estimate_footprint(
            provider="openrouter",
            model="google/gemini-2.0-flash",
            tokens_out=300,
            latency_s=2.0,
            zone="WOR",
        )
        assert result is not None
        assert result.tier == "aliased"
        assert result.estimate is False

    def test_openrouter_gpt4o_resolves(self) -> None:
        result = estimate_footprint(
            provider="openrouter",
            model="openai/gpt-4o",
            tokens_out=400,
            latency_s=3.0,
            zone="WOR",
        )
        assert result is not None
        assert result.tier == "aliased"
        assert result.estimate is False

    def test_aliased_no_proxy_model(self) -> None:
        result = estimate_footprint(
            provider="openrouter",
            model="anthropic/claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        assert result.proxy_model is None

    def test_aliased_zone_recorded(self) -> None:
        result = estimate_footprint(
            provider="openrouter",
            model="anthropic/claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="FRA",
        )
        assert result is not None
        assert result.zone == "FRA"


# ---------------------------------------------------------------------------
# Tier 3 — param-count seam (active_params / total_params supplied)
# ---------------------------------------------------------------------------

class TestTier3Params:
    """Caller supplies param counts directly; no registry lookup needed."""

    def test_params_tier_returns_footprint(self) -> None:
        result = estimate_footprint(
            provider="openrouter",
            model="some-vendor/unknown-dense-7b",
            tokens_out=500,
            latency_s=3.0,
            zone="WOR",
            active_params=7.0,
            total_params=7.0,
        )
        assert result is not None
        assert result.tier == "params"
        assert result.estimate is False
        assert result.gco2e > 0.0

    def test_params_tier_no_proxy_model(self) -> None:
        result = estimate_footprint(
            provider="openrouter",
            model="some-vendor/unknown-dense-7b",
            tokens_out=500,
            latency_s=3.0,
            zone="WOR",
            active_params=7.0,
            total_params=7.0,
        )
        assert result is not None
        assert result.proxy_model is None

    def test_params_moe_model(self) -> None:
        result = estimate_footprint(
            provider="openrouter",
            model="some-vendor/unknown-moe-70b",
            tokens_out=800,
            latency_s=5.0,
            zone="WOR",
            active_params=13.0,
            total_params=70.0,
        )
        assert result is not None
        assert result.tier == "params"
        assert result.gco2e > 0.0


# ---------------------------------------------------------------------------
# Tier 4 — similar (known provider family, model not in alias table)
# ---------------------------------------------------------------------------

class TestTier4Similar:
    """Unknown model under a provider family EcoLogits knows → borrows family default."""

    def test_unknown_anthropic_model_is_similar(self) -> None:
        result = estimate_footprint(
            provider="anthropic",
            model="claude-totally-unknown-xyz",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        assert result.tier == "similar"
        assert result.estimate is True
        assert result.proxy_model is not None
        assert result.gco2e > 0.0

    def test_unknown_openai_model_is_similar(self) -> None:
        result = estimate_footprint(
            provider="openai",
            model="gpt-99-turbo-fantasy",
            tokens_out=400,
            latency_s=2.0,
            zone="WOR",
        )
        assert result is not None
        assert result.tier == "similar"
        assert result.estimate is True
        assert result.proxy_model is not None

    def test_similar_positive_energy(self) -> None:
        result = estimate_footprint(
            provider="anthropic",
            model="claude-totally-unknown-xyz",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is not None
        assert result.energy_wh > 0.0
        assert result.water_ml > 0.0


# ---------------------------------------------------------------------------
# Tier 5 — provider-default (armance router provider unknown to EcoLogits)
# ---------------------------------------------------------------------------

class TestTier5ProviderDefault:
    """custom-openai / unknown router → conservative 8B dense bucket."""

    def test_custom_openai_provider_default(self) -> None:
        result = estimate_footprint(
            provider="custom-openai",
            model="my-private-llm",
            tokens_out=500,
            latency_s=3.0,
            zone="WOR",
        )
        assert result is not None
        assert result.tier == "provider-default"
        assert result.estimate is True
        assert result.proxy_model is not None
        assert result.gco2e > 0.0

    def test_provider_default_positive_values(self) -> None:
        result = estimate_footprint(
            provider="totally-unknown-provider",
            model="some-model",
            tokens_out=300,
            latency_s=2.0,
            zone="WOR",
        )
        assert result is not None
        assert result.tier == "provider-default"
        assert result.estimate is True
        assert result.energy_wh > 0.0
        assert result.water_ml > 0.0


# ---------------------------------------------------------------------------
# Tier 6 — unknown / None (never fabricate)
# ---------------------------------------------------------------------------

class TestTier6Unknown:
    """':free' id with no params → None; never return a fabricated figure."""

    def test_free_model_no_params_returns_none(self) -> None:
        result = estimate_footprint(
            provider="openrouter",
            model="some-vendor/mystery-model:free",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        assert result is None

    def test_free_model_with_params_bypasses_unknown(self) -> None:
        # Supplying params → tier 3, not tier 6
        result = estimate_footprint(
            provider="openrouter",
            model="some-vendor/mystery-model:free",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
            active_params=7.0,
            total_params=7.0,
        )
        assert result is not None
        assert result.tier == "params"


# ---------------------------------------------------------------------------
# Cross-tier: EI.1 test updated — unknown model of known provider → tier 4
# ---------------------------------------------------------------------------

class TestEI1UpdatedBehavior:
    """EI.1 had test_unknown_model_returns_none with provider='anthropic'.
    After EI.2, anthropic is a known family → tier 4 (similar), not None.
    Tier-6/None requires a ':free' suffix or a fully unknown provider.
    """

    def test_unknown_anthropic_now_tier_similar_not_none(self) -> None:
        result = estimate_footprint(
            provider="anthropic",
            model="claude-totally-unknown-xyz",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        # Must not return None — that would mean silently skipping a known family.
        assert result is not None
        assert result.estimate is True
