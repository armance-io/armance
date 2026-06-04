from __future__ import annotations

import json
import pytest
from pathlib import Path
from httpx import AsyncClient

from armance.platform.storage import LocalFilesystemStorage


@pytest.mark.asyncio
async def test_get_deliverables_flat_list_sorted(client: AsyncClient, armance_root: Path) -> None:
    """GET /deliverables aggregates exports and mona docs sorted by created_at desc."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    # 1. Seed exports
    wf_dir = armance_root / "exports" / "wf-a" / "run-20260524-153000"
    wf_dir.mkdir(parents=True, exist_ok=True)
    
    synth_file = wf_dir / "synthesis.md"
    synth_file.write_text("# Synthèse — Foo\nSome content.", encoding="utf-8")
    
    pdf_file = wf_dir / "report.pdf"
    pdf_file.write_text("fake pdf bytes", encoding="utf-8")

    # 2. Seed docs
    docs_dir = armance_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    mona_file = docs_dir / "mona-bar-20260524.md"
    mona_file.write_text("# Bar\nMona content.", encoding="utf-8")

    # Fetch deliverables
    resp = await client.get(f"/projects/default/sessions/{sid}/deliverables")
    assert resp.status_code == 200
    data = resp.json()

    # We expect 3 deliverables
    assert len(data) == 3

    # Check synthesis
    synth_item = next(x for x in data if x["kind"] == "synthesis")
    assert synth_item["id"] == "exports/wf-a/run-20260524-153000/synthesis.md"
    assert synth_item["title"] == "Synthèse — Foo"
    assert synth_item["format"] == "md"
    assert synth_item["workflow"] == "wf-a"
    assert synth_item["run_id"] == "run-20260524-153000"
    assert synth_item["starred"] is False

    # Check export (pdf)
    pdf_item = next(x for x in data if x["kind"] == "export")
    assert pdf_item["id"] == "exports/wf-a/run-20260524-153000/report.pdf"
    assert pdf_item["title"] == "Synthèse — Foo"  # sibling synthesis title
    assert pdf_item["format"] == "pdf"
    assert pdf_item["workflow"] == "wf-a"
    assert pdf_item["run_id"] == "run-20260524-153000"

    # Check mona-deliverable
    mona_item = next(x for x in data if x["kind"] == "mona-deliverable")
    assert mona_item["id"] == "docs/mona-bar-20260524.md"
    assert mona_item["title"] == "Bar"
    assert mona_item["format"] == "md"


@pytest.mark.asyncio
async def test_patch_star_deliverable(client: AsyncClient, armance_root: Path) -> None:
    """PATCH /deliverables/{id}/star toggles starred and updates deliverables.json."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    # Seed docs
    docs_dir = armance_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    mona_file = docs_dir / "mona-bar-20260524.md"
    mona_file.write_text("# Bar", encoding="utf-8")

    # Star it
    target_id = "docs/mona-bar-20260524.md"
    resp = await client.patch(
        f"/projects/default/sessions/{sid}/deliverables/{target_id}/star",
        json={"starred": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == target_id
    assert data["starred"] is True

    # Check that deliverables.json is updated
    storage = LocalFilesystemStorage(root=armance_root)
    assert await storage.exists("deliverables.json")
    json_content = await storage.read_text("deliverables.json")
    starred_data = json.loads(json_content)
    assert target_id in starred_data["starred"]

    # Star it to False
    resp = await client.patch(
        f"/projects/default/sessions/{sid}/deliverables/{target_id}/star",
        json={"starred": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["starred"] is False

    json_content = await storage.read_text("deliverables.json")
    starred_data = json.loads(json_content)
    assert target_id not in starred_data["starred"]


@pytest.mark.asyncio
async def test_patch_star_unknown_id_404(client: AsyncClient) -> None:
    """PATCH on an unknown id returns 404."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.patch(
        f"/projects/default/sessions/{sid}/deliverables/docs/unknown.md/star",
        json={"starred": True},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "deliverable_not_found"


@pytest.mark.asyncio
async def test_get_deliverables_unknown_session_404(client: AsyncClient) -> None:
    """GET on an unknown session returns 404."""
    resp = await client.get("/projects/default/sessions/unknown-session-id/deliverables")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "session_not_found"


@pytest.mark.asyncio
async def test_patch_star_unknown_session_404(client: AsyncClient) -> None:
    """PATCH on an unknown session returns 404."""
    resp = await client.patch(
        "/projects/default/sessions/unknown-session-id/deliverables/some-id/star",
        json={"starred": True},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "session_not_found"

