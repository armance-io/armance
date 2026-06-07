"""Tests for global/local path resolution (grandma launcher foundation).

These cover the clean-break split: config / secrets / base-agents live in a
single GLOBAL directory (platformdirs); per-folder data lives under
``<folder>/.armance``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from armance import paths


def test_global_config_dir_uses_platformdirs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARMANCE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(
        paths.platformdirs, "user_config_dir", lambda app: f"/fake/cfg/{app}"
    )
    assert paths.global_config_dir() == Path("/fake/cfg/armance")


def test_global_config_dir_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARMANCE_CONFIG_DIR", str(tmp_path / "g"))
    assert paths.global_config_dir() == tmp_path / "g"


def test_global_config_and_env_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARMANCE_CONFIG_DIR", str(tmp_path / "g"))
    assert paths.global_config_path() == tmp_path / "g" / "config.yaml"
    assert paths.global_env_path() == tmp_path / "g" / ".env"
    assert paths.global_agents_dir() == tmp_path / "g" / "agents"


def test_projects_registry_path_is_global(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARMANCE_CONFIG_DIR", str(tmp_path / "g"))
    assert paths.projects_registry_path() == tmp_path / "g" / "projects.json"


def test_local_data_dir_is_per_folder(tmp_path: Path) -> None:
    folder = tmp_path / "my-project"
    assert paths.local_data_dir(folder) == folder / ".armance"
