"""EI.3 — latency capture + ledger footprint fields.

Tests:
  - call_with_ledger records a Footprint when provider kwarg supplied.
  - snapshot()["total"] sums gco2e across two calls.
  - snapshot() works with zero footprint entries (backward-compat path).
  - LedgerEntry serialises correctly with and without footprint in _flush.
  - provider=None leaves footprint=None (no fabrication).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from armance.core.models.footprint import Footprint
from armance.service.llm_service import LedgerEntry, TokenLedger, call_with_ledger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_response(tokens_out: int = 600) -> object:
    from armance.core.protocols.llm import LLMResponse
    return LLMResponse(
        text="hello",
        tokens_in=100,
        tokens_out=tokens_out,
        finish_reason="stop",
        cost_usd=0.01,
    )


def _fake_client(tokens_out: int = 600):
    from armance.core.protocols.llm import LLMResponse
    resp = LLMResponse(
        text="hello",
        tokens_in=100,
        tokens_out=tokens_out,
        finish_reason="stop",
        cost_usd=0.01,
    )
    client = AsyncMock()
    client.stream_complete = AsyncMock(return_value=resp)
    return client, resp


# ---------------------------------------------------------------------------
# LedgerEntry — footprint field
# ---------------------------------------------------------------------------

class TestLedgerEntryFootprint:
    def test_ledger_entry_accepts_footprint(self) -> None:
        fp = Footprint(
            energy_wh=1.0, gco2e=0.5, water_ml=2.0, embodied_gco2e=0.1,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        e = LedgerEntry(agent="bob", tokens_in=10, tokens_out=20, cost_usd=0.01, footprint=fp)
        assert e.footprint is fp

    def test_ledger_entry_footprint_defaults_none(self) -> None:
        e = LedgerEntry(agent="bob", tokens_in=10, tokens_out=20, cost_usd=0.01)
        assert e.footprint is None


# ---------------------------------------------------------------------------
# TokenLedger.record + snapshot — gco2e aggregation
# ---------------------------------------------------------------------------

class TestTokenLedgerFootprint:
    def test_record_with_footprint(self) -> None:
        ledger = TokenLedger()
        fp = Footprint(
            energy_wh=1.0, gco2e=0.5, water_ml=2.0, embodied_gco2e=0.1,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=fp)
        snap = ledger.snapshot()
        assert snap["total"]["gco2e"] == pytest.approx(0.5)
        assert snap["total"]["water_ml"] == pytest.approx(2.0)

    def test_snapshot_sums_gco2e_across_two_calls(self) -> None:
        ledger = TokenLedger()
        fp1 = Footprint(
            energy_wh=1.0, gco2e=0.3, water_ml=1.0, embodied_gco2e=0.05,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        fp2 = Footprint(
            energy_wh=2.0, gco2e=0.7, water_ml=3.0, embodied_gco2e=0.1,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=fp1)
        ledger.record("alice", 100, 300, cost_usd=0.02, footprint=fp2)
        snap = ledger.snapshot()
        assert snap["total"]["gco2e"] == pytest.approx(1.0)
        assert snap["total"]["water_ml"] == pytest.approx(4.0)

    def test_snapshot_per_agent_gco2e(self) -> None:
        ledger = TokenLedger()
        fp_a = Footprint(
            energy_wh=1.0, gco2e=0.4, water_ml=1.5, embodied_gco2e=0.05,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        fp_b = Footprint(
            energy_wh=2.0, gco2e=0.6, water_ml=2.5, embodied_gco2e=0.1,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=fp_a)
        ledger.record("bob", 100, 300, cost_usd=0.02, footprint=fp_b)
        snap = ledger.snapshot()
        assert snap["per_agent"]["alice"]["gco2e"] == pytest.approx(0.4)
        assert snap["per_agent"]["bob"]["gco2e"] == pytest.approx(0.6)

    def test_snapshot_none_footprint_counts_as_zero(self) -> None:
        """Backward compat: entries without footprint don't break snapshot."""
        ledger = TokenLedger()
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=None)
        snap = ledger.snapshot()
        assert snap["total"]["gco2e"] == pytest.approx(0.0)
        assert snap["total"]["water_ml"] == pytest.approx(0.0)

    def test_snapshot_mixed_none_and_footprint(self) -> None:
        ledger = TokenLedger()
        fp = Footprint(
            energy_wh=1.0, gco2e=0.5, water_ml=2.0, embodied_gco2e=0.1,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=None)
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=fp)
        snap = ledger.snapshot()
        assert snap["total"]["gco2e"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Flush serialises footprint without crashing
# ---------------------------------------------------------------------------

class TestLedgerFlush:
    def test_flush_with_footprint(self, tmp_path: Path) -> None:
        path = tmp_path / "ledger.json"
        ledger = TokenLedger(persist_path=path)
        fp = Footprint(
            energy_wh=1.0, gco2e=0.5, water_ml=2.0, embodied_gco2e=0.1,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=fp)
        assert path.exists()
        data = json.loads(path.read_text())
        entry = data["entries"][0]
        assert entry["gco2e"] == pytest.approx(0.5)
        assert entry["water_ml"] == pytest.approx(2.0)
        assert entry["tier"] == "exact"
        assert entry["estimate"] is False

    def test_flush_with_none_footprint(self, tmp_path: Path) -> None:
        path = tmp_path / "ledger.json"
        ledger = TokenLedger(persist_path=path)
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=None)
        data = json.loads(path.read_text())
        entry = data["entries"][0]
        assert entry.get("gco2e") is None

    def test_old_ledger_json_missing_footprint_fields(self, tmp_path: Path) -> None:
        """Old ledger.json written without footprint fields; snapshot still works."""
        path = tmp_path / "ledger.json"
        # Simulate old format: no gco2e/water_ml fields
        old_payload = {
            "entries": [
                {"agent": "alice", "tokens_in": 100, "tokens_out": 200, "cost_usd": 0.01}
            ],
            "snapshot_unsafe": None,
        }
        path.write_text(json.dumps(old_payload), encoding="utf-8")
        # TokenLedger never reads its own json (append-write only); test that
        # snapshot on an entry without footprint returns zero gco2e gracefully.
        ledger = TokenLedger(persist_path=path)
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=None)
        snap = ledger.snapshot()
        assert snap["total"]["gco2e"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# call_with_ledger — latency timing + footprint recording
# ---------------------------------------------------------------------------

class TestCallWithLedgerFootprint:
    @pytest.mark.asyncio
    async def test_records_footprint_when_provider_supplied(self) -> None:
        client, resp = _fake_client(600)
        ledger = TokenLedger()

        with patch("armance.service.llm_service.complete_with_continuation", return_value=resp):
            await call_with_ledger(
                client,
                "alice",
                [{"role": "user", "content": "hi"}],
                "claude-sonnet-4-6",
                ledger=ledger,
                provider="anthropic",
            )

        snap = ledger.snapshot()
        assert snap["total"]["gco2e"] > 0.0

    @pytest.mark.asyncio
    async def test_footprint_none_when_no_provider(self) -> None:
        client, resp = _fake_client(600)
        ledger = TokenLedger()

        with patch("armance.service.llm_service.complete_with_continuation", return_value=resp):
            await call_with_ledger(
                client,
                "alice",
                [{"role": "user", "content": "hi"}],
                "claude-sonnet-4-6",
                ledger=ledger,
                # no provider kwarg
            )

        snap = ledger.snapshot()
        assert snap["total"]["gco2e"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_gco2e_sums_across_two_calls(self) -> None:
        client, resp = _fake_client(600)
        ledger = TokenLedger()

        with patch("armance.service.llm_service.complete_with_continuation", return_value=resp):
            await call_with_ledger(
                client, "alice", [{"role": "user", "content": "hi"}],
                "claude-sonnet-4-6", ledger=ledger, provider="anthropic",
            )
            await call_with_ledger(
                client, "alice", [{"role": "user", "content": "hi"}],
                "claude-sonnet-4-6", ledger=ledger, provider="anthropic",
            )

        snap = ledger.snapshot()
        assert snap["total"]["calls"] == 2
        # Each call adds footprint; total must be roughly 2× a single call
        assert snap["total"]["gco2e"] > 0.0
        assert snap["per_agent"]["alice"]["gco2e"] == pytest.approx(snap["total"]["gco2e"])

    @pytest.mark.asyncio
    async def test_existing_callers_not_broken(self) -> None:
        """call_with_ledger without provider= still returns a valid LLMResponse."""
        from armance.core.protocols.llm import LLMResponse
        client, resp = _fake_client(400)
        ledger = TokenLedger()

        with patch("armance.service.llm_service.complete_with_continuation", return_value=resp):
            result = await call_with_ledger(
                client, "bob", [{"role": "user", "content": "test"}],
                "some-model", ledger=ledger,
            )

        assert isinstance(result, LLMResponse)
        assert ledger.snapshot()["total"]["calls"] == 1


# ---------------------------------------------------------------------------
# snapshot() min/max bounds
# ---------------------------------------------------------------------------

class TestSnapshotBounds:
    def test_snapshot_sums_min_max(self) -> None:
        from armance.service.llm_service import TokenLedger
        from armance.core.models.footprint import Footprint
        led = TokenLedger()
        fp = Footprint(
            energy_wh=1.0, gco2e=2.0, water_ml=3.0, embodied_gco2e=0.2,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
            gco2e_min=1.0, gco2e_max=3.0, water_ml_min=2.0, water_ml_max=4.0,
        )
        led.record("alice", 10, 20, cost_usd=0.0, footprint=fp)
        led.record("alice", 10, 20, cost_usd=0.0, footprint=fp)
        snap = led.snapshot()
        assert snap["total"]["gco2e_min"] == 2.0
        assert snap["total"]["gco2e_max"] == 6.0

    def test_snapshot_bounds_fallback_to_midpoint_when_none(self) -> None:
        # A footprint without explicit bounds contributes its midpoint to both.
        from armance.service.llm_service import TokenLedger
        from armance.core.models.footprint import Footprint
        led = TokenLedger()
        fp = Footprint(
            energy_wh=1.0, gco2e=5.0, water_ml=3.0, embodied_gco2e=0.2,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )  # no *_min/*_max
        led.record("bob", 1, 1, cost_usd=0.0, footprint=fp)
        snap = led.snapshot()
        assert snap["total"]["gco2e_min"] == 5.0
        assert snap["total"]["gco2e_max"] == 5.0

    def test_ledger_initialization_loads_existing_file(self, tmp_path: Path) -> None:
        from armance.service.llm_service import TokenLedger
        from armance.core.models.footprint import Footprint
        
        persist = tmp_path / "ledger.json"
        
        led = TokenLedger(persist_path=persist)
        fp = Footprint(
            energy_wh=1.0, gco2e=5.0, water_ml=3.0, embodied_gco2e=0.2,
            estimate=False, tier="exact", proxy_model="some-proxy", zone="WOR",
            gco2e_min=4.0, gco2e_max=6.0, water_ml_min=2.0, water_ml_max=4.0,
        )
        led.record("alice", 10, 20, cost_usd=0.01, footprint=fp)
        
        led2 = TokenLedger(persist_path=persist)
        
        assert len(led2.entries) == 1
        entry = led2.entries[0]
        assert entry.agent == "alice"
        assert entry.tokens_in == 10
        assert entry.tokens_out == 20
        assert entry.cost_usd == 0.01
        assert entry.footprint is not None
        assert entry.footprint.gco2e == 5.0
        assert entry.footprint.water_ml == 3.0
        assert entry.footprint.tier == "exact"
        assert entry.footprint.proxy_model == "some-proxy"
        assert entry.footprint.zone == "WOR"
        assert entry.footprint.gco2e_min == 4.0
        assert entry.footprint.gco2e_max == 6.0


def test_accumulate_tiers_honesty_mapping() -> None:
    """provider-default is a guess, not a computation: it must land in
    'estimated'. Only a real declared parameter count is 'computed'."""
    from armance.service.footprint_ops import _accumulate_tiers, _empty_footprint_bucket

    bucket = _empty_footprint_bucket()
    rows = [
        {"gco2e": 1.0, "tier": "exact", "model": "a"},
        {"gco2e": 1.0, "tier": "aliased", "model": "b"},
        {"gco2e": 1.0, "tier": "params", "model": "c"},
        {"gco2e": 1.0, "tier": "similar", "model": "d"},
        {"gco2e": 1.0, "tier": "provider-default", "model": "e"},
        {"gco2e": 1.0, "tier": "bounded", "model": "f"},
    ]
    for r in rows:
        _accumulate_tiers(bucket, r)
    assert bucket["tiers"] == {
        "declared": 2.0, "computed": 1.0, "estimated": 2.0, "bounded": 1.0,
    }
