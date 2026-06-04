"""B.1 — GET /library tests.

Spec (web-b-viewer.md §B.1):
  1. Seed .armance/ with a doc + index it; route returns 200 with body
     matching get_rag_status(...) exactly.
  2. With no embedding_provider, returns 200 with available: false.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.asyncio
async def test_get_library_returns_rag_status(client: AsyncClient, armance_root: Path) -> None:
    """GET /library returns body matching get_rag_status() exactly."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    # Seed a doc so get_rag_status has something to inspect.
    docs_dir = armance_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "test.md").write_text("# Test doc\nContent here.", encoding="utf-8")

    # Mock get_rag_status to return a known value.
    fake_status = {
        "available": True,
        "indexed": 1,
        "loaded": 0,
        "docs": ["test.md"],
    }
    with patch(
        "armance.web.backend.routes.library.get_rag_status",
        return_value=fake_status,
    ):
        resp = await client.get(f"/projects/default/sessions/{sid}/library")

    assert resp.status_code == 200
    body = resp.json()
    assert body["library"] == fake_status


@pytest.mark.asyncio
async def test_get_library_counts_feuillets_per_doc(client: AsyncClient) -> None:
    """Per-doc + total feuillet counts come from docs_in_db chunks (keyed by
    'name', not 'source' — the latter silently produced 0 feuillets)."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    fake_status = {
        "available": True,
        "docs_on_disk": [{"name": "test.md", "size_kb": 2, "in_db": True}],
        "docs_in_db": [{"name": "test.md", "chunks": 23}],
        "total_chunks": 23,
        "embedding_model": "text-embedding-3-small",
    }
    with patch(
        "armance.web.backend.routes.library.get_rag_status",
        return_value=fake_status,
    ):
        resp = await client.get(f"/projects/default/sessions/{sid}/library")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_feuillets"] == 23
    assert body["docs"][0]["feuillets"] == 23
    assert body["docs"][0]["status"] == "indexed"


@pytest.mark.asyncio
async def test_get_library_no_embedding_provider_returns_available_false(
    client: AsyncClient,
) -> None:
    """Without embedding_provider, GET /library returns available: false."""
    cr = await client.post("/projects/default/sessions")
    sid = cr.json()["id"]

    fake_status = {"available": False, "indexed": 0, "loaded": 0, "docs": []}
    with patch(
        "armance.web.backend.routes.library.get_rag_status",
        return_value=fake_status,
    ):
        resp = await client.get(f"/projects/default/sessions/{sid}/library")

    assert resp.status_code == 200
    assert resp.json()["library"]["available"] is False
