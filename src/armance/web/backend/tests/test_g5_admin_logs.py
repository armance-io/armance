"""G5 — GET /projects/{pid}/admin/logs (paginated, filtered).

Tests:
  - With 100 lines in llm_exchanges.jsonl, ?limit=20&agent=Armance returns
    matching lines and {total, cursor}.
  - Filter by agent: only matching events returned.
  - cursor-based pagination: second page continues from cursor.
  - Missing logs dir: returns empty list.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from httpx import AsyncClient


def _write_log(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _make_records(n: int, agent: str = "Armance") -> list[dict]:
    return [
        {
            "event": "response",
            "agent": agent,
            "timestamp": f"2026-05-{(i % 28) + 1:02d}T10:00:00",
            "tokens_in": 100 + i,
            "tokens_out": 50,
            "cost_usd": 0.001,
        }
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_logs_filter_by_agent_with_limit(client: AsyncClient, armance_root: Path) -> None:
    logs_dir = armance_root / "logs"
    records = _make_records(60, "Armance") + _make_records(40, "Mona")
    _write_log(logs_dir / "llm_exchanges.jsonl", records)

    resp = await client.get("/projects/default/admin/logs?limit=20&agent=Armance")

    assert resp.status_code == 200
    body = resp.json()
    assert "lines" in body
    assert "total" in body
    assert "cursor" in body
    assert len(body["lines"]) == 20
    assert body["total"] == 60
    for line in body["lines"]:
        assert line["agent"] == "Armance"


@pytest.mark.asyncio
async def test_logs_cursor_pagination(client: AsyncClient, armance_root: Path) -> None:
    logs_dir = armance_root / "logs"
    _write_log(logs_dir / "llm_exchanges.jsonl", _make_records(50, "Armance"))

    resp1 = await client.get("/projects/default/admin/logs?limit=20&agent=Armance")
    assert resp1.status_code == 200
    body1 = resp1.json()
    cursor = body1["cursor"]
    assert cursor is not None

    resp2 = await client.get(f"/projects/default/admin/logs?limit=20&agent=Armance&cursor={cursor}")
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert len(body2["lines"]) == 20

    resp3 = await client.get(f"/projects/default/admin/logs?limit=20&agent=Armance&cursor={body2['cursor']}")
    assert resp3.status_code == 200
    body3 = resp3.json()
    assert len(body3["lines"]) == 10
    assert body3["cursor"] is None


@pytest.mark.asyncio
async def test_logs_missing_dir(client: AsyncClient, armance_root: Path) -> None:
    resp = await client.get("/projects/default/admin/logs")

    assert resp.status_code == 200
    body = resp.json()
    assert body["lines"] == []
    assert body["total"] == 0
    assert body["cursor"] is None
