"""``armance preset`` subcommand — list / show / apply domain preset packs.

Kept out of ``cli.py`` (file is at its LOC exception ceiling); ``main``
delegates here with the raw remaining argv.
"""
from __future__ import annotations

import sys
from pathlib import Path

USAGE = (
    "usage: armance preset {list|show <name>|apply <name>} [--root PATH]\n"
    "  list           list available presets (builtin + user packs)\n"
    "  show <name>    describe one preset (workflows, roles, knowledge, bench)\n"
    "  apply <name>   drop the preset's data into the current project"
)


def cmd_preset(argv: list[str], root: Path | None = None) -> int:
    from armance.service import preset_ops

    args = list(argv)
    if "--root" in args:
        idx = args.index("--root")
        try:
            root = Path(args[idx + 1])
        except IndexError:
            print("error: --root requires a path", file=sys.stderr)
            return 2
        del args[idx:idx + 2]

    action = args[0] if args else "list"
    if action in ("-h", "--help", "help"):
        print(USAGE)
        return 0

    if action == "list":
        print(preset_ops.format_preset_list(preset_ops.available_presets()))
        return 0

    if action in ("show", "apply"):
        if len(args) < 2:
            print(USAGE, file=sys.stderr)
            return 2
        name = args[1]
        preset = preset_ops.find_preset(name)
        if preset is None:
            known = ", ".join(p.name for p in preset_ops.available_presets()) or "(none)"
            print(f"unknown preset: {name} (known: {known})", file=sys.stderr)
            return 1
        if action == "show":
            print(preset_ops.format_preset_show(preset))
            return 0
        report = preset_ops.apply_preset(preset, root or Path.cwd())
        print(report.summary())
        return 0

    print(f"unknown preset command: {action}\n{USAGE}", file=sys.stderr)
    return 2
