"""Unit tests for agent_sandbox scrub layers."""

from __future__ import annotations

from armance.service.agent_sandbox import (
    normalise_hallucinated_tool_calls,
    scrub_reply,
    strip_hallucinated_tool_calls,
    strip_unauthorised_execute_tags,
    truncate_simulated_turns,
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


def test_truncate_simulated_turns_cuts_runaway_dialogue() -> None:
    """Model simulates Q/A pattern with multiple acknowledgements in one reply."""
    runaway = (
        "Cadrage clair.\n\n"
        "**Tension :** dossier ambigu.\n\n"
        "Quel frein ?\n\n"
        "C'était inachevé.\n\n"
        "Parfait. Chronologie nette.\n\n"
        "Question pivot ?\n\n"
        "Exact. Mandataire = socle.\n\n"
        "Stratégie ?\n\n"
        "[EXECUTE:/save]"
    )
    out = truncate_simulated_turns(runaway)
    assert "truncated" in out
    assert "[EXECUTE:/save]" not in out
    assert "Exact." not in out


def test_truncate_simulated_turns_leaves_single_ack_alone() -> None:
    normal = "Bien. Voilà ce qui m'intrigue: l'écart de quinze ans. Pouvez-vous préciser ?"
    assert truncate_simulated_turns(normal) == normal


def test_scrub_reply_invokes_simulated_turns_truncator() -> None:
    runaway = (
        "Cadrage clair.\n\nQ1 ?\n\nA1\n\nParfait.\n\nQ2 ?\n\nA2\n\nExact.\n\nQ3 ?"
    )
    out = scrub_reply(runaway, agent_role="armance")
    assert "Exact." not in out
    assert "truncated" in out
