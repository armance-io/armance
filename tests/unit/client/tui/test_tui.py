"""Tests for armance.client.tui.types (AgentStatus, COMMANDS, build_help_text).

tui.py was removed as part of the Rich → Textual migration.
Relevant functionality moved to:
  - armance.client.tui.types  (AgentStatus, COMMANDS, build_help_text)
  - armance.service.handlers  (dispatch, command handlers)
  - armance.client.tui.app    (Textual app entry point)
"""
from __future__ import annotations

from armance.client.tui.types import AgentStatus, COMMANDS, build_help_text


# ---------------------------------------------------------------------------
# AgentStatus (moved to types.py)
# ---------------------------------------------------------------------------

def test_agent_status_defaults() -> None:
    s = AgentStatus(name="alpha")
    assert s.state == "idle"
    assert s.tokens_in == 0
    assert s.tokens_out == 0
    assert s.cost_usd == 0.0


def test_agent_status_with_values() -> None:
    s = AgentStatus(name="beta", state="working", tokens_in=100, tokens_out=50, cost_usd=0.002)
    assert s.name == "beta"
    assert s.state == "working"
    assert s.tokens_in == 100


# ---------------------------------------------------------------------------
# COMMANDS / build_help_text (moved to types.py)
# ---------------------------------------------------------------------------

def test_commands_contains_expected_keys() -> None:
    assert "help" in COMMANDS
    assert "quit" in COMMANDS
    assert "task" in COMMANDS
    assert "workflow" in COMMANDS


def test_build_help_text_contains_slash_commands() -> None:
    text = build_help_text()
    assert "/help" in text
    assert "/quit" in text
    assert "/task" in text
