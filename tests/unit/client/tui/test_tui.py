"""Tests for legacy armance.client.tui.tui — skipped, file deleted.

tui.py was removed as part of the Rich → Textual migration.
Relevant functionality moved to:
  - armance.client.tui.types  (AgentStatus, COMMANDS, build_help_text)
  - armance.service.handlers  (dispatch, command handlers)
  - armance.client.tui.app    (Textual app entry point)
"""
from __future__ import annotations

import pytest

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


# ---------------------------------------------------------------------------
# Legacy functions removed — skip tests that relied on them
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="parse_command removed with tui.py; use handlers dispatch instead")
def test_parse_command_legacy() -> None:
    pass


@pytest.mark.skip(reason="render_layout removed with tui.py; Textual widgets replace it")
def test_render_layout_legacy() -> None:
    pass


@pytest.mark.skip(reason="smoke_render removed with tui.py; Textual pilot tests replace it")
def test_smoke_render_legacy() -> None:
    pass


@pytest.mark.skip(reason="suggest_completions removed with tui.py; SuggestFromList in input.py")
def test_suggest_completions_legacy() -> None:
    pass
