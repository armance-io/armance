"""Skill base class — MCP-shaped metadata contract.

Every Skill subclass must declare:
  - description   : str   — human-readable purpose
  - input_schema  : dict  -- JSON Schema for the skill's arguments
  - output_schema : dict  -- JSON Schema for the skill's return value

Spec: docs/spec/18_command_nl_bridge.md § Skill contract (Invariant 3)
"""
from __future__ import annotations

from typing import Any


class Skill:
    """Abstract base for all Armance skills.

    Subclasses must override description, input_schema, and output_schema.
    """

    description: str = ""
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}
    output_schema: dict[str, Any] = {"type": "string"}
