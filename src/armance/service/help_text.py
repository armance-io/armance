"""Service-layer command help text and formatting.

Decouples the command list from client/TUI structures. All strings are
pulled from the NLS catalogue (armance.nls) so the language switch
honours /help output.
"""
from __future__ import annotations

# Canonical command list. The actual one-line help text is fetched from
# the NLS catalogue under the `help_cmd.<name>` key, so translations live
# in fr.yaml / en.yaml and not in this file.
COMMAND_KEYS: list[str] = [
    "switch", "model", "effort", "save", "report", "judge", "export",
    "workflow", "task", "deliverable", "role", "library", "help", "quit",
]


def build_help_text() -> str:
    """Return formatted help string for all slash commands."""
    from armance.nls import t
    return "\n".join(t(f"help_cmd.{name}") for name in COMMAND_KEYS)


# Backward-compat: code that imported `COMMANDS` (a dict) historically
# expected {cmd_name: one_line_help}. Resolve from the NLS catalogue
# lazily via a dict-like view.
class _LazyCommandsMap:
    def __iter__(self):
        return iter(COMMAND_KEYS)

    def __contains__(self, key: str) -> bool:
        return key in COMMAND_KEYS

    def __len__(self) -> int:
        return len(COMMAND_KEYS)

    def __getitem__(self, key: str) -> str:
        from armance.nls import t
        if key not in COMMAND_KEYS:
            raise KeyError(key)
        return t(f"help_cmd.{key}")

    def keys(self):
        return list(COMMAND_KEYS)

    def values(self):
        return [self[k] for k in COMMAND_KEYS]

    def items(self):
        return [(k, self[k]) for k in COMMAND_KEYS]


COMMANDS = _LazyCommandsMap()
