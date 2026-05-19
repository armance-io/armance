"""Per-language voice overlay appended to every agent system prompt.

Short directive — keeps prompts maintainable without translating bodies.
"""
from __future__ import annotations


_OVERLAYS: dict[str, str] = {
    "en": (
        "## Output language\n"
        "Reply in English. Match the user's register and tone."
    ),
    "fr": (
        "## Langue de réponse\n"
        "Réponds en français, peu importe la langue de l'utilisateur. "
        "Garde le ton et le registre du contexte."
    ),
    "es": (
        "## Idioma de respuesta\n"
        "Responde en español, sin importar el idioma del usuario. "
        "Conserva el registro y el tono."
    ),
    "de": (
        "## Antwortsprache\n"
        "Antworte auf Deutsch, unabhängig von der Sprache des Nutzers. "
        "Halte Register und Ton bei."
    ),
    "zh": (
        "## 回复语言\n"
        "无论用户使用哪种语言,请始终用中文回复,保持语气和风格一致。"
    ),
    "ja": (
        "## 返答言語\n"
        "ユーザーの言語に関係なく、常に日本語で返答してください。"
        "口調とレジスターを保ってください。"
    ),
}


def voice_overlay(language: str | None) -> str:
    """Return the voice overlay block for the configured language."""
    code = (language or "en").lower()
    return _OVERLAYS.get(code, _OVERLAYS["en"])
