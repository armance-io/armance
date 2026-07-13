"""EI.4 — response log line carries footprint fields.

Spec: a `response` log entry in llm_exchanges.jsonl contains
gco2e, water_ml, estimate, tier, zone.
Also: None footprint writes null for those fields (never omit them).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from armance.core.models.footprint import Footprint
from armance.service.llm_service import log_response


def _fake_response(tokens_out: int = 600) -> object:
    from armance.core.protocols.llm import LLMResponse
    return LLMResponse(
        text="hello",
        tokens_in=100,
        tokens_out=tokens_out,
        finish_reason="stop",
        cost_usd=0.01,
    )


def _last_jsonl_entry(log_file: Path) -> dict:
    lines = [ln for ln in log_file.read_text().splitlines() if ln.strip()]
    return json.loads(lines[-1])


# ---------------------------------------------------------------------------
# log_response with footprint
# ---------------------------------------------------------------------------

class TestLogResponseFootprintFields:
    def test_response_line_contains_gco2e(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        fp = Footprint(
            energy_wh=1.0, gco2e=0.42, water_ml=2.1, embodied_gco2e=0.05,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        log_response("alice", "claude-sonnet-4-6", _fake_response(), footprint=fp)
        entry = _last_jsonl_entry(tmp_path / ".armance" / "logs" / "llm_exchanges.jsonl")
        assert entry["event"] == "response"
        assert entry["gco2e"] == pytest.approx(0.42)

    def test_response_line_contains_water_ml(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        fp = Footprint(
            energy_wh=1.0, gco2e=0.42, water_ml=2.1, embodied_gco2e=0.05,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        log_response("alice", "claude-sonnet-4-6", _fake_response(), footprint=fp)
        entry = _last_jsonl_entry(tmp_path / ".armance" / "logs" / "llm_exchanges.jsonl")
        assert entry["water_ml"] == pytest.approx(2.1)

    def test_response_line_contains_estimate(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        fp = Footprint(
            energy_wh=1.0, gco2e=0.42, water_ml=2.1, embodied_gco2e=0.05,
            estimate=True, tier="similar", proxy_model="anthropic/claude-haiku-4-5", zone="WOR",
        )
        log_response("alice", "claude-sonnet-4-6", _fake_response(), footprint=fp)
        entry = _last_jsonl_entry(tmp_path / ".armance" / "logs" / "llm_exchanges.jsonl")
        assert entry["estimate"] is True

    def test_response_line_contains_tier(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        fp = Footprint(
            energy_wh=1.0, gco2e=0.42, water_ml=2.1, embodied_gco2e=0.05,
            estimate=False, tier="aliased", proxy_model=None, zone="WOR",
        )
        log_response("alice", "claude-sonnet-4-6", _fake_response(), footprint=fp)
        entry = _last_jsonl_entry(tmp_path / ".armance" / "logs" / "llm_exchanges.jsonl")
        assert entry["tier"] == "aliased"

    def test_response_line_contains_zone(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        fp = Footprint(
            energy_wh=1.0, gco2e=0.42, water_ml=2.1, embodied_gco2e=0.05,
            estimate=False, tier="exact", proxy_model=None, zone="FRA",
        )
        log_response("alice", "claude-sonnet-4-6", _fake_response(), footprint=fp)
        entry = _last_jsonl_entry(tmp_path / ".armance" / "logs" / "llm_exchanges.jsonl")
        assert entry["zone"] == "FRA"

    def test_response_line_none_footprint_writes_null_fields(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        log_response("alice", "claude-sonnet-4-6", _fake_response(), footprint=None)
        entry = _last_jsonl_entry(tmp_path / ".armance" / "logs" / "llm_exchanges.jsonl")
        assert entry["gco2e"] is None
        assert entry["water_ml"] is None
        assert entry["estimate"] is None
        assert entry["tier"] is None
        assert entry["zone"] is None

    def test_existing_fields_still_present(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        fp = Footprint(
            energy_wh=1.0, gco2e=0.3, water_ml=1.0, embodied_gco2e=0.05,
            estimate=False, tier="exact", proxy_model=None, zone="WOR",
        )
        log_response("alice", "claude-sonnet-4-6", _fake_response(400), footprint=fp)
        entry = _last_jsonl_entry(tmp_path / ".armance" / "logs" / "llm_exchanges.jsonl")
        assert entry["tokens_out"] == 400
        assert entry["cost_usd"] == pytest.approx(0.01)
        assert "response_preview" in entry

    def test_no_footprint_kwarg_backward_compat(self, tmp_path: Path, monkeypatch) -> None:
        """Existing callers that don't pass footprint= still work."""
        monkeypatch.chdir(tmp_path)
        log_response("alice", "claude-sonnet-4-6", _fake_response())
        entry = _last_jsonl_entry(tmp_path / ".armance" / "logs" / "llm_exchanges.jsonl")
        assert entry["event"] == "response"
        # footprint fields present as null (not missing)
        assert "gco2e" in entry
        assert entry["gco2e"] is None
