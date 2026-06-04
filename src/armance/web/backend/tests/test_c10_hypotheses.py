"""C.10 — GET /workflows/{name}/runs/{run_id}/hypotheses route.

Parses Mona's autonomous-mode hypothesis markers across the run's
step-*.md files and returns the structured list for the LivePanel
HypothesisList component.

Markers (per system-judge.md):
  **Hypothèse (Mona) :** <text>
  **Hypothesis (Mona):**  <text>

Spec: web-c-deliberation.md § C.10
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from pathlib import Path


@pytest.mark.asyncio
async def test_hypotheses_returned_from_step_files(
    client: AsyncClient, armance_root: Path
) -> None:
    """Markers across multiple steps are aggregated, in step order."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    run_dir = armance_root / "exports" / "dossier-vapp" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "step-design.md").write_text(
        "## Reflection\n"
        "Some prose.\n\n"
        "**Hypothèse (Mona) :** Le marché cible est l'Europe.\n"
        "Une autre ligne.\n\n"
        "**Hypothèse (Mona) :** Le budget reste sous 50k.\n",
        encoding="utf-8",
    )
    (run_dir / "step-synthesise.md").write_text(
        "Mona synthesis here.\n"
        "**Hypothesis (Mona):** Assumes no regulation change.\n",
        encoding="utf-8",
    )

    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/dossier-vapp/runs/run-1/hypotheses"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "hypotheses" in data
    items = data["hypotheses"]
    assert len(items) == 3
    # Each entry carries the step id + text + language hint.
    assert items[0]["step_id"] == "design"
    assert "Europe" in items[0]["text"]
    assert items[2]["step_id"] == "synthesise"
    assert items[2]["language"] in ("en", "fr")


@pytest.mark.asyncio
async def test_hypotheses_unknown_run_returns_404(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/no-such-run/hypotheses"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_hypotheses_empty_run_returns_empty_list(
    client: AsyncClient, armance_root: Path
) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    run_dir = armance_root / "exports" / "wf-empty" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "step-x.md").write_text("Pure prose, no marker.\n", encoding="utf-8")

    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf-empty/runs/run-1/hypotheses"
    )
    assert resp.status_code == 200
    assert resp.json() == {"hypotheses": []}


@pytest.mark.asyncio
async def test_hypotheses_path_traversal_rejected(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    resp = await client.get(
        f"/projects/default/sessions/{sid}/workflows/wf/runs/..%2Fescape/hypotheses"
    )
    assert resp.status_code in (400, 404)
