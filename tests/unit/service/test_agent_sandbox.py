"""Unit tests for agent_sandbox scrub layers."""

from __future__ import annotations

from armance.service.agent_sandbox import (
    normalise_hallucinated_tool_calls,
    scrub_reply,
    strip_hallucinated_tool_calls,
    strip_unauthorised_execute_tags,
)


def test_normalise_tool_call_to_execute() -> None:
    reply = "verrouillé.\n<tool_call>save"
    out = normalise_hallucinated_tool_calls(reply, allow={"save"})
    assert "[EXECUTE:/save]" in out


def test_normalise_tool_call_not_in_allowlist_left_for_strip() -> None:
    reply = "<tool_call>recruit"
    out = normalise_hallucinated_tool_calls(reply, allow={"save"})
    assert "[EXECUTE:" not in out
    assert "<tool_call>" in out


def test_strip_drops_tool_call_after_normalise_pass() -> None:
    raw = "<tool_call>read</tool_call>"
    out = strip_hallucinated_tool_calls(raw)
    assert "<tool_call>" not in out


def test_scrub_reply_armance_save_path() -> None:
    """End-to-end: Armance's `<tool_call>save` becomes a runnable [EXECUTE:/save]."""
    raw = "Contexte verrouillé.\n<tool_call>save"
    out = scrub_reply(raw, agent_role="armance")
    assert "[EXECUTE:/save]" in out
    assert "<tool_call>" not in out


def test_scrub_strips_unauthorised_tag_for_kim() -> None:
    raw = "Going to recruit. [EXECUTE:/recruit]"
    out = scrub_reply(raw, agent_role="kim")
    assert "[EXECUTE:/recruit]" not in out


def test_strip_unauthorised_tags_keeps_allowed() -> None:
    raw = "Designing now. [EXECUTE:/workflow-design]"
    out = strip_unauthorised_execute_tags(raw, agent_role="kim")
    assert "[EXECUTE:/workflow-design]" in out
