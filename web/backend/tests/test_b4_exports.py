"""B.4 — GET /exports/{filename} tests.

Spec (web-b-viewer.md §B.4):
  1. .md served text/markdown; charset=utf-8; .pdf/.docx/.pptx as application/octet-stream.
  2. path traversal rejected with 400.
  3. implemented using pathlib.resolve() + is_relative_to(exports_root), and Storage.read_bytes.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.asyncio
async def test_download_export_md_content_type(client: AsyncClient, armance_root: Path) -> None:
    """GET /exports/doc.md serves text/markdown; charset=utf-8."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    exports_dir = armance_root / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    (exports_dir / "doc.md").write_text("# Markdown", encoding="utf-8")

    resp = await client.get(f"/projects/default/sessions/{sid}/exports/doc.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
    assert b"# Markdown" in resp.content


@pytest.mark.asyncio
async def test_download_export_pdf_content_type(client: AsyncClient, armance_root: Path) -> None:
    """GET /exports/doc.pdf serves application/octet-stream."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    exports_dir = armance_root / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    (exports_dir / "doc.pdf").write_bytes(b"%PDF-1.4")

    resp = await client.get(f"/projects/default/sessions/{sid}/exports/doc.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/octet-stream"
    assert b"%PDF-1.4" in resp.content


@pytest.mark.asyncio
async def test_download_export_path_traversal_returns_400(client: AsyncClient) -> None:
    """GET /exports/../../etc/passwd returns 400 (or 404 if normalized by client)."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.get(f"/projects/default/sessions/{sid}/exports/../../etc/passwd")
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_download_export_uses_storage_read_bytes(client: AsyncClient, armance_root: Path) -> None:
    """The read must go through Storage.read_bytes (for V3 GCS compat)."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    exports_dir = armance_root / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    (exports_dir / "file.md").write_text("hello", encoding="utf-8")

    from unittest.mock import AsyncMock
    with patch("backend.routes.exports.LocalFilesystemStorage") as MockStorage:
        instance = MockStorage.return_value
        instance.read_bytes = AsyncMock(return_value=b"intercepted")
        
        resp = await client.get(f"/projects/default/sessions/{sid}/exports/file.md")
        
        assert resp.status_code == 200
        assert resp.content == b"intercepted"
        instance.read_bytes.assert_called_once_with("exports/file.md")
