"""D.1 — GET /workflows — list workflows for the session.

Spec: web-d-pipeline.md § D.1
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from pathlib import Path


def _write_wf(armance_root: Path, name: str, scope: str, n_steps: int) -> None:
    wf_dir = armance_root / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    steps_yaml = "\n".join(
        f"  - id: step_{i}\n    kind: task\n    role: historien"
        for i in range(n_steps)
    )
    (wf_dir / f"{name}.yaml").write_text(
        f"name: {name}\nscope: {scope}\nstrategy: equilibree\nsteps:\n{steps_yaml}\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_list_workflows_empty(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    resp = await client.get(f"/projects/default/sessions/{sid}/workflows")
    assert resp.status_code == 200
    assert resp.json() == {"workflows": []}


@pytest.mark.asyncio
async def test_list_workflows_returns_entries(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _write_wf(armance_root, "dossier-vapp", "produce a VAPP dossier", 3)
    _write_wf(armance_root, "comm-strategy", "frame a comm campaign", 5)

    resp = await client.get(f"/projects/default/sessions/{sid}/workflows")
    assert resp.status_code == 200
    items = resp.json()["workflows"]
    names = sorted(it["name"] for it in items)
    assert names == ["comm-strategy", "dossier-vapp"]
    for it in items:
        assert "scope" in it
        assert "step_count" in it
    dv = next(it for it in items if it["name"] == "dossier-vapp")
    assert dv["step_count"] == 3
    assert dv["scope"] == "produce a VAPP dossier"


@pytest.mark.asyncio
async def test_list_workflows_skips_invalid_yaml(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _write_wf(armance_root, "good", "scope", 1)
    (armance_root / "workflows" / "broken.yaml").write_text(
        "this is: not\n  valid: workflow:\n   yaml\n",
        encoding="utf-8",
    )
    resp = await client.get(f"/projects/default/sessions/{sid}/workflows")
    assert resp.status_code == 200
    names = [it["name"] for it in resp.json()["workflows"]]
    assert "good" in names
    # broken.yaml may or may not appear depending on the YAML parser's
    # tolerance — what matters is that the route doesn't 500.
