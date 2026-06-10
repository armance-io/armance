"""Armance — multi-agent strategic brain."""
from __future__ import annotations

try:  # single source of truth: pyproject [project] version
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("armance")
except Exception:  # running from a raw checkout without install
    __version__ = "0.0.0"
