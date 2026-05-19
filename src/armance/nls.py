"""Natural Language Support (NLS) — single source of truth for user-facing strings.

HARD CONSTRAINT: no user-facing string may be hardcoded in Python code.
Every message the user sees MUST come from this module via `t(key, **kwargs)`.

Catalogues live in `src/armance/nls/<lang>.yaml`. English (`en.yaml`) is the
master catalogue. Other languages fall back to English for missing keys.

Usage:

    from armance.nls import t
    msg = t("ingest.success", indexed=2, skipped=1)

The active language is resolved in this order:
    1. explicit `lang=` arg
    2. `set_language(lang)` global
    3. fallback: "en"
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_MASTER_LANG = "en"
_SUPPORTED_LANGS = {"en", "fr", "es", "de", "zh", "ja"}
_NLS_DIR = Path(__file__).parent / "nls_catalogues"

# Cache: lang -> flat key -> string
_catalogue: dict[str, dict[str, str]] = {}
_active_lang: str = _MASTER_LANG


def _flatten(d: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested YAML dict into dotted keys: {a: {b: x}} -> {'a.b': 'x'}."""
    out: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = str(v)
    return out


def _load_lang(lang: str) -> dict[str, str]:
    if lang in _catalogue:
        return _catalogue[lang]
    path = _NLS_DIR / f"{lang}.yaml"
    if not path.exists():
        logger.warning("NLS file missing for lang=%s at %s", lang, path)
        _catalogue[lang] = {}
        return _catalogue[lang]
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        _catalogue[lang] = _flatten(raw)
    except Exception as exc:
        logger.exception("failed to load NLS for %s: %s", lang, exc)
        _catalogue[lang] = {}
    return _catalogue[lang]


def set_language(lang: str) -> None:
    """Set the active language globally."""
    global _active_lang
    if lang not in _SUPPORTED_LANGS:
        logger.warning("unsupported language %r, falling back to %s", lang, _MASTER_LANG)
        lang = _MASTER_LANG
    _active_lang = lang
    _load_lang(lang)


def get_language() -> str:
    return _active_lang


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    """Translate a key, formatting with kwargs.

    Falls back to the master language (en) if the key is missing in the
    active language. If still missing, returns the key itself (visible
    sentinel so devs notice).
    """
    target = lang or _active_lang
    cat = _load_lang(target)
    msg = cat.get(key)
    if msg is None and target != _MASTER_LANG:
        msg = _load_lang(_MASTER_LANG).get(key)
    if msg is None:
        logger.warning("NLS key missing: %r", key)
        return f"!!{key}!!"
    if kwargs:
        try:
            return msg.format(**kwargs)
        except KeyError as exc:
            logger.warning("NLS format missing arg %s for key %r", exc, key)
            return msg
    return msg
