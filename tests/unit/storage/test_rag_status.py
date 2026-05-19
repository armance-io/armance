"""Tests for rag_status: get_rag_status + format_rag_status_markdown."""
from __future__ import annotations

from pathlib import Path

import pytest

from armance.storage.rag_status import get_rag_status, format_rag_status_markdown


@pytest.fixture()
def armance_root(tmp_path: Path) -> Path:
    root = tmp_path / ".armance"
    root.mkdir()
    (root / "docs").mkdir()
    (root / "vector").mkdir()
    return root


def test_empty_docs(armance_root: Path) -> None:
    status = get_rag_status(armance_root)
    assert status["total_chunks"] == 0
    assert status["docs_on_disk"] == []
    assert status["orphans"] == []
    md = format_rag_status_markdown(status)
    assert "No documents" in md


def test_doc_not_indexed(armance_root: Path) -> None:
    (armance_root / "docs" / "spec.md").write_text("# Test")
    status = get_rag_status(armance_root)
    assert len(status["docs_on_disk"]) == 1
    doc = status["docs_on_disk"][0]
    assert doc["name"] == "spec.md"
    assert not doc["in_manifest"]
    assert not doc["in_db"]
    md = format_rag_status_markdown(status)
    assert "⏳" in md
    assert "spec.md" in md


def test_doc_in_manifest_marks_stale(armance_root: Path) -> None:
    import json
    doc = armance_root / "docs" / "spec.md"
    doc.write_text("# Original")
    # Put a wrong hash in manifest → stale
    manifest = {"spec.md": "aaabbbccc000"}
    (armance_root / "vector" / "manifest.json").write_text(json.dumps(manifest))
    status = get_rag_status(armance_root)
    assert status["docs_on_disk"][0]["stale"] is True
    md = format_rag_status_markdown(status)
    assert "🔄" in md


def test_orphan_detected(armance_root: Path) -> None:
    import json
    # manifest has a file not on disk
    manifest = {"deleted.md": "abc123"}
    (armance_root / "vector" / "manifest.json").write_text(json.dumps(manifest))
    status = get_rag_status(armance_root)
    assert "deleted.md" in status["orphans"]
    md = format_rag_status_markdown(status)
    assert "Orphans" in md or "deleted.md" in md


def test_format_returns_markdown(armance_root: Path) -> None:
    status = get_rag_status(armance_root)
    md = format_rag_status_markdown(status)
    assert "## RAG library" in md
    assert "Chunks" in md or "chunks" in md.lower()
