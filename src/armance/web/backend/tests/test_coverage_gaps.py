"""Coverage gap tests — routes/docs, routes/exports, routes/library, deps.

These tests cover the lines that are uncovered and push coverage ≥ 85%.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient


# ─── docs.py ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_doc_returns_201(client: AsyncClient, armance_root: Path) -> None:
    """POST /docs uploads a file to <armance_root>/docs/<filename>."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.post(
        f"/projects/default/sessions/{sid}/docs",
        files={"file": ("hello.txt", b"Hello World", "text/plain")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "hello.txt"
    assert body["size"] == 11

    # File must exist on disk (via Storage ABC).
    assert (armance_root / "docs" / "hello.txt").exists()


@pytest.mark.asyncio
async def test_upload_doc_unknown_session_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/projects/default/sessions/bad-sid/docs",
        files={"file": ("f.txt", b"x", "text/plain")},
    )
    assert resp.status_code == 404


# ─── exports.py ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_download_export_returns_file(client: AsyncClient, armance_root: Path) -> None:
    """GET /exports/<filename> serves the file."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    # Plant an export file.
    exports_dir = armance_root / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    (exports_dir / "report.md").write_text("# Report\nContent", encoding="utf-8")

    resp = await client.get(f"/projects/default/sessions/{sid}/exports/report.md")
    assert resp.status_code == 200
    assert b"# Report" in resp.content


@pytest.mark.asyncio
async def test_download_export_not_found_returns_404(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    resp = await client.get(f"/projects/default/sessions/{sid}/exports/nonexistent.pdf")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_export_path_traversal_rejected(client: AsyncClient) -> None:
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    resp = await client.get(f"/projects/default/sessions/{sid}/exports/../../etc/passwd")
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_download_export_unknown_session_404(client: AsyncClient) -> None:
    resp = await client.get("/projects/default/sessions/bad-sid/exports/report.md")
    assert resp.status_code == 404


# ─── library.py ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_library_status_returns_library_dict(client: AsyncClient) -> None:
    """GET /library returns {library: {...}}."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.get(f"/projects/default/sessions/{sid}/library")
    assert resp.status_code == 200
    assert "library" in resp.json()


@pytest.mark.asyncio
async def test_library_status_stale_session_heals(client: AsyncClient) -> None:
    # Stale/browser-cached sid self-heals instead of 404-looping, so the
    # bibliothèque panel loads on first launch.
    resp = await client.get("/projects/default/sessions/bad-sid/library")
    assert resp.status_code == 200


# ─── deps.py — get_web_session ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_web_session_resolves_known_sid(client: AsyncClient) -> None:
    """Deps.get_web_session resolves via /sessions/{sid} endpoint."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]
    resp = await client.get(f"/projects/default/sessions/{sid}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_web_session_raises_404_for_unknown(client: AsyncClient) -> None:
    """Deps.get_web_session raises 404 for unknown sid."""
    resp = await client.get("/projects/default/sessions/bad-sid")
    assert resp.status_code == 404
