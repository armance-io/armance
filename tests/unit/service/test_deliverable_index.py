from __future__ import annotations

import json
import pytest
from pathlib import Path

from armance.platform.storage import LocalFilesystemStorage
from armance.service.deliverable_index import (
    extract_markdown_title,
    get_starred_ids,
    set_starred_id,
    list_deliverables,
)


def test_extract_markdown_title_success(tmp_path: Path) -> None:
    # 1. No file -> returns stem
    assert extract_markdown_title(tmp_path / "nonexistent.md") == "nonexistent"

    # 2. Markdown with title -> returns first heading
    f = tmp_path / "doc.md"
    f.write_text("# This is my title  \nContent", encoding="utf-8")
    assert extract_markdown_title(f) == "This is my title"

    # 3. Markdown with subheadings or no title -> returns stem
    f2 = tmp_path / "doc2.md"
    f2.write_text("Some text\n## Subheading", encoding="utf-8")
    assert extract_markdown_title(f2) == "Subheading"

    # 4. Empty markdown -> returns stem
    f3 = tmp_path / "doc3.md"
    f3.write_text("", encoding="utf-8")
    assert extract_markdown_title(f3) == "doc3"


@pytest.mark.asyncio
async def test_get_and_set_starred_ids(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(root=tmp_path)
    
    # Initially empty
    assert await get_starred_ids(storage) == []

    # Star an ID
    await set_starred_id(storage, "exports/wf/run-1/synthesis.md", True)
    assert await get_starred_ids(storage) == ["exports/wf/run-1/synthesis.md"]

    # Star another ID
    await set_starred_id(storage, "docs/mona-doc.md", True)
    assert set(await get_starred_ids(storage)) == {"exports/wf/run-1/synthesis.md", "docs/mona-doc.md"}

    # Unstar an ID
    await set_starred_id(storage, "exports/wf/run-1/synthesis.md", False)
    assert await get_starred_ids(storage) == ["docs/mona-doc.md"]


@pytest.mark.asyncio
async def test_list_deliverables_empty(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(root=tmp_path)
    res = await list_deliverables(tmp_path, storage)
    assert res == []


@pytest.mark.asyncio
async def test_list_deliverables_with_data(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(root=tmp_path)

    # 1. Seed exports
    wf_dir = tmp_path / "exports" / "wf-a" / "run-20260524-153000"
    wf_dir.mkdir(parents=True, exist_ok=True)
    
    synth_file = wf_dir / "synthesis.md"
    synth_file.write_text("# Synthèse — Foo", encoding="utf-8")
    
    pdf_file = wf_dir / "report.pdf"
    pdf_file.write_text("fake pdf bytes", encoding="utf-8")

    # Sibling exports in a run without synthesis.md
    wf_dir2 = tmp_path / "exports" / "wf-b" / "run-20260524-160000"
    wf_dir2.mkdir(parents=True, exist_ok=True)
    docx_file = wf_dir2 / "report.docx"
    docx_file.write_text("docx bytes", encoding="utf-8")

    # 2. Seed docs
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    mona_file = docs_dir / "mona-bar-20260524.md"
    mona_file.write_text("# Bar", encoding="utf-8")

    # Ignored files (non-directories in exports, non-run folders, non-mona docs)
    (tmp_path / "exports" / "file.txt").write_text("ignored", encoding="utf-8")
    (tmp_path / "exports" / "wf-a" / "not-a-run").mkdir(parents=True, exist_ok=True)
    (tmp_path / "exports" / "wf-a" / "not-a-run" / "synthesis.md").write_text("# Ignored", encoding="utf-8")
    (docs_dir / "other-doc.md").write_text("# Other", encoding="utf-8")

    res = await list_deliverables(tmp_path, storage)
    assert len(res) == 4

    # Verify synthesis.md
    synth_item = next(x for x in res if x["kind"] == "synthesis")
    assert synth_item["format"] == "md"
    assert synth_item["workflow"] == "wf-a"
    assert synth_item["run_id"] == "run-20260524-153000"
    assert synth_item["title"] == "Synthèse — Foo"
    assert synth_item["starred"] is False

    # Verify sibling export with synthesis
    pdf_item = next(x for x in res if x["kind"] == "export" and x["format"] == "pdf")
    assert pdf_item["title"] == "Synthèse — Foo"

    # Verify export without synthesis
    docx_item = next(x for x in res if x["kind"] == "export" and x["format"] == "docx")
    assert docx_item["title"] == "report"

    # Verify mona doc
    mona_item = next(x for x in res if x["kind"] == "mona-deliverable")
    assert mona_item["title"] == "Bar"

