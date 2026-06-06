"""Web access-token / password resolution (Epic S · security gate).

Resolution order for the web interface secret (SEC1-SEC2):

1. ``ARMANCE_WEB_PASSWORD`` environment variable.
2. ``config.web.password`` from .armance/config.yaml.
3. A lazily-generated, process-stable random token (32 hex chars).

This module is pure (no FastAPI) so it stays in the service layer; the
transport gate in ``armance.web.backend`` consumes it.
"""
from __future__ import annotations

import os
import secrets

from armance.config import Config

_ENV_VAR = "ARMANCE_WEB_PASSWORD"

# Process-lifetime cache for the auto-generated token. Generated once on
# first use so the printed startup URL and the live gate agree for the
# whole server run.
_cached_token: str | None = None


def reset_web_secret_cache() -> None:
    """Drop the cached auto-generated token (test helper)."""
    global _cached_token
    _cached_token = None


def _configured_secret(config: Config) -> str | None:
    """Return an explicitly-configured secret (env or config), or None."""
    env = os.environ.get(_ENV_VAR)
    if env:
        return env
    if config.web.password:
        return config.web.password
    return None


def resolve_web_secret(config: Config) -> str:
    """Resolve the active web secret, generating a token if none configured."""
    global _cached_token
    explicit = _configured_secret(config)
    if explicit is not None:
        return explicit
    if _cached_token is None:
        _cached_token = secrets.token_hex(16)  # 32 hex characters
    return _cached_token


def was_auto_generated(config: Config) -> bool:
    """True when the secret is the transient token, not an explicit value."""
    return _configured_secret(config) is None


def check_web_secret(config: Config, candidate: str | None) -> bool:
    """Constant-time comparison of *candidate* against the active secret.

    Uses ``secrets.compare_digest`` to avoid a timing side-channel.
    """
    if not candidate:
        return False
    expected = resolve_web_secret(config)
    return secrets.compare_digest(candidate, expected)
