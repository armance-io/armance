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
    from armance.web.backend.routes.admin import _footprint_cache
    _footprint_cache.clear()
    # No logs dir created — should return empty, not 500
    resp = await client.get("/projects/default/admin/footprint?group_by=agent")
    assert resp.status_code == 200
    body = resp.json()
    assert body["by_agent"] == {}


def _resp_bounded(
    agent: str,
    gco2e: float,
    gco2e_min: float,
    gco2e_max: float,
    water_ml: float,
    water_ml_min: float,
    water_ml_max: float,
    ts: str = "2026-05-29T10:00:00",
) -> dict:
    """A D1-era record carrying explicit min/max bounds."""
    return {
        "event": "response",
        "agent": agent,
        "timestamp": ts,
        "gco2e": gco2e,
        "gco2e_min": gco2e_min,
        "gco2e_max": gco2e_max,
        "water_ml": water_ml,
        "water_ml_min": water_ml_min,
        "water_ml_max": water_ml_max,
        "estimate": True,
        "tier": "estimate",
        "zone": "WOR",
    }


@pytest.mark.asyncio
async def test_footprint_buckets_carry_bounds(
    client: AsyncClient, armance_root: Path
) -> None:
    """Every bucket exposes gco2e_min/max + water bounds; response has equiv."""
    from armance.web.backend.routes.admin import _footprint_cache
    _footprint_cache.clear()

    logs_dir = armance_root / "logs"
    _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [
        _resp_bounded("alice", 0.4, 0.2, 0.6, 2.0, 1.0, 3.0),
    ])
    resp = await client.get("/projects/default/admin/footprint?group_by=agent")
    assert resp.status_code == 200
    body = resp.json()
    for bucket in body["by_agent"].values():
        assert "gco2e_min" in bucket and "gco2e_max" in bucket
        assert "water_ml_min" in bucket and "water_ml_max" in bucket
    alice = body["by_agent"]["alice"]
    assert alice["gco2e_min"] == pytest.approx(0.2)
    assert alice["gco2e_max"] == pytest.approx(0.6)
    assert alice["water_ml_min"] == pytest.approx(1.0)
    assert alice["water_ml_max"] == pytest.approx(3.0)
    # equiv is a top-level ADEME equivalence on the midpoint total.
    assert "equiv" in body
    assert "phone_charges" in body["equiv"]
    assert "car_km" in body["equiv"]
    assert "water_glasses" in body["equiv"]


@pytest.mark.asyncio
async def test_footprint_bounds_fallback_old_records(
    client: AsyncClient, armance_root: Path
) -> None:
    """Old records without bound fields fall back to the midpoint value."""
    from armance.web.backend.routes.admin import _footprint_cache
    _footprint_cache.clear()

    logs_dir = armance_root / "logs"
    # _resp has no gco2e_min/max — must fall back to gco2e/water_ml.
    _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [
        _resp("alice", 0.3, 1.0),
    ])
    resp = await client.get("/projects/default/admin/footprint?group_by=agent")
    assert resp.status_code == 200
    alice = resp.json()["by_agent"]["alice"]
    assert alice["gco2e_min"] == pytest.approx(0.3)
    assert alice["gco2e_max"] == pytest.approx(0.3)
    assert alice["water_ml_min"] == pytest.approx(1.0)
    assert alice["water_ml_max"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_footprint_explicit_null_bound_falls_back(
    client: AsyncClient, armance_root: Path
) -> None:
    """A record with gco2e set but an explicit-null bound falls back, no crash."""
    from armance.web.backend.routes.admin import _footprint_cache
    _footprint_cache.clear()

    logs_dir = armance_root / "logs"
    rec = _resp("alice", 0.3, 1.0)
    rec["gco2e_min"] = None  # explicit null bound (partial D1 record)
    rec["gco2e_max"] = None
    _write_log(logs_dir / "sid1-llm_exchanges.jsonl", [rec])
    resp = await client.get("/projects/default/admin/footprint?group_by=agent")
    assert resp.status_code == 200
    alice = resp.json()["by_agent"]["alice"]
    assert alice["gco2e_min"] == pytest.approx(0.3)
    assert alice["gco2e_max"] == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_footprint_session_buckets_carry_bounds(
    client: AsyncClient, armance_root: Path
) -> None:
    """by_session buckets also carry bound fields."""
    from armance.web.backend.routes.admin import _footprint_cache
    _footprint_cache.clear()

    logs_dir = armance_root / "logs"
    _write_log(logs_dir / "abc123-llm_exchanges.jsonl", [
        _resp_bounded("alice", 0.4, 0.2, 0.6, 2.0, 1.0, 3.0),
    ])
    resp = await client.get("/projects/default/admin/footprint?group_by=session")
    assert resp.status_code == 200
    sess = resp.json()["by_session"]["abc123"]
    assert sess["gco2e_min"] == pytest.approx(0.2)
    assert sess["gco2e_max"] == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_footprint_cache_second_call_no_recompute(
    client: AsyncClient, armance_root: Path
) -> None:
    """Second request within 30s hits cache — footprint_stats called only once."""
    from armance.web.backend.routes import admin as admin_module
    from armance.web.backend.routes.admin import _footprint_cache
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
