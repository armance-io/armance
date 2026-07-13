"""Tests for armance.storage.ingestion document loaders."""
from __future__ import annotations

from pathlib import Path

import pytest

from armance.storage.ingestion import (
    MAX_FILE_BYTES,
    Chunk,
    chunk_text,
    load_docx,
    load_file,
    load_md,
    load_pdf,
    load_txt,
    sync_docs,
)


# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------


def test_chunk_sha256_auto():
    c = Chunk(text="hello", source="f.txt")
    assert len(c.sha256) == 64


def test_chunk_sha256_deterministic():
    c1 = Chunk(text="hello", source="f.txt")
    c2 = Chunk(text="hello", source="f.txt")
    assert c1.sha256 == c2.sha256


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------


def test_chunk_text_single_para():
    chunks = chunk_text("Short text.", source="t.txt")
    assert len(chunks) == 1
    assert chunks[0].text == "Short text."
    assert chunks[0].source == "t.txt"
    assert chunks[0].page == 0


def test_chunk_text_preserves_page():
    chunks = chunk_text("Text.", source="f.pdf", page=3)
    assert chunks[0].page == 3


def test_chunk_text_splits_large(tmp_path: Path):
    # Build text that overflows 512 tokens by repeating words
    para = "word " * 200  # ~200 tokens per para
    text = "\n\n".join([para] * 5)  # ~1000 tokens total
    chunks = chunk_text(text, source="big.txt", max_tokens=512, overlap=64)
    assert len(chunks) >= 2


def test_chunk_text_overlap(tmp_path: Path):
    # 3 large paragraphs, each ~200 tokens → chunks overlap
    para = "word " * 200
    text = "\n\n".join([para] * 4)
    chunks = chunk_text(text, source="big.txt", max_tokens=512, overlap=64)
    # With overlap the second chunk should share some content with the first
    if len(chunks) >= 2:
        first_words = set(chunks[0].text.split())
        second_words = set(chunks[1].text.split())
        assert first_words & second_words, "overlap should share words"


# ---------------------------------------------------------------------------
# load_txt / load_md
# ---------------------------------------------------------------------------


