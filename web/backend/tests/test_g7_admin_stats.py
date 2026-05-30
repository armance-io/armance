"""G7 — GET /projects/{pid}/admin/stats.

Tests:
  - Seeded llm_exchanges.jsonl with 3 agents: returns per-agent
    tokens_in/tokens_out/cost_usd/msg_count/avg_latency_ms + global summary.
  - Cached for 30s: second call within window does not re-read the file.
"""
from __future__ import annotations

import json
import time
import pytest
from pathlib import Path
from httpx import AsyncClient
from unittest.mock import patch


def _write_log(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _make_exchange(agent: str, tokens_in: int, tokens_out: int, cost: float,
                   ts_req: str, ts_resp: str, latency_ms: float) -> list[dict]:
    return [
        {"event": "request", "agent": agent, "timestamp": ts_req},
        {
            "event": "response",
            "agent": agent,
            "timestamp": ts_resp,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost,
            "latency_ms": latency_ms,
        },
    ]


@pytest.mark.asyncio
async def test_stats_per_agent_and_global(client: AsyncClient, armance_root: Path) -> None:
    # Import and clear the cache before the test
    from backend.routes.admin_stats import _stats_cache
    _stats_cache.clear()

    logs_dir = armance_root / "logs"
    records: list[dict] = []
    records += _make_exchange("Alice", 100, 50, 0.001, "2026-05-01T10:00:00", "2026-05-01T10:00:01", 1000)
    records += _make_exchange("Alice", 200, 80, 0.002, "2026-05-01T11:00:00", "2026-05-01T11:00:02", 2000)
    records += _make_exchange("Bob", 300, 120, 0.003, "2026-05-01T12:00:00", "2026-05-01T12:00:03", 3000)
    records += _make_exchange("Carol", 50, 20, 0.0005, "2026-05-01T13:00:00", "2026-05-01T13:00:00.5", 500)
    _write_log(logs_dir / "llm_exchanges.jsonl", records)

    resp = await client.get("/projects/default/admin/stats")

    assert resp.status_code == 200
    body = resp.json()

    assert "agents" in body
    assert "global" in body

    alice = body["agents"]["Alice"]
    assert alice["tokens_in"] == 300
    assert alice["tokens_out"] == 130
    assert abs(alice["cost_usd"] - 0.003) < 1e-6
    assert alice["msg_count"] == 2
    assert alice["avg_latency_ms"] == 1500.0

    bob = body["agents"]["Bob"]
    assert bob["msg_count"] == 1
    assert bob["tokens_in"] == 300

    carol = body["agents"]["Carol"]
    assert carol["msg_count"] == 1

    g = body["global"]
    assert g["msg_count"] == 4
    assert g["tokens_in"] == 650
    assert g["tokens_out"] == 270


@pytest.mark.asyncio
async def test_stats_cached_within_30s(client: AsyncClient, armance_root: Path) -> None:
    from backend.routes.admin_stats import _stats_cache
    _stats_cache.clear()

    logs_dir = armance_root / "logs"
    records = _make_exchange("X", 10, 5, 0.0001, "2026-05-01T10:00:00", "2026-05-01T10:00:00.1", 100)
    _write_log(logs_dir / "llm_exchanges.jsonl", records)

    import backend.routes.admin_stats as stats_mod

    read_calls: list[int] = []
    original_read = stats_mod._read_log_records

    def counting_read(logs_dir):  # type: ignore[no-untyped-def]
        read_calls.append(1)
        return original_read(logs_dir)

    with patch.object(stats_mod, "_read_log_records", side_effect=counting_read):
        resp1 = await client.get("/projects/default/admin/stats")
        resp2 = await client.get("/projects/default/admin/stats")

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert len(read_calls) == 1, f"expected 1 read, got {len(read_calls)}"
