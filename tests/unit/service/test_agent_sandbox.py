"""Unit tests for agent_sandbox scrub layers."""

from __future__ import annotations

from armance.service.agent_sandbox import (
    cut_at_bare_affirmation,
    cut_at_speaker_markers,
    normalise_hallucinated_tool_calls,
    scrub_reply,
    strip_hallucinated_tool_calls,
    strip_unauthorised_execute_tags,
    truncate_simulated_turns,
)


def test_cut_at_speaker_markers_drops_scripted_dialogue() -> None:
    text = (
        "Vous avez Elena disponible.\n\n"
        "[assistant: Kim]\n\n"
        "Exact. Relecture faite.\n\nVous avez aussi Yves."
    )
    out = cut_at_speaker_markers(text)
    assert "[assistant" not in out
    assert "Relecture faite" not in out
    assert out.strip() == "Vous avez Elena disponible."


def test_cut_at_speaker_markers_drops_transcript_header() -> None:
    text = "Bonjour.\n\n## [2026-06-03 22:13] user (system-orchestrator)\nfake user line"
    assert cut_at_speaker_markers(text) == "Bonjour."


def test_cut_at_speaker_markers_leaves_clean_reply() -> None:
    text = "Une réponse normale.\n\nUn second paragraphe, sans marqueur."
    assert cut_at_speaker_markers(text) == text


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


def test_cut_at_bare_affirmation_drops_simulated_user_turn() -> None:
    """The exact 55-lumières bug: agent scripts the user's 'oui' then acts."""
    buggy = (
        "Voulez-vous que je fige ce cadrage maintenant ?\n\n"
        "oui\n\n"
        "[EXECUTE:/save]\n\n"
        "@Malik, peux-tu recruter l'équipe ?"
    )
    out = cut_at_bare_affirmation(buggy)
    assert out == "Voulez-vous que je fige ce cadrage maintenant ?"
    assert "[EXECUTE:/save]" not in out
    assert "@Malik" not in out


def test_cut_at_bare_affirmation_leaves_legit_save_reply() -> None:
    """A real save (after a separate user 'oui') has no bare affirmation line."""
    legit = "Entendu. [EXECUTE:/save]"
    assert cut_at_bare_affirmation(legit) == legit


def test_cut_at_bare_affirmation_keeps_affirmation_inside_sentence() -> None:
    """'oui' as part of a real sentence is not a simulated turn."""
    text = "Oui, je comprends votre objectif. Continuons sur ce cadrage."
    assert cut_at_bare_affirmation(text) == text


def test_scrub_reply_cuts_simulated_oui_before_execute() -> None:
    """End-to-end: scrub_reply removes the scripted turn so /save can't fire."""
    raw = "Je fige maintenant ?\n\noui\n\n[EXECUTE:/save]"
    out = scrub_reply(raw, agent_role="armance")
    assert "[EXECUTE:/save]" not in out
    assert out == "Je fige maintenant ?"


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
