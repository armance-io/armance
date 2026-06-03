"""EI.6 — TUI sub-title chip + /footprint command.

Tests pure functions only — no Textual screen instantiation.

Sub-tasks:
  1. _format_token_subtitle: gCO₂e chip present; ~ prefix on estimate;
     🌱? on unknown; water_ml appended when show_water=True.
  2. snapshot() carries estimate/unknown flags from ledger entries.
  3. aggregate_footprint_records: groups jsonl records by agent/day/month;
     flags estimate buckets.
  4. cmd_footprint: formats a Rich table string; groups by agent;
     flags estimates.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from armance.core.models.footprint import Footprint
from armance.service.footprint_ops import (
    aggregate_footprint_records,
    format_token_subtitle,
)
from armance.service.llm_service import TokenLedger


# ---------------------------------------------------------------------------
# format_token_subtitle
# ---------------------------------------------------------------------------

class TestFormatTokenSubtitle:
    def _snap_with_gco2e(
        self,
        gco2e: float,
        water_ml: float = 1.0,
        has_estimate: bool = False,
        has_unknown: bool = False,
    ) -> dict:
        return {
            "total": {
                "tokens_in": 100,
                "tokens_out": 200,
                "cost_usd": 0.01,
                "calls": 1,
                "gco2e": gco2e,
                "water_ml": water_ml,
                "has_estimate": has_estimate,
                "has_unknown": has_unknown,
            }
        }

    def test_chip_present_in_subtitle(self) -> None:
        snap = self._snap_with_gco2e(0.42)
        result = format_token_subtitle(snap, show_water=False)
        assert "gCO₂e" in result or "CO₂" in result

    def test_gco2e_value_in_subtitle(self) -> None:
        snap = self._snap_with_gco2e(0.42)
        result = format_token_subtitle(snap, show_water=False)
        assert "0.42" in result or "4.2e-01" in result or "🌱" in result

    def test_tilde_prefix_on_estimate(self) -> None:
        snap = self._snap_with_gco2e(0.42, has_estimate=True)
        result = format_token_subtitle(snap, show_water=False)
        assert "~" in result

    def test_question_mark_on_unknown(self) -> None:
        snap = self._snap_with_gco2e(0.0, has_unknown=True)
        result = format_token_subtitle(snap, show_water=False)
        assert "?" in result
        assert "🌱" in result

    def test_water_appended_when_show_water(self) -> None:
        snap = self._snap_with_gco2e(0.42, water_ml=5.0)
        result = format_token_subtitle(snap, show_water=True)
        assert "💧" in result

    def test_water_absent_when_show_water_false(self) -> None:
        snap = self._snap_with_gco2e(0.42, water_ml=5.0)
        result = format_token_subtitle(snap, show_water=False)
        assert "💧" not in result

    def test_tokens_and_cost_still_present(self) -> None:
        snap = self._snap_with_gco2e(0.3)
        result = format_token_subtitle(snap, show_water=False)
        assert "↑" in result
        assert "↓" in result
        assert "$" in result

    def test_zero_gco2e_no_unknown_shows_chip(self) -> None:
        snap = self._snap_with_gco2e(0.0, has_unknown=False)
        result = format_token_subtitle(snap, show_water=False)
        assert "🌱" in result

    def test_mixed_known_and_unknown_flags_partial(self) -> None:
        # Some calls had a footprint (gco2e>0) and some did not (has_unknown).
        # The summed chip must still carry a ``?`` so the user sees the total
        # is incomplete rather than a clean, complete-looking number.
        snap = self._snap_with_gco2e(0.42, has_unknown=True)
        result = format_token_subtitle(snap, show_water=False)
        assert "🌱" in result
        assert "0.42" in result or "4.2e-01" in result
        assert "?" in result

    def test_mixed_unknown_suppresses_water(self) -> None:
        # Water total is also partial when any entry is unknown — don't show it.
        snap = self._snap_with_gco2e(0.42, water_ml=5.0, has_unknown=True)
        result = format_token_subtitle(snap, show_water=True)
        assert "💧" not in result


# ---------------------------------------------------------------------------
# snapshot() estimate/unknown flags
# ---------------------------------------------------------------------------

class TestSnapshotEstimateFlags:
    def test_has_estimate_true_when_entry_estimate(self) -> None:
        ledger = TokenLedger()
        fp = Footprint(
            energy_wh=1.0, gco2e=0.3, water_ml=1.0, embodied_gco2e=0.05,
            estimate=True, tier="similar", proxy_model="x/y", zone="WOR",
        )
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=fp)
        snap = ledger.snapshot()
        assert snap["total"]["has_estimate"] is True

    def test_has_estimate_false_when_exact_tier(self) -> None:
        ledger = TokenLedger()
        fp = Footprint(
            energy_wh=1.0, gco2e=0.3, water_ml=1.0, embodied_gco2e=0.05,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=fp)
        snap = ledger.snapshot()
        assert snap["total"]["has_estimate"] is False

    def test_has_unknown_true_when_no_footprint(self) -> None:
        ledger = TokenLedger()
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=None)
        snap = ledger.snapshot()
        assert snap["total"]["has_unknown"] is True

    def test_has_unknown_false_when_all_have_footprint(self) -> None:
        ledger = TokenLedger()
        fp = Footprint(
            energy_wh=1.0, gco2e=0.3, water_ml=1.0, embodied_gco2e=0.05,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        ledger.record("alice", 100, 200, cost_usd=0.01, footprint=fp)
        snap = ledger.snapshot()
        assert snap["total"]["has_unknown"] is False

    def test_per_agent_has_estimate_flag(self) -> None:
        ledger = TokenLedger()
        fp = Footprint(
            energy_wh=1.0, gco2e=0.3, water_ml=1.0, embodied_gco2e=0.05,
            estimate=True, tier="similar", proxy_model="x/y", zone="WOR",
        )
        ledger.record("bob", 100, 200, cost_usd=0.01, footprint=fp)
        snap = ledger.snapshot()
        assert snap["per_agent"]["bob"]["has_estimate"] is True


# ---------------------------------------------------------------------------
# aggregate_footprint_records
# ---------------------------------------------------------------------------

def _make_records(tmp_path: Path, records: list[dict]) -> Path:
    log_file = tmp_path / "llm_exchanges.jsonl"
    for r in records:
        log_file.write_text(
            log_file.read_text() if log_file.exists() else ""
        )
        with open(log_file, "a") as f:
            f.write(json.dumps(r) + "\n")
    return log_file


class TestAggregateFootprintRecords:
    def _response(
        self,
        agent: str,
        gco2e: float | None,
        water_ml: float | None,
        estimate: bool | None = False,
        tier: str | None = "exact",
        zone: str | None = "WOR",
        ts: str = "2026-05-29T10:00:00",
    ) -> dict:
        return {
            "event": "response",
            "agent": agent,
            "timestamp": ts,
            "gco2e": gco2e,
            "water_ml": water_ml,
            "estimate": estimate,
            "tier": tier,
            "zone": zone,
        }

    def test_groups_by_agent(self, tmp_path: Path) -> None:
        log = _make_records(tmp_path, [
            self._response("alice", 0.3, 1.0),
            self._response("bob", 0.5, 2.0),
            self._response("alice", 0.2, 0.5),
        ])
        result = aggregate_footprint_records([log])
        assert "alice" in result["by_agent"]
        assert "bob" in result["by_agent"]
        assert result["by_agent"]["alice"]["gco2e"] == pytest.approx(0.5)

    def test_groups_by_day(self, tmp_path: Path) -> None:
        log = _make_records(tmp_path, [
            self._response("alice", 0.3, 1.0, ts="2026-05-29T10:00:00"),
            self._response("alice", 0.2, 0.8, ts="2026-05-30T12:00:00"),
        ])
        result = aggregate_footprint_records([log])
        assert "2026-05-29" in result["by_day"]
        assert "2026-05-30" in result["by_day"]

    def test_groups_by_month(self, tmp_path: Path) -> None:
        log = _make_records(tmp_path, [
            self._response("alice", 0.3, 1.0, ts="2026-05-01T10:00:00"),
            self._response("alice", 0.4, 1.5, ts="2026-06-01T10:00:00"),
        ])
        result = aggregate_footprint_records([log])
        assert "2026-05" in result["by_month"]
        assert "2026-06" in result["by_month"]

    def test_estimate_bucket_flagged(self, tmp_path: Path) -> None:
        log = _make_records(tmp_path, [
            self._response("alice", 0.3, 1.0, estimate=True, tier="similar"),
        ])
        result = aggregate_footprint_records([log])
        assert result["by_agent"]["alice"]["has_estimate"] is True

    def test_none_gco2e_skips_sum(self, tmp_path: Path) -> None:
        log = _make_records(tmp_path, [
            self._response("alice", None, None, estimate=None, tier=None),
        ])
        result = aggregate_footprint_records([log])
        assert result["by_agent"]["alice"]["gco2e"] == pytest.approx(0.0)
        assert result["by_agent"]["alice"]["has_unknown"] is True

    def test_ignores_non_response_events(self, tmp_path: Path) -> None:
        log = _make_records(tmp_path, [
            {"event": "request", "agent": "alice", "timestamp": "2026-05-29T10:00:00"},
            self._response("alice", 0.3, 1.0),
        ])
        result = aggregate_footprint_records([log])
        assert result["by_agent"]["alice"]["gco2e"] == pytest.approx(0.3)

    def test_dominant_zone_recorded(self, tmp_path: Path) -> None:
        log = _make_records(tmp_path, [
            self._response("alice", 0.3, 1.0, zone="FRA"),
            self._response("alice", 0.2, 0.8, zone="FRA"),
        ])
        result = aggregate_footprint_records([log])
        assert result["dominant_zone"] == "FRA"


# ---------------------------------------------------------------------------
# cmd_footprint output (pure string check)
# ---------------------------------------------------------------------------

class TestCmdFootprintOutput:
    @pytest.mark.asyncio
    async def test_footprint_cmd_returns_string(self, tmp_path: Path) -> None:
        from armance.service.footprint_ops import cmd_footprint
        ctx = MagicMock()
        ctx.armance_root = tmp_path
        (tmp_path / ".armance" / "logs").mkdir(parents=True)
        result = await cmd_footprint([], ctx)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_footprint_cmd_with_data_has_agent(self, tmp_path: Path) -> None:
        from armance.service.footprint_ops import cmd_footprint
        log_dir = tmp_path / ".armance" / "logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "llm_exchanges.jsonl"
        log_file.write_text(json.dumps({
            "event": "response",
            "agent": "alice",
            "timestamp": "2026-05-29T10:00:00",
            "gco2e": 0.42,
            "water_ml": 2.0,
            "estimate": False,
            "tier": "exact",
            "zone": "WOR",
        }) + "\n")
        ctx = MagicMock()
        ctx.armance_root = tmp_path
        result = await cmd_footprint([], ctx)
        assert "alice" in result
