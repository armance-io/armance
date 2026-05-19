"""Armance TUI - Textual-based terminal user interface.

This package provides the Textual-based TUI for Armance.
The legacy Rich/prompt_toolkit implementation is in tui.py and tui_loop.py.
"""
from __future__ import annotations

try:
    from armance.client.tui.app import ArmanceApp
except ImportError:
    ArmanceApp = None

__all__ = ["ArmanceApp"] if ArmanceApp else []
