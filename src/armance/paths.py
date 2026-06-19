"""Global vs local path resolution (grandma-launcher foundation).

Clean-break split:

- **Global** ``~/.config/armance`` (via :mod:`platformdirs`; ``%APPDATA%`` on
  Windows, ``~/Library/Application Support`` on macOS) holds **config,
  secrets, base agents, and the project registry** — one setup for the whole
  machine. Override with the ``ARMANCE_CONFIG_DIR`` env var (used by tests and
  power users).
- **Local** ``<folder>/.armance`` holds **data only** (docs, sessions, runs,
  context, exports …) for that project folder.

This module is a leaf: it must not import from ``armance.service`` /
``armance.client`` so it stays usable from every layer. The detailed *data*
layout under a given root lives in :mod:`armance.storage.paths`.
"""
from __future__ import annotations

import os
from pathlib import Path

import platformdirs

APP_NAME = "armance"
CONFIG_DIR_ENV = "ARMANCE_CONFIG_DIR"


def global_config_dir() -> Path:
    """Return the machine-wide Armance config directory.

    Honours ``ARMANCE_CONFIG_DIR`` when set, else ``platformdirs``'
    per-user config dir for the app.
    """
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override)
    # ``appauthor=False`` drops platformdirs' default author segment, which
    # otherwise defaults to the app name and yields a redundant
    # ``%LOCALAPPDATA%\armance\armance`` on Windows. POSIX (XDG) ignores the
    # author segment, so ``~/.config/armance`` is unchanged.
    return Path(platformdirs.user_config_dir(APP_NAME, appauthor=False))


def global_config_path() -> Path:
    """Path to the global ``config.yaml``."""
    return global_config_dir() / "config.yaml"


def global_env_path() -> Path:
    """Path to the global ``.env`` (provider secrets)."""
    return global_config_dir() / ".env"


def global_agents_dir() -> Path:
    """Directory holding the global base agents (Armance / Malik / Kim / …)."""
    return global_config_dir() / "agents"


def projects_registry_path() -> Path:
    """Path to the global project registry (``projects.json``)."""
    return global_config_dir() / "projects.json"


def local_data_dir(folder: Path) -> Path:
    """Return the per-folder data directory (``<folder>/.armance``)."""
    return folder / ".armance"
