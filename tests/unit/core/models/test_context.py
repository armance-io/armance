"""Tests for armance.core.models.context."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from armance.core.models.context import (
    append_to_layer,
    chunk_text,
    diff_sources,
    load_context,
    load_manifest,
    next_layer_version,
    scan_sources,
    write_context_layers,
    write_manifest,
)
from armance.storage.rag_index import context_with_rag


def _setup_armance(tmp_path: Path) -> Path:
    armance = tmp_path / ".armance"
    (armance / "docs" / "auth").mkdir(parents=True)
    (armance / "docs" / "auth" / "rfc.md").write_text("# Auth RFC\n\nbody", encoding="utf-8")
    (armance / "docs" / "stray.md").write_text("loose doc", encoding="utf-8")
    (armance / "reports" / "backend").mkdir(parents=True)
    (armance / "reports" / "backend" / "alpha_v1.md").write_text("v1", encoding="utf-8")
    (armance / "reports" / "backend" / "alpha_v2.md").write_text("v2", encoding="utf-8")
    (armance / "reports" / "backend" / "beta_v1.md").write_text("beta1", encoding="utf-8")
    return armance


def test_scan_keeps_only_latest_report_version(tmp_path: Path) -> None:
    armance = _setup_armance(tmp_path)
    sources = scan_sources(armance)
    names = {sf.path.name for sf in sources}
    assert "alpha_v2.md" in names
    assert "alpha_v1.md" not in names
    assert "beta_v1.md" in names
    assert "rfc.md" in names
    assert "stray.md" in names


def test_diff_sources_added_removed_unchanged(tmp_path: Path) -> None:
    armance = _setup_armance(tmp_path)
    sources = scan_sources(armance)
    write_manifest(armance, sources)
    manifest = load_manifest(armance)

    again = diff_sources(scan_sources(armance), manifest)
    assert again.added == []
    assert again.removed == []
    assert {sf.path.name for sf in again.unchanged} == {sf.path.name for sf in sources}

    # mutate one doc, drop another
    (armance / "docs" / "auth" / "rfc.md").write_text("# Auth RFC\n\nupdated", encoding="utf-8")
    (armance / "docs" / "stray.md").unlink()
    new_sources = scan_sources(armance)
    diff = diff_sources(new_sources, manifest)
    added_names = {sf.path.name for sf in diff.added}
    assert "rfc.md" in added_names
    assert any(p.name == "stray.md" for p in diff.removed)


def test_chunk_text_under_cap_returns_single() -> None:
    chunks = chunk_text("hello world", chunk_max_tokens=4000)
    assert chunks == ["hello world"]


def test_chunk_text_splits_on_paragraph_when_over_cap() -> None:
    para = ("word " * 200).strip()
    text = "\n\n".join([para] * 10)
    chunks = chunk_text(text, chunk_max_tokens=300)
    assert len(chunks) > 1
    # every chunk fits the cap
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    for c in chunks:
        assert len(enc.encode(c)) <= 300


def test_chunk_text_hard_splits_oversized_paragraph() -> None:
    big = " ".join(["lorem"] * 5000)
    chunks = chunk_text(big, chunk_max_tokens=200)
    assert len(chunks) > 1


def test_next_layer_version_increments(tmp_path: Path) -> None:
    ctx_dir = tmp_path / "context"
    ctx_dir.mkdir()
    (ctx_dir / "L0_v1.md").write_text("v1", encoding="utf-8")
    (ctx_dir / "L0_v3.md").write_text("v3", encoding="utf-8")
    assert next_layer_version(ctx_dir, "L0") == 4


@pytest.mark.asyncio
async def test_write_context_layers_produces_l0_l1_l2(tmp_path: Path) -> None:
    armance = _setup_armance(tmp_path)
    sources = scan_sources(armance)

    async def fake_writer(layer, srcs):
        return f"{layer}: {len(srcs)} sources"

    result = await write_context_layers(armance, sources, writer=fake_writer)

    # Spec path: context/L0/v001_<date>_context.md
    assert result.l0_path.name.startswith("v001_")
    assert result.l0_path.name.endswith("_context.md")
    assert result.l0_path.read_text(encoding="utf-8").startswith("L0: ")
    themes = {p.name.split("_")[1] for p in result.l1_paths}
    assert "auth" in themes
    assert "backend" in themes
    assert "general" in themes
    assert any("L2_auth_" in p.name for p in result.l2_paths)
    assert result.manifest_path is not None and result.manifest_path.exists()
    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert all("hash" in v for v in payload.values())


def test_load_context_empty_dir_returns_empty(tmp_path: Path) -> None:
    armance = tmp_path / ".armance"
    armance.mkdir(parents=True)
    ctx_dir = armance / "context"
    ctx_dir.mkdir()
    assert load_context(armance) == ""


def test_load_context_with_l0(tmp_path: Path) -> None:
    armance = tmp_path / ".armance"
    armance.mkdir(parents=True)
    ctx_dir = armance / "context"
    ctx_dir.mkdir()
    (ctx_dir / "L0_v1.md").write_text("l0 content", encoding="utf-8")
    result = load_context(armance)
    assert "## L0" in result
    assert "l0 content" in result


def test_load_context_with_l0_and_l1(tmp_path: Path) -> None:
    armance = tmp_path / ".armance"
    armance.mkdir(parents=True)
    ctx_dir = armance / "context"
    ctx_dir.mkdir()
    (ctx_dir / "L0_v1.md").write_text("l0", encoding="utf-8")
    (ctx_dir / "L1_backend_v1.md").write_text("backend stuff", encoding="utf-8")
    (ctx_dir / "L1_frontend_v1.md").write_text("frontend stuff", encoding="utf-8")
    result = load_context(armance)
    assert "## L0" in result
    assert "## L1 \u2014 backend" in result
    assert "backend stuff" in result
    assert "## L1 \u2014 frontend" in result
    assert "frontend stuff" in result


def test_load_context_max_level_filter(tmp_path: Path) -> None:
    armance = tmp_path / ".armance"
    armance.mkdir(parents=True)
    ctx_dir = armance / "context"
    ctx_dir.mkdir()
    (ctx_dir / "L0_v1.md").write_text("l0", encoding="utf-8")
    (ctx_dir / "L1_backend_v1.md").write_text("l1", encoding="utf-8")
    (ctx_dir / "L2_backend_foo_v1.md").write_text("l2", encoding="utf-8")
    # max_level=1 should include L0+L1 but not L2
    result = load_context(armance, max_level=1)
    assert "## L0" in result
    assert "## L1" in result
    assert "l2" not in result
    # max_level=2 should include L2
    result2 = load_context(armance, max_level=2)
    assert "## L2" in result2
    assert "l2" in result2


# ---------------------------------------------------------------------------
# context_with_rag (task 1.6)
# ---------------------------------------------------------------------------


def test_context_with_rag_returns_empty_when_no_docs(tmp_path: Path) -> None:
    from armance.storage.rag_index import context_with_rag

    root = tmp_path / ".armance"
    root.mkdir()
    result = context_with_rag(root, "any query")
    assert result == ""


def test_context_with_rag_returns_formatted_chunks(tmp_path: Path) -> None:
    from armance.storage.ingestion import sync_docs
    from armance.storage.rag_index import context_with_rag

    root = tmp_path / ".armance"
    docs = root / "docs"
    docs.mkdir(parents=True)
    (docs / "geo.txt").write_text("Paris is the capital of France.", encoding="utf-8")
    sync_docs(root)

    result = context_with_rag(root, "capital France")
    assert "Source: geo.txt p." in result
    assert "Paris" in result


# ---------------------------------------------------------------------------
# append_to_layer (task 4.4 / 1.6)
# ---------------------------------------------------------------------------


def test_append_to_layer_creates_file(tmp_path: Path) -> None:
    root = tmp_path / ".armance"
    path = append_to_layer(root, layer="L1", theme="checkpoint", text="User input here.")
    assert path.exists()
    assert path.read_text() == "User input here."
    assert "L1_checkpoint_v1" in path.name


def test_append_to_layer_increments_version(tmp_path: Path) -> None:
    root = tmp_path / ".armance"
    p1 = append_to_layer(root, theme="checkpoint", text="first")
    p2 = append_to_layer(root, theme="checkpoint", text="second")
    assert "v1" in p1.name
    assert "v2" in p2.name
