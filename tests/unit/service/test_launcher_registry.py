"""Tests for the project registry (grandma launcher, sub-feature 2).

The registry is the global ``projects.json`` listing known project folders,
sorted by recency, with stale (missing-path) detection.
"""
from __future__ import annotations

from pathlib import Path

from armance import paths
from armance.service import launcher_registry as reg


def test_empty_registry_lists_nothing(isolate_global_config: Path) -> None:
    assert reg.list_projects() == []


def test_bump_adds_and_updates(isolate_global_config: Path, tmp_path: Path) -> None:
    proj = tmp_path / "alpha"
    proj.mkdir()

    reg.bump_project(proj)
    items = reg.list_projects()
    assert len(items) == 1
    assert items[0]["name"] == "alpha"
    assert items[0]["path"] == str(proj.resolve())
    assert items[0]["exists"] is True
    first_ts = items[0]["last_opened"]

    # Bumping again updates last_opened, does not duplicate.
    reg.bump_project(proj)
    items2 = reg.list_projects()
    assert len(items2) == 1
    assert items2[0]["last_opened"] >= first_ts


def test_sorted_by_recency(isolate_global_config: Path, tmp_path: Path) -> None:
    a = tmp_path / "a"
    a.mkdir()
    b = tmp_path / "b"
    b.mkdir()
    reg.bump_project(a)
    reg.bump_project(b)  # most recent
    names = [p["name"] for p in reg.list_projects()]
    assert names == ["b", "a"]


def test_stale_path_flagged_not_removed(isolate_global_config: Path, tmp_path: Path) -> None:
    proj = tmp_path / "gone"
    proj.mkdir()
    reg.bump_project(proj)
    proj.rmdir()  # path no longer exists

    items = reg.list_projects()
    assert len(items) == 1
    assert items[0]["exists"] is False


def test_registry_written_to_global(isolate_global_config: Path, tmp_path: Path) -> None:
    proj = tmp_path / "x"
    proj.mkdir()
    reg.bump_project(proj)
    assert paths.projects_registry_path().exists()
