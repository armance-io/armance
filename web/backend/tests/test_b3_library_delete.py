"""B.3 — DELETE /library/docs/{name} (unindex + delete, confirmed).

Spec (web-b-viewer.md §B.3):
  1. Without {confirm: true} → 409 {error: confirm_required}.
     With it → 200 {unindexed: true, deleted: true}; file gone; forget_doc called.
  2. Unknown filename → 404.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.asyncio
async def test_delete_doc_without_confirm_returns_409(client: AsyncClient, armance_root: Path) -> None:
    """DELETE /library/docs/{name} without confirm → 409 confirm_required."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    # Plant the file.
    docs_dir = armance_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "doc.md").write_text("content", encoding="utf-8")

    resp = await client.request(
        "DELETE",
        f"/projects/default/sessions/{sid}/library/docs/doc.md",
        json={"confirm": False},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "confirm_required"
    # File should still exist.
    assert (docs_dir / "doc.md").exists()


@pytest.mark.asyncio
async def test_delete_doc_with_confirm_deletes_file(client: AsyncClient, armance_root: Path) -> None:
    """DELETE /library/docs/{name} with confirm=true → 200; file gone; forget_doc called."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    docs_dir = armance_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "report.md").write_text("# Report", encoding="utf-8")

    with patch("backend.routes.library_delete.forget_doc") as mock_forget:
        mock_forget.return_value = "ok"
        resp = await client.request(
            "DELETE",
            f"/projects/default/sessions/{sid}/library/docs/report.md",
            json={"confirm": True},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["unindexed"] is True
    assert body["deleted"] is True
    assert not (docs_dir / "report.md").exists()
    mock_forget.assert_called_once()


@pytest.mark.asyncio
async def test_delete_doc_unknown_name_returns_404(client: AsyncClient, armance_root: Path) -> None:
    """DELETE /library/docs/{name} for a non-existent file → 404."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.request(
        "DELETE",
        f"/projects/default/sessions/{sid}/library/docs/nonexistent.md",
        json={"confirm": True},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_doc_unknown_session_404(client: AsyncClient) -> None:
    resp = await client.request(
        "DELETE",
        "/projects/default/sessions/bad-sid/library/docs/x.md",
        json={"confirm": True},
    )
    assert resp.status_code == 404
