"""Per-language voice overlay appended to every agent system prompt.

Short directive — keeps prompts maintainable without translating bodies.
"""
from __future__ import annotations


_OVERLAYS: dict[str, str] = {
    "en": (
        "## OUTPUT LANGUAGE — STRICT\n"
        "Your entire reply MUST be in English. Do not switch to any other "
        "language even if the user writes in one; mirror their meaning, "
        "not their language. Match their register and tone. Always finish "
        "your sentences — never end with '...' or trail off mid-thought."
    ),
    "fr": (
        "## LANGUE DE RÉPONSE — STRICT\n"
        "Toute ta réponse DOIT être en français. Ne bascule jamais vers une "
        "autre langue, même si l'utilisateur en utilise une ; reformule "
        "son propos en français. Garde son ton et son registre. Termine "
        "toujours tes phrases — jamais de « … » ni de pensée tronquée."
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
