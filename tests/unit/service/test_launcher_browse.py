"""Tests for the launcher's server-side folder browser (sub-feature 2).

Security-sensitive: ``/launcher/browse`` exposes the local filesystem. It must
stay confined to a root (the user's home by default), rejecting path-traversal
and symlink escapes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from armance.service import launcher_browse as br


def test_lists_immediate_subdirs(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "file.txt").write_text("x")

    result = br.browse(tmp_path, root=tmp_path)
    names = [d["name"] for d in result["dirs"]]
    assert names == ["a", "b"]  # sorted, dirs only (no file.txt)
    assert result["path"] == str(tmp_path.resolve())


def test_descend_into_subdir(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep").mkdir()
    result = br.browse(sub, root=tmp_path)
    assert [d["name"] for d in result["dirs"]] == ["deep"]


def test_traversal_above_root_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(br.BrowseError):
        br.browse(root / ".." / "..", root=root)


def test_absolute_escape_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(br.BrowseError):
        br.browse(Path("/etc"), root=root)


def test_symlink_escape_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "escape"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(br.BrowseError):
        br.browse(link, root=root)


def test_nonexistent_path_rejected(tmp_path: Path) -> None:
    with pytest.raises(br.BrowseError):
        br.browse(tmp_path / "nope", root=tmp_path)
