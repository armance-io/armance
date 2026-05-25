"""B.2 — POST /projects/{pid}/sessions/{sid}/library/docs tests.

Spec (web-b-viewer.md §B.2):
  1. multipart/form-data file + auto_index=true → 201 {name, size, indexed: true};
     file lands in .armance/docs/<file>; sync_docs was called.
  2. auto_index=false → 201 {name, size, indexed: false}; doc lands; not indexed.
  3. empty filename → 400; file > MAX_UPLOAD_BYTES → 413; path traversal → 400.
  4. writes go through Storage.write_bytes (mock and assert).
"""
from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.asyncio
async def test_import_doc_auto_index_true(client: AsyncClient, armance_root: Path) -> None:
    """POST /library/docs with auto_index=true → 201; file saved; sync_docs called."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    with patch("backend.routes.library_docs.sync_docs") as mock_sync:
        mock_sync.return_value = {"test.md": 5}
        resp = await client.post(
            f"/projects/default/sessions/{sid}/library/docs",
            data={"auto_index": "true"},
            files={"file": ("test.md", b"# Test\nContent.", "text/markdown")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "test.md"
    assert body["indexed"] is True
    assert (armance_root / "docs" / "test.md").exists()
    mock_sync.assert_called_once()


@pytest.mark.asyncio
async def test_import_doc_auto_index_false(client: AsyncClient, armance_root: Path) -> None:
    """POST /library/docs with auto_index=false → 201; file saved; not indexed."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    with patch("backend.routes.library_docs.sync_docs") as mock_sync:
        resp = await client.post(
            f"/projects/default/sessions/{sid}/library/docs",
            data={"auto_index": "false"},
            files={"file": ("report.md", b"# Report\nBody.", "text/markdown")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "report.md"
    assert body["indexed"] is False
    assert (armance_root / "docs" / "report.md").exists()
    mock_sync.assert_not_called()


@pytest.mark.asyncio
async def test_import_doc_empty_filename_returns_400(client: AsyncClient) -> None:
    """POST /library/docs with empty filename → 400 or 422 (FastAPI validation)."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.post(
        f"/projects/default/sessions/{sid}/library/docs",
        data={"auto_index": "false"},
        files={"file": ("", b"content", "text/plain")},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_import_doc_path_traversal_returns_400(client: AsyncClient) -> None:
    """POST /library/docs with traversal filename → 400."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    resp = await client.post(
        f"/projects/default/sessions/{sid}/library/docs",
        data={"auto_index": "false"},
        files={"file": ("../escape.md", b"bad", "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_doc_too_large_returns_413(client: AsyncClient) -> None:
    """POST /library/docs with oversized file → 413."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    # Create a file larger than MAX_UPLOAD_BYTES (50 MB)
    from backend.routes.library_docs import MAX_UPLOAD_BYTES
    big_data = b"x" * (MAX_UPLOAD_BYTES + 1)

    resp = await client.post(
        f"/projects/default/sessions/{sid}/library/docs",
        data={"auto_index": "false"},
        files={"file": ("big.pdf", big_data, "application/pdf")},
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_import_doc_uses_storage_write_bytes(
    client: AsyncClient, armance_root: Path
) -> None:
    """Writes go through Storage.write_bytes (not direct pathlib)."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    write_calls = []

    class FakeStorage:
        async def write_bytes(self, key: str, data: bytes) -> None:
            write_calls.append((key, data))
            # Actually write so the file exists.
            path = armance_root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        async def read_bytes(self, key: str) -> bytes:
            return (armance_root / key).read_bytes()

        async def list(self, prefix: str) -> list[str]:
            return []

    with patch("backend.routes.library_docs.LocalFilesystemStorage", return_value=FakeStorage()):
        with patch("backend.routes.library_docs.sync_docs", return_value={}):
            resp = await client.post(
                f"/projects/default/sessions/{sid}/library/docs",
                data={"auto_index": "false"},
                files={"file": ("doc.md", b"Content", "text/markdown")},
            )

    assert resp.status_code == 201
    assert any("docs/doc.md" in k for k, _ in write_calls)
