"""Env file operations for the web admin routes.

Reads and writes ``.env`` via the Storage ABC, preserving comments.
Validates key names against ``^[A-Z][A-Z0-9_]*$``.
Values are masked as ``sk-***…<last4>`` on list; full value only on write confirmation.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from armance.platform.storage import Storage

_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ENV_KEY = ".env"


class EnvKeyError(ValueError):
    """Raised when a key name fails validation."""


def _mask(value: str) -> str:
    """Return a masked version: ``sk-***…<last4>`` (min 4 chars exposed)."""
    last4 = value[-4:] if len(value) >= 4 else value
    return f"sk-***…{last4}"


def _parse_env(text: str) -> list[tuple[str, str | None, str]]:
    """Parse .env text into (key, value, raw_line) triples.

    Comment and blank lines have key=None.
    """
    result: list[tuple[str, str | None, str]] = []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            result.append(("", None, line))
            continue
        if "=" in stripped:
            k, _, v = stripped.partition("=")
            result.append((k.strip(), v.strip(), line))
        else:
            result.append(("", None, line))
    return result


async def list_secrets(storage: "Storage", reveal: bool = False) -> list[dict]:
    """Return masked or clear list of env entries: [{name, value, set}]."""
    if not await storage.exists(_ENV_KEY):
        return []
    text = await storage.read_text(_ENV_KEY)
    entries: list[dict] = []
    for key, value, _ in _parse_env(text):
        if key and _KEY_RE.match(key):
            is_base_url = key.endswith("_BASE_URL")
            is_masked = not (reveal or is_base_url)
            entries.append({
                "name": key,
                "value": (_mask(value) if is_masked else value) if value else "",
                "set": bool(value),
            })
    return entries


async def set_secret(storage: "Storage", name: str, value: str) -> None:
    """Write or overwrite *name* in .env, preserving other lines."""
    if not _KEY_RE.match(name):
        raise EnvKeyError(f"invalid key name: {name!r}")
    if any(c in value for c in "\r\n\x00"):
        raise EnvKeyError(f"value for {name!r} contains illegal control characters")

    text = await storage.read_text(_ENV_KEY) if await storage.exists(_ENV_KEY) else ""
    lines = _parse_env(text)

    found = False
    new_lines: list[str] = []
    for key, _val, raw in lines:
        if key == name:
            new_lines.append(f"{name}={value}\n")
            found = True
        else:
            new_lines.append(raw if raw.endswith("\n") else raw + "\n")

    if not found:
        new_lines.append(f"{name}={value}\n")

    await storage.write_text(_ENV_KEY, "".join(new_lines))


async def delete_secret(storage: "Storage", name: str) -> bool:
    """Remove *name* from .env. Returns True if the key was present."""
    if not _KEY_RE.match(name):
        raise EnvKeyError(f"invalid key name: {name!r}")

    if not await storage.exists(_ENV_KEY):
        return False

    text = await storage.read_text(_ENV_KEY)
    lines = _parse_env(text)

    new_lines: list[str] = []
    found = False
    for key, _val, raw in lines:
        if key == name:
            found = True
        else:
            new_lines.append(raw if raw.endswith("\n") else raw + "\n")

    if found:
        await storage.write_text(_ENV_KEY, "".join(new_lines))
    return found
