"""EI.7 — GET /projects/{pid}/admin/footprint route tests.

Tests:
  - group_by=agent returns per-agent rollup.
  - group_by=day returns per-day rollup.
  - group_by=month returns per-month rollup.
  - group_by=session returns two separate session buckets from two log files.
  - 30s cache: second call within window returns same result without re-reading.
  - Missing logs dir returns empty result (no 500).
  - Requires get_current_user (200 with user dep, not 401 — V2 stub always passes).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient


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
    ts: str = "2026-05-29T10:00:00",
    zone: str | None = "WOR",
) -> dict:
    return {
        "event": "response",
        "agent": agent,
        "timestamp": ts,
        "gco2e": gco2e,
        "water_ml": water_ml,
        "estimate": estimate,
        "tier": "exact",
        "zone": zone,
    }


@pytest.mark.asyncio
async def test_footprint_group_by_agent(client: AsyncClient, armance_root: Path) -> None:
    logs_dir = armance_root / "logs"
    _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [
        _resp("alice", 0.3, 1.0),
        _resp("bob", 0.5, 2.0),
    ])
    resp = await client.get("/projects/default/admin/footprint?group_by=agent")
    assert resp.status_code == 200
    body = resp.json()
    assert "by_agent" in body
    assert "alice" in body["by_agent"]
    assert "bob" in body["by_agent"]


@pytest.mark.asyncio
async def test_footprint_group_by_day(client: AsyncClient, armance_root: Path) -> None:
    logs_dir = armance_root / "logs"
    _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [
        _resp("alice", 0.3, 1.0, ts="2026-05-29T10:00:00"),
        _resp("alice", 0.2, 0.8, ts="2026-05-30T12:00:00"),
    ])
    resp = await client.get("/projects/default/admin/footprint?group_by=day")
    assert resp.status_code == 200
    body = resp.json()
    assert "by_day" in body
    assert "2026-05-29" in body["by_day"]
    assert "2026-05-30" in body["by_day"]


@pytest.mark.asyncio
async def test_footprint_group_by_month(client: AsyncClient, armance_root: Path) -> None:
    logs_dir = armance_root / "logs"
    _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [
        _resp("alice", 0.3, 1.0, ts="2026-05-01T10:00:00"),
    ])
    resp = await client.get("/projects/default/admin/footprint?group_by=month")
    assert resp.status_code == 200
    body = resp.json()
    assert "by_month" in body
    assert "2026-05" in body["by_month"]


@pytest.mark.asyncio
async def test_footprint_group_by_session_two_files(
    client: AsyncClient, armance_root: Path
) -> None:
    """Two session log files → two separate session buckets."""
    logs_dir = armance_root / "logs"
    _write_log(logs_dir / "abc123-llm_exchanges.jsonl", [_resp("alice", 0.3, 1.0)])
    _write_log(logs_dir / "def456-llm_exchanges.jsonl", [_resp("bob", 0.5, 2.0)])
    resp = await client.get("/projects/default/admin/footprint?group_by=session")
    assert resp.status_code == 200
    body = resp.json()
    assert "by_session" in body
    assert "abc123" in body["by_session"]
    assert "def456" in body["by_session"]
    assert body["by_session"]["abc123"]["gco2e"] == pytest.approx(0.3)
    assert body["by_session"]["def456"]["gco2e"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_footprint_default_group_by_is_agent(
    client: AsyncClient, armance_root: Path
) -> None:
    logs_dir = armance_root / "logs"
    _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [_resp("alice", 0.3, 1.0)])
    resp = await client.get("/projects/default/admin/footprint")
    assert resp.status_code == 200
    body = resp.json()
    assert "by_agent" in body


@pytest.mark.asyncio
async def test_footprint_missing_logs_no_500(
    client: AsyncClient, armance_root: Path
) -> None:
    from backend.routes.admin import _footprint_cache
    _footprint_cache.clear()
    # No logs dir created — should return empty, not 500
    resp = await client.get("/projects/default/admin/footprint?group_by=agent")
    assert resp.status_code == 200
    body = resp.json()
    assert body["by_agent"] == {}


@pytest.mark.asyncio
async def test_footprint_cache_second_call_no_recompute(
    client: AsyncClient, armance_root: Path
) -> None:
    """Second request within 30s hits cache — footprint_stats called only once."""
    from backend.routes import admin as admin_module
    from backend.routes.admin import _footprint_cache
    _footprint_cache.clear()

    logs_dir = armance_root / "logs"
    _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [_resp("alice", 0.3, 1.0)])

    call_count = 0
    original = admin_module.footprint_stats

    def counting_stats(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original(*args, **kwargs)

    with patch.object(admin_module, "footprint_stats", side_effect=counting_stats):
        await client.get("/projects/default/admin/footprint?group_by=agent")
        await client.get("/projects/default/admin/footprint?group_by=agent")

    assert call_count == 1  # second call served from cache
