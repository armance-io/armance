"""D.7 — GET /runs/{run_id}/arguments + /runs/{run_id}/sources.

Reads the JSON sidecars Mona writes alongside synthesis.md (D.8).
When the sidecars are absent, returns the empty v1 envelope.

Spec: web-d-pipeline.md § D.7 + D.B + D.C
"""
from __future__ import annotations

import json
import pytest
from httpx import AsyncClient
from pathlib import Path


def _seed_run(armance_root: Path, name: str = "wf", run_id: str = "run-1") -> Path:
    run_dir = armance_root / "exports" / name / run_id
    run_dir.mkdir(parents=True)
    return run_dir


@pytest.mark.asyncio
async def test_arguments_returns_sidecar(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    run_dir = _seed_run(armance_root)
    payload = {
        "version": 1,
        "run_id": "run-1",
        "generated_at": "2026-05-26T22:00:00Z",
        "arguments": [{"id": "a_001", "claim": "x", "status": "retained"}],
    }
    (run_dir / "arguments.json").write_text(json.dumps(payload), encoding="utf-8")

    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-1/arguments"
    )
    assert resp.status_code == 200
    assert resp.json() == payload


@pytest.mark.asyncio
async def test_arguments_empty_when_no_sidecar(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_run(armance_root)

    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-1/arguments"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 1
    assert body["arguments"] == []


@pytest.mark.asyncio
async def test_arguments_unknown_run_404(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/nope/arguments"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sources_returns_sidecar(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    run_dir = _seed_run(armance_root)
    payload = {
        "version": 1,
        "sources": [
            {"id": "s_001", "kind": "doc", "ref": "docs/report.pdf#chunk_12"},
        ],
    }
    (run_dir / "sources.json").write_text(json.dumps(payload), encoding="utf-8")

    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-1/sources"
    )
    assert resp.status_code == 200
    assert resp.json() == payload


@pytest.mark.asyncio
async def test_sources_empty_when_no_sidecar(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _seed_run(armance_root)
    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/run-1/sources"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 1
    assert body["sources"] == []
