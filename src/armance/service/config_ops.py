"""Config validation helper for the web admin route.

Provides ``validate_config_patch`` which merges a partial dict onto an
existing ``Config`` and raises ``ConfigValidationError`` on unknown fields
or invalid values.
"""
from __future__ import annotations

from pydantic import ValidationError

from armance.config import Config


class ConfigValidationError(Exception):
    """Raised when a config patch is invalid.

    ``fields`` maps field name → human-readable reason.
    """

    def __init__(self, fields: dict[str, str]) -> None:
        self.fields = fields
        super().__init__(str(fields))


def validate_config_patch(current: Config, patch: dict) -> Config:
    """Merge *patch* onto *current* and return the updated Config.

    Raises ``ConfigValidationError`` listing every invalid field.
    """
    known_fields = set(Config.model_fields.keys())
    unknown = {k for k in patch if k not in known_fields}
    if unknown:
        raise ConfigValidationError({k: "unknown field" for k in unknown})

    merged = current.model_dump()
    merged.update(patch)

    try:
        return Config(**merged)
    except ValidationError as exc:
        fields: dict[str, str] = {}
        for error in exc.errors():
            loc = error.get("loc", ())
            key = str(loc[0]) if loc else "unknown"
            fields[key] = error.get("msg", "invalid value")
        raise ConfigValidationError(fields) from exc
