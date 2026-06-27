"""Export latest L0 + roadmap to claude / opencode / cline / roo targets.

Each target writes a small handoff file that points at the live Armance
artifacts under .armance/context/ and lists the main TUI commands so a
downstream code agent (Claude Code, Cline, Cursor, Roo Code) knows
where the strategic context lives.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"_v(\d+)\.md$")
_SPEC_VERSION_RE = re.compile(r"^v(\d+)_")

TARGETS = ("claude", "opencode", "cline", "roo")
TARGET_PATHS: dict[str, str] = {
    "claude": "CLAUDE.md",
    "opencode": "AGENTS.md",
    "cline": ".clinerules",
    "roo": ".roo/rules.md",
}


@dataclass(slots=True)
class ExportContext:
    l0_path: Path | None
    roadmap_path: Path | None


def _latest(directory: Path, prefix: str) -> Path | None:
    """Find latest versioned file for a prefix.

    Supports:
    - Spec subdir format: directory/<prefix>/v<NNN>_*.md  (for L0)
    - Legacy flat format: directory/<prefix>_v<N>.md
    """
    if not directory.exists():
        return None

    best: tuple[int, Path] | None = None

    # Try spec subdir first (e.g. context/L0/v001_date_slug.md)
    subdir = directory / prefix
    if subdir.exists():
        for path in subdir.glob("v*.md"):
            m = _SPEC_VERSION_RE.match(path.name)
            if m:
                n = int(m.group(1))
                if best is None or n > best[0]:
                    best = (n, path)
        if best is not None:
            return best[1]

    # Fall back to legacy flat format
    for path in directory.glob(f"{prefix}_v*.md"):
        m = _VERSION_RE.search(path.name)
        if not m:
            continue
        n = int(m.group(1))
        if best is None or n > best[0]:
            best = (n, path)
    return best[1] if best else None


def collect_export_context(armance_root: Path) -> ExportContext:
    context_dir = armance_root / "context"
    return ExportContext(
        l0_path=_latest(context_dir, "L0"),
        roadmap_path=_latest(context_dir, "roadmap"),
    )


def render_target(target: str, ctx: ExportContext) -> str:
    if target not in TARGET_PATHS:
        raise ValueError(f"unknown export target: {target}")

    title = {
        "claude": "Armance strategic context for Claude Code",
        "opencode": "Armance strategic context for OpenCode",
        "cline": "Armance strategic context for Cline",
        "roo": "Armance strategic context for Roo Code",
    }[target]

    lines = [f"# {title}", ""]
    lines.append("Armance maintains the strategic plan under `.armance/`.")
    lines.append("Read these before touching code:")
    if ctx.l0_path is not None:
        lines.append(f"- L0 summary: `{ctx.l0_path.as_posix()}`")
    if ctx.roadmap_path is not None:
        lines.append(f"- Roadmap: `{ctx.roadmap_path.as_posix()}`")
    lines.append("- Reports: `.armance/reports/<role>/<agent>_v<N>.md`")
    lines.append("- Judge verdicts: `.armance/judge/judge_v<N>.md`")
    lines.append("")
    lines.append("## Armance commands")
    lines.append("- `armance run` — open the TUI")
    lines.append("- `/task <role> <prompt>` — single agent run")
    lines.append("- `/workflow run <name>` — execute a YAML workflow")
    lines.append("- `/judge @file …` — run the chameleon judge")
    lines.append(f"- `/export {target}` — refresh this file")
    lines.append("")
    return "\n".join(lines)


def export_target(repo_root: Path, target: str, *, armance_root: Path | None = None) -> Path:
    armance_root = armance_root or (repo_root / ".armance")
    ctx = collect_export_context(armance_root)
    body = render_target(target, ctx)
    out = repo_root / TARGET_PATHS[target]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    return out


def export_all(repo_root: Path, *, armance_root: Path | None = None) -> list[Path]:
    return [export_target(repo_root, t, armance_root=armance_root) for t in TARGETS]
