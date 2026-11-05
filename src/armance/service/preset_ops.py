"""Apply domain preset packs to a project — pure data drop, no domain logic.

``apply_preset`` copies pack files where existing mechanisms already read
them:

- workflows → ``.armance/workflows/<name>.yaml`` (engine loads them as-is)
- roles + knowledge → ``.armance/docs/presets/<preset>/…`` (library scan
  picks them up; indexing stays an explicit ``/library index`` step so
  apply never touches the network)

Non-destructive by contract: an existing file with different content is
reported as a conflict and left untouched; identical content is a no-op.
Applying twice is therefore idempotent.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from armance import paths
from armance.core.models.preset import Preset, discover_presets
from armance.storage import paths as storage_paths

logger = logging.getLogger(__name__)


def builtin_presets_dir() -> Path:
    """Directory of presets bundled in the wheel (``armance/assets/presets``)."""
    return Path(str(resources.files("armance").joinpath("assets/presets")))


def user_presets_dir() -> Path:
    """Directory of user-dropped preset packs (global config dir)."""
    return paths.global_config_dir() / "presets"


def preset_search_dirs() -> list[Path]:
    """User packs first (they shadow builtins on name collision)."""
    return [user_presets_dir(), builtin_presets_dir()]


def available_presets() -> list[Preset]:
    return discover_presets(preset_search_dirs())


def find_preset(name: str) -> Preset | None:
    for preset in available_presets():
        if preset.name == name:
            return preset
    return None


@dataclass
class ApplyReport:
    """Outcome of one ``apply_preset`` call."""

    preset: str
    installed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"preset '{self.preset}' applied"]
        if self.installed:
            lines.append(f"  installed ({len(self.installed)}):")
            lines.extend(f"    + {p}" for p in self.installed)
        if self.unchanged:
            lines.append(f"  unchanged: {len(self.unchanged)}")
        if self.conflicts:
            lines.append(f"  conflicts kept untouched ({len(self.conflicts)}):")
            lines.extend(f"    ! {p}" for p in self.conflicts)
        lines.append(
            "  knowledge dropped under .armance/docs/ — run /library scan "
            "then /library index to make it searchable"
        )
        return "\n".join(lines)


def _copy_file(src: Path, dest: Path, rel: str, report: ApplyReport) -> None:
    content = src.read_text(encoding="utf-8")
    if dest.exists():
        if dest.read_text(encoding="utf-8") == content:
            report.unchanged.append(rel)
        else:
            report.conflicts.append(rel)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    report.installed.append(rel)


def apply_preset(preset: Preset, repo_root: Path) -> ApplyReport:
    """Drop the pack's data into ``<repo_root>/.armance``. Idempotent."""
    armance_root = storage_paths.armance_root(repo_root)
    report = ApplyReport(preset=preset.name)

    workflows_dir = storage_paths.workflows_dir(armance_root)
    for wf in preset.workflow_files():
        _copy_file(wf, workflows_dir / wf.name, f"workflows/{wf.name}", report)

    docs_base = storage_paths.docs_dir(armance_root) / "presets" / preset.name
    for doc in preset.knowledge_files():
        _copy_file(doc, docs_base / doc.name, f"docs/presets/{preset.name}/{doc.name}", report)
    for role in preset.role_files():
        _copy_file(
            role, docs_base / "roles" / role.name,
            f"docs/presets/{preset.name}/roles/{role.name}", report,
        )

    _write_marker(armance_root, preset)
    logger.info(
        "preset %s applied: %d installed, %d unchanged, %d conflicts",
        preset.name, len(report.installed), len(report.unchanged), len(report.conflicts),
    )
    return report


def _write_marker(armance_root: Path, preset: Preset) -> None:
    marker_dir = armance_root / "presets"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker = marker_dir / f"{preset.name}.json"
    marker.write_text(
        json.dumps(
            {
                "name": preset.name,
                "version": preset.manifest.version,
                "applied_at": datetime.now(tz=timezone.utc).isoformat(),
                "source": str(preset.root),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def format_preset_list(presets: list[Preset]) -> str:
    if not presets:
        return "no presets found (builtin dir empty, no user packs)"
    lines = ["available presets:"]
    for p in presets:
        title = f" — {p.manifest.title}" if p.manifest.title else ""
        lines.append(f"  {p.name} (v{p.manifest.version}, {p.manifest.language}){title}")
    return "\n".join(lines)


def format_preset_show(preset: Preset) -> str:
    m = preset.manifest
    lines = [
        f"{m.name} v{m.version} ({m.language})",
        m.title or "(no title)",
        "",
        m.description.strip() or "(no description)",
        "",
        f"workflows: {', '.join(p.stem for p in preset.workflow_files()) or '(none)'}",
        f"roles:     {', '.join(p.stem for p in preset.role_files()) or '(none)'}",
        f"knowledge: {', '.join(p.stem for p in preset.knowledge_files()) or '(none)'}",
        f"bench:     {'yes' if (preset.bench_dir / 'bench.yaml').is_file() else 'no'}",
    ]
    return "\n".join(lines)
