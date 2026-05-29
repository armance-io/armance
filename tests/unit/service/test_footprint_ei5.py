"""EI.5 — electricity_mix_zone config field honoured.

Spec: with electricity_mix_zone: FRA, same request yields lower gco2e than WOR.
FRA grid is much cleaner (gwp 0.044 vs 0.473 kgCO2eq/kWh).

Tests:
  - FootprintConfig model exists on Config.
  - default zone is WOR.
  - FRA zone produces lower gco2e than WOR for identical request.
  - call_with_ledger reads zone from _CURRENT_CONFIG.
  - zone="WOR" used when config has no footprint section (backward compat).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from armance.config import Config
from armance.service.footprint import estimate_footprint


# ---------------------------------------------------------------------------
# Config model
# ---------------------------------------------------------------------------

class TestFootprintConfig:
    def test_config_has_footprint_section(self) -> None:
        cfg = Config()
        assert hasattr(cfg, "footprint")

    def test_default_zone_is_wor(self) -> None:
        cfg = Config()
        assert cfg.footprint.electricity_mix_zone == "WOR"

    def test_default_enabled_true(self) -> None:
        cfg = Config()
        assert cfg.footprint.enabled is True

    def test_zone_set_to_fra(self) -> None:
        from armance.config import FootprintConfig
        cfg = Config(footprint=FootprintConfig(electricity_mix_zone="FRA"))
        assert cfg.footprint.electricity_mix_zone == "FRA"

    def test_config_yaml_roundtrip(self) -> None:
        """FootprintConfig survives pydantic model_dump / model_validate."""
        cfg = Config()
        d = cfg.model_dump()
        cfg2 = Config.model_validate(d)
        assert cfg2.footprint.electricity_mix_zone == "WOR"


# ---------------------------------------------------------------------------
# Zone influences gco2e (the core assertion of EI.5)
# ---------------------------------------------------------------------------

class TestZoneInfluencesGco2e:
    def test_fra_lower_gco2e_than_wor(self) -> None:
        wor = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="WOR",
        )
        fra = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="FRA",
        )
        assert wor is not None
        assert fra is not None
        assert fra.gco2e < wor.gco2e

    def test_fra_zone_recorded_on_footprint(self) -> None:
        result = estimate_footprint(
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_out=600,
            latency_s=4.0,
            zone="FRA",
        )
        assert result is not None
        assert result.zone == "FRA"


# ---------------------------------------------------------------------------
# call_with_ledger reads zone from _CURRENT_CONFIG
# ---------------------------------------------------------------------------

class TestCallWithLedgerZone:
    @pytest.mark.asyncio
    async def test_zone_from_config_used(self) -> None:
        from armance.core.protocols.llm import LLMResponse
        from armance.service.llm_service import TokenLedger, call_with_ledger, set_current_config
        from armance.config import Config
        from armance.config import FootprintConfig

        resp = LLMResponse(
            text="hi", tokens_in=100, tokens_out=600,
            finish_reason="stop", cost_usd=0.01,
        )
        client_mock = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock()
        ledger = TokenLedger()

        # Set config with FRA zone
        cfg = Config(footprint=FootprintConfig(electricity_mix_zone="FRA"))
        set_current_config(cfg)

        with patch("armance.service.llm_service.complete_with_continuation", return_value=resp):
            await call_with_ledger(
                client_mock, "alice",
                [{"role": "user", "content": "hi"}],
                "claude-sonnet-4-6",
                ledger=ledger,
                provider="anthropic",
            )

        snap = ledger.snapshot()
        # FRA should produce positive but lower gco2e than WOR
        assert snap["total"]["gco2e"] > 0.0
        # Verify zone recorded in entry
        assert ledger.entries[0].footprint is not None
        assert ledger.entries[0].footprint.zone == "FRA"

    @pytest.mark.asyncio
    async def test_no_config_falls_back_to_wor(self) -> None:
        from armance.core.protocols.llm import LLMResponse
        from armance.service import llm_service
        from armance.service.llm_service import TokenLedger, call_with_ledger

        resp = LLMResponse(
            text="hi", tokens_in=100, tokens_out=600,
            finish_reason="stop", cost_usd=0.01,
        )
        client_mock = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock()
        ledger = TokenLedger()

        # Temporarily clear config
        old = llm_service._CURRENT_CONFIG
        llm_service._CURRENT_CONFIG = None
        try:
            with patch("armance.service.llm_service.complete_with_continuation", return_value=resp):
                await call_with_ledger(
                    client_mock, "alice",
                    [{"role": "user", "content": "hi"}],
                    "claude-sonnet-4-6",
                    ledger=ledger,
                    provider="anthropic",
                )
        finally:
            llm_service._CURRENT_CONFIG = old

        snap = ledger.snapshot()
        assert snap["total"]["gco2e"] > 0.0
        assert ledger.entries[0].footprint is not None
        assert ledger.entries[0].footprint.zone == "WOR"
