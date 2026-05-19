"""Armance save-tag safety nets — exercise the explicit-consent gate logic
without touching the network. Mirrors the block in HostAgentService.dialogue.
"""
from __future__ import annotations


def _post_process(user_text: str, reply: str) -> str:
    user_low = user_text.strip().lower()
    explicit_save_words = (
        "verrouille", "verrouiller", "sauve", "sauvegarde", "save",
        "save it", "freeze", "lock",
    )
    user_explicit_save = (
        user_low in {
            "oui verrouille", "oui sauve", "verrouille", "sauvegarde", "save",
            "save it", "freeze it", "lock it", "go save", "on sauve",
            "on sauve ce contexte", "oui sauvegarde", "oui save",
        }
        or any(w in user_low for w in explicit_save_words)
    )
    announce_words = (
        "verrouillé", "verrouille", "sauvegardé", "sauvegarde",
        "contexte sauvegardé", "context locked", "context saved",
    )
    llm_announces_save = any(w in reply.lower() for w in announce_words)

    if (
        "[EXECUTE:/save]" not in reply
        and user_explicit_save
        and llm_announces_save
    ):
        reply = reply.rstrip() + "\n\n[EXECUTE:/save]"

    if "[EXECUTE:/save]" in reply and not user_explicit_save:
        reply = reply.replace("[EXECUTE:/save]", "").strip()
        if not reply:
            reply = (
                "Avant de verrouiller ce contexte, je veux m'assurer que tu "
                "valides bien : souhaites-tu que je le sauvegarde maintenant ?"
            )
        else:
            reply += (
                "\n\nSouhaites-tu que je verrouille / sauvegarde ce "
                "contexte maintenant ?"
            )
    return reply


def test_strips_save_tag_when_user_did_not_consent() -> None:
    """User confirms the summary but doesn't ask to save → tag stripped, re-ask."""
    out = _post_process(
        "C'est ca. J'aimerais commencer par réfléchir au contenu.",
        "[EXECUTE:/save]",
    )
    assert "[EXECUTE:/save]" not in out
    assert "sauvegarde" in out.lower() or "verrouille" in out.lower()


def test_keeps_save_tag_when_user_explicitly_asks() -> None:
    out = _post_process(
        "oui, sauvegarde le contexte",
        "Très bien.\n[EXECUTE:/save]",
    )
    assert "[EXECUTE:/save]" in out


def test_injects_tag_when_announce_but_no_tag() -> None:
    out = _post_process(
        "verrouille s'il te plait",
        "Contexte verrouillé.",
    )
    assert "[EXECUTE:/save]" in out


def test_ambiguous_oui_does_not_save() -> None:
    """Bare 'oui' confirming a summary is not a save consent."""
    out = _post_process("oui", "[EXECUTE:/save]")
    assert "[EXECUTE:/save]" not in out