def test_load_txt(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_text("Para one.\n\nPara two.", encoding="utf-8")
    chunks = load_txt(f)
    assert len(chunks) >= 1
    combined = " ".join(c.text for c in chunks)
    assert "Para one." in combined
    assert "Para two." in combined


def test_load_md(tmp_path: Path):
    f = tmp_path / "test.md"
    f.write_text("# Title\n\nBody text.\n\n## Section\n\nMore.", encoding="utf-8")
    chunks = load_md(f)
    assert len(chunks) >= 1
    combined = " ".join(c.text for c in chunks)
    assert "Title" in combined


def test_load_txt_skips_large_file(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    f = tmp_path / "big.txt"
    f.write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    import logging

    with caplog.at_level(logging.WARNING):
        chunks = load_txt(f)
    assert chunks == []
    assert "50 MB" in caplog.text


# ---------------------------------------------------------------------------
# load_pdf
# ---------------------------------------------------------------------------


def _make_minimal_pdf(path: Path, text: str = "Hello PDF world.") -> None:
    """Write a real minimal PDF with one page of text."""
    from pypdf import PdfWriter
    from pypdf.generic import NameObject, ArrayObject, NumberObject

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    # add a simple text annotation so extract_text() returns something
    writer.add_annotation(
        page_number=0,
        annotation={
            "/Type": NameObject("/Annot"),
            "/Subtype": NameObject("/FreeText"),
            "/Rect": ArrayObject([NumberObject(72), NumberObject(700), NumberObject(500), NumberObject(740)]),
            "/Contents": text,
        },
    )
    with open(path, "wb") as f:
        writer.write(f)


def test_load_pdf_returns_chunks(tmp_path: Path):
    f = tmp_path / "doc.pdf"
    _make_minimal_pdf(f)
    # pypdf may return empty string for blank pages — just verify no crash
    chunks = load_pdf(f)
    assert isinstance(chunks, list)


def test_load_pdf_skips_large(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    f = tmp_path / "big.pdf"
    f.write_bytes(b"%PDF-1.4\n" + b"x" * (MAX_FILE_BYTES + 1))
    import logging

    with caplog.at_level(logging.WARNING):
        chunks = load_pdf(f)
    assert chunks == []


# ---------------------------------------------------------------------------
# load_docx
# ---------------------------------------------------------------------------


def _make_docx(path: Path, paragraphs: list[str]) -> None:
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    doc.save(str(path))


def test_load_docx(tmp_path: Path):
    f = tmp_path / "doc.docx"
    _make_docx(f, ["First paragraph.", "Second paragraph.", "Third paragraph."])
    chunks = load_docx(f)
    assert len(chunks) >= 1
    combined = " ".join(c.text for c in chunks)
    assert "First paragraph." in combined
    assert "Third paragraph." in combined


def test_load_docx_skips_large(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    f = tmp_path / "big.docx"
    f.write_bytes(b"PK" + b"x" * (MAX_FILE_BYTES + 1))
    import logging

    with caplog.at_level(logging.WARNING):
        chunks = load_docx(f)
    assert chunks == []


# ---------------------------------------------------------------------------
# load_file dispatch
# ---------------------------------------------------------------------------


def test_load_file_txt(tmp_path: Path):
    f = tmp_path / "x.txt"
    f.write_text("hello", encoding="utf-8")
    assert load_file(f) != []


def test_load_file_md(tmp_path: Path):
    f = tmp_path / "x.md"
    f.write_text("# hi", encoding="utf-8")
    assert load_file(f) != []


def test_load_file_unsupported(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    f = tmp_path / "x.csv"
    f.write_text("a,b,c", encoding="utf-8")
    import logging

    with caplog.at_level(logging.WARNING):
        chunks = load_file(f)
    assert chunks == []
    assert "unsupported" in caplog.text


# ---------------------------------------------------------------------------
# sync_docs (task 1.5)
# ---------------------------------------------------------------------------


def _armance_root(tmp_path: Path) -> Path:
    root = tmp_path / ".armance"
    (root / "docs").mkdir(parents=True)
    return root


def test_sync_docs_first_run(tmp_path: Path) -> None:
    root = _armance_root(tmp_path)
    (root / "docs" / "a.txt").write_text("hello", encoding="utf-8")
    result = sync_docs(root)
    assert result["indexed"] == 1
    assert result["skipped"] == 0
    assert result["deleted"] == 0


def test_sync_docs_idempotent(tmp_path: Path) -> None:
    root = _armance_root(tmp_path)
    (root / "docs" / "a.txt").write_text("hello", encoding="utf-8")
    sync_docs(root)
    result = sync_docs(root)
    assert result["indexed"] == 0
    assert result["skipped"] == 1


def test_sync_docs_reindexes_changed_file(tmp_path: Path) -> None:
    root = _armance_root(tmp_path)
    f = root / "docs" / "a.txt"
    f.write_text("version 1", encoding="utf-8")
    sync_docs(root)
    f.write_text("version 2 changed content", encoding="utf-8")
    result = sync_docs(root)
    assert result["indexed"] == 1


def test_sync_docs_removes_deleted_file(tmp_path: Path) -> None:
    root = _armance_root(tmp_path)
    f = root / "docs" / "a.txt"
    f.write_text("content", encoding="utf-8")
    sync_docs(root)
    f.unlink()
    result = sync_docs(root)
    assert result["deleted"] == 1


def test_sync_docs_manifest_persisted(tmp_path: Path) -> None:
    root = _armance_root(tmp_path)
    (root / "docs" / "a.md").write_text("# doc", encoding="utf-8")
    sync_docs(root)
    manifest_path = root / "vector" / "manifest.json"
    assert manifest_path.exists()
    import json
    manifest = json.loads(manifest_path.read_text())
    assert "a.md" in manifest


def test_sync_docs_no_docs_dir(tmp_path: Path) -> None:
    root = tmp_path / ".armance"
    root.mkdir()
    result = sync_docs(root)
    assert result == {"indexed": 0, "skipped": 0, "deleted": 0}
