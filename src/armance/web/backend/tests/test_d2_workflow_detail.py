"""D.2 — GET /workflows/{name} — workflow YAML + graph layout."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from pathlib import Path


def _write(armance_root: Path) -> None:
    wf_dir = armance_root / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "dossier-vapp.yaml").write_text(
        "name: dossier-vapp\n"
        "scope: produce a VAPP dossier\n"
        "strategy: equilibree\n"
        "steps:\n"
        "  - id: research\n    kind: task\n    role: historien\n"
        "  - id: revise\n    kind: task\n    role: historien\n    depends_on: [research]\n"
        "  - id: synthesise\n    kind: judge\n    role: mona\n    depends_on: [revise]\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_get_workflow_returns_yaml_and_graph(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    _write(armance_root)

    resp = await client.get(f"/projects/default/sessions/{sid}/workflows/dossier-vapp")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "dossier-vapp"
    assert data["scope"] == "produce a VAPP dossier"
    # `strategy` is not on the Workflow model — surfaced as "" via getattr.
    assert "strategy" in data
    assert len(data["steps"]) == 3
    assert "graph" in data
    nodes = data["graph"]["nodes"]
    edges = data["graph"]["edges"]
    assert len(nodes) == 3
    ids = {n["id"] for n in nodes}
    assert ids == {"research", "revise", "synthesise"}
    # Two depends_on edges.
    assert len(edges) == 2
    targets = {e["target"] for e in edges}
    assert targets == {"revise", "synthesise"}
    # Each node has an (x, y) position.
    for n in nodes:
        assert "position" in n
        assert "x" in n["position"]
        assert "y" in n["position"]


@pytest.mark.asyncio
async def test_get_workflow_unknown_returns_404(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    resp = await client.get(f"/projects/default/sessions/{sid}/workflows/nope")
    assert resp.status_code == 404
