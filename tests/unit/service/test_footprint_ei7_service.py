"""EI.7 — footprint_stats service function.

Tests the pure footprint_stats() aggregation (by agent/day/month/session).
by_session is keyed by filename-derived sid, not a field in each record.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from armance.service.footprint_ops import footprint_stats


def _write_log(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _resp(
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


class TestFootprintStatsService:
    def test_returns_all_four_keys(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [_resp("alice", 0.3, 1.0)])
        result = footprint_stats(logs_dir, project_id="default")
        assert "by_agent" in result
        assert "by_day" in result
        assert "by_month" in result
        assert "by_session" in result

    def test_by_agent_aggregates(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [
            _resp("alice", 0.3, 1.0),
            _resp("alice", 0.2, 0.5),
            _resp("bob", 0.5, 2.0),
        ])
        result = footprint_stats(logs_dir, project_id="default")
        assert result["by_agent"]["alice"]["gco2e"] == pytest.approx(0.5)
        assert result["by_agent"]["bob"]["gco2e"] == pytest.approx(0.5)

    def test_by_day_groups(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [
            _resp("alice", 0.3, 1.0, ts="2026-05-29T10:00:00"),
            _resp("alice", 0.2, 0.8, ts="2026-05-30T12:00:00"),
        ])
        result = footprint_stats(logs_dir, project_id="default")
        assert "2026-05-29" in result["by_day"]
        assert "2026-05-30" in result["by_day"]

    def test_by_month_groups(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [
            _resp("alice", 0.3, 1.0, ts="2026-05-01T10:00:00"),
            _resp("alice", 0.4, 1.5, ts="2026-06-01T10:00:00"),
        ])
        result = footprint_stats(logs_dir, project_id="default")
        assert "2026-05" in result["by_month"]
        assert "2026-06" in result["by_month"]

    def test_by_session_keyed_by_filename_sid(self, tmp_path: Path) -> None:
        """Two session files → two separate session buckets, not merged."""
        logs_dir = tmp_path / "logs"
        _write_log(logs_dir / "abc123-llm_exchanges.jsonl", [_resp("alice", 0.3, 1.0)])
        _write_log(logs_dir / "def456-llm_exchanges.jsonl", [_resp("bob", 0.5, 2.0)])
        result = footprint_stats(logs_dir, project_id="default")
        # Must be TWO session buckets, not one merged bucket
        assert len(result["by_session"]) == 2
        assert "abc123" in result["by_session"]
        assert "def456" in result["by_session"]
        assert result["by_session"]["abc123"]["gco2e"] == pytest.approx(0.3)
        assert result["by_session"]["def456"]["gco2e"] == pytest.approx(0.5)

    def test_by_session_fallback_file_keyed_as_default(self, tmp_path: Path) -> None:
        """The bare llm_exchanges.jsonl (no session prefix) → keyed 'default'."""
        logs_dir = tmp_path / "logs"
        _write_log(logs_dir / "llm_exchanges.jsonl", [_resp("alice", 0.3, 1.0)])
        result = footprint_stats(logs_dir, project_id="default")
        assert "default" in result["by_session"]

    def test_estimate_flagged_in_session_bucket(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [
            _resp("alice", 0.3, 1.0, estimate=True, tier="similar"),
        ])
        result = footprint_stats(logs_dir, project_id="default")
        assert result["by_session"]["sid1"]["has_estimate"] is True

    def test_none_gco2e_marks_unknown(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [
            _resp("alice", None, None, estimate=None, tier=None),
        ])
        result = footprint_stats(logs_dir, project_id="default")
        assert result["by_session"]["sid1"]["has_unknown"] is True
        assert result["by_session"]["sid1"]["gco2e"] == pytest.approx(0.0)

    def test_empty_logs_dir_returns_empty_dicts(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        result = footprint_stats(logs_dir, project_id="default")
        assert result["by_agent"] == {}
        assert result["by_session"] == {}

    def test_missing_logs_dir_returns_empty_dicts(self, tmp_path: Path) -> None:
        result = footprint_stats(tmp_path / "nonexistent", project_id="default")
        assert result["by_agent"] == {}
