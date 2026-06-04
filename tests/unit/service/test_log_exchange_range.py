"""log_response must persist the carbon/water min-max bounds, not just the
midpoint — otherwise the live range collapses to a flat value downstream."""

from __future__ import annotations

import json
import os
from pathlib import Path

from armance.core.models.footprint import Footprint
from armance.service.llm_service import LLMResponse, log_response


def _read_only_record(logs_dir: Path) -> dict:
    log_file = logs_dir / "llm_exchanges.jsonl"
    lines = [ln for ln in log_file.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1
    return json.loads(lines[0])


def test_log_response_persists_range_bounds(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fp = Footprint(
        energy_wh=0.05,
        gco2e=0.006,
        water_ml=0.25,
        embodied_gco2e=0.0,
        estimate=False,
        tier="aliased",
        proxy_model=None,
        zone="WOR",
        gco2e_min=0.0034,
        gco2e_max=0.0086,
        water_ml_min=0.18,
        water_ml_max=0.33,
    )
    resp = LLMResponse(text="hi", tokens_in=2, tokens_out=10, cost_usd=None, finish_reason="stop")
    log_response("alice", "claude-haiku-4-5", resp, footprint=fp)

    rec = _read_only_record(tmp_path / ".armance" / "logs")
    assert rec["gco2e_min"] == 0.0034
    assert rec["gco2e_max"] == 0.0086
    assert rec["water_ml_min"] == 0.18
    assert rec["water_ml_max"] == 0.33
    # midpoint and tier still present
    assert rec["gco2e"] == 0.006
    assert rec["tier"] == "aliased"
