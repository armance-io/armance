"""Per-language voice overlay appended to every agent system prompt.

Short directive — keeps prompts maintainable without translating bodies.
"""
from __future__ import annotations


_OVERLAYS: dict[str, str] = {
    "en": (
        "## OUTPUT LANGUAGE — STRICT, NON-NEGOTIABLE\n"
        "Your entire reply MUST be written in English — every sentence, "
        "every word. This is the configured project language and it does "
        "NOT change mid-session.\n"
        "- Do NOT switch to French (or any other language) even for a "
        "single phrase, quote, salutation, or technical term.\n"
        "- Do NOT switch if the user writes one message in another "
        "language — mirror their MEANING in English, never their language.\n"
        "- Do NOT switch if a system prompt section is written in French "
        "— those are instructions for you, not output samples.\n"
        "- The only allowed non-English fragments are proper nouns, "
        "filenames, and code/identifiers.\n"
        "Match the user's register and tone, in English. Always finish "
        "your sentences — never trail off with '...'."
    ),
    "fr": (
        "## LANGUE DE RÉPONSE — STRICT, NON NÉGOCIABLE\n"
        "Toute ta réponse DOIT être rédigée en français — chaque phrase, "
        "chaque mot. C'est la langue configurée du projet et elle ne "
        "change PAS en cours de session.\n"
        "- Ne bascule JAMAIS vers l'anglais (ni aucune autre langue), "
        "même pour une seule phrase, citation, salutation ou terme technique.\n"
        "- Ne bascule PAS si l'utilisateur écrit un message dans une autre "
        "langue — reformule son SENS en français, jamais sa langue.\n"
        "- Ne bascule PAS si une section du prompt système est rédigée en "
        "anglais — ce sont des instructions, pas des exemples de sortie.\n"
        "- Seuls les noms propres, fichiers et identifiants de code "
        "peuvent rester non francisés.\n"
        "Garde le ton et le registre de l'utilisateur, en français. "
        "Termine toujours tes phrases — jamais de « … »."
    ),
    "es": (
        "## IDIOMA DE RESPUESTA — ESTRICTO\n"
        "Toda tu respuesta DEBE estar en español. Nunca cambies a otro "
        "idioma, aunque el usuario lo use; reformula su mensaje en español. "
        "Conserva su registro y tono. Termina siempre tus frases — nunca "
        "uses « ... » ni dejes la idea a medias."
    ),
    "de": (
        "## ANTWORTSPRACHE — STRIKT\n"
        "Deine gesamte Antwort MUSS auf Deutsch sein. Wechsle nie in eine "
        "andere Sprache, auch wenn der Nutzer eine andere verwendet; gib "
        "seinen Inhalt auf Deutsch wieder. Halte Register und Ton bei. "
        "Beende stets deine Sätze — nie mit drei Punkten abbrechen."
    ),
    "zh": (
        "## 回复语言 — 严格\n"
        "你的整个回复必须使用中文。即使用户使用其他语言,也绝不切换;"
        "请用中文复述其意思,保持语气和风格一致。务必把每句话说完,"
        "绝不用「……」收尾或半途而废。"
    ),
    "ja": (
        "## 返答言語 — 厳守\n"
        "返答全体は必ず日本語で書くこと。ユーザーが他言語を使っても切り替えず、"
        "意味を日本語で言い直す。口調とレジスターを保つ。文は常に最後まで書き、"
        "「…」で中断したり言葉を濁したりしない。"
    ),
}


def voice_overlay(language: str | None) -> str:
    """Return the voice overlay block for the configured language."""
    code = (language or "en").lower()
    return _OVERLAYS.get(code, _OVERLAYS["en"])
