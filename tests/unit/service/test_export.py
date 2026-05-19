"""Tests for armance.service.export."""
from __future__ import annotations

from pathlib import Path

import pytest

from armance.service.export import (
    TARGETS,
    TARGET_PATHS,
    collect_export_context,
    export_all,
    export_target,
)


def _seed_context(tmp_path: Path) -> Path:
    armance = tmp_path / ".armance"
    ctx_dir = armance / "context"
    ctx_dir.mkdir(parents=True)
    (ctx_dir / "L0_v1.md").write_text("v1", encoding="utf-8")
    (ctx_dir / "L0_v3.md").write_text("v3", encoding="utf-8")
    (ctx_dir / "roadmap_v2.md").write_text("road", encoding="utf-8")
    return armance


def test_collect_export_context_picks_latest(tmp_path: Path) -> None:
    armance = _seed_context(tmp_path)
    ctx = collect_export_context(armance)
    assert ctx.l0_path is not None and ctx.l0_path.name == "L0_v3.md"
    assert ctx.roadmap_path is not None and ctx.roadmap_path.name == "roadmap_v2.md"


def test_export_each_target_produces_file_with_refs(tmp_path: Path) -> None:
    _seed_context(tmp_path)
    for target in TARGETS:
        path = export_target(tmp_path, target)
        assert path == tmp_path / TARGET_PATHS[target]
        body = path.read_text(encoding="utf-8")
        assert "L0_v3.md" in body
        assert "roadmap_v2.md" in body
        assert f"/export {target}" in body


def test_export_all_writes_every_target(tmp_path: Path) -> None:
    _seed_context(tmp_path)
    paths = export_all(tmp_path)
    assert {p.name for p in paths} == {Path(TARGET_PATHS[t]).name for t in TARGETS}
    for target in TARGETS:
        out = tmp_path / TARGET_PATHS[target]
        assert out.exists()


def test_export_unknown_target_raises(tmp_path: Path) -> None:
    _seed_context(tmp_path)
    with pytest.raises(ValueError):
        export_target(tmp_path, "missing")


def test_export_handles_missing_context_gracefully(tmp_path: Path) -> None:
    (tmp_path / ".armance" / "context").mkdir(parents=True)
    out = export_target(tmp_path, "claude")
    body = out.read_text(encoding="utf-8")
    assert "Armance strategic context" in body
    assert "L0 summary" not in body
