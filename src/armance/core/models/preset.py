"""Domain preset pack — manifest, layout, loader.

A preset is a pure-data directory. The engine never knows about domains;
``preset apply`` only drops files where existing mechanisms already read
them (workflows dir, library docs). Layout:

    <preset_root>/
        preset.yaml          # manifest (name, title, description, ...)
        workflows/*.yaml     # workflow YAML files (engine schema)
        roles/*.md           # suggested role sheets (become library docs)
        knowledge/*.md       # domain knowledge (become library docs)
        bench/               # replayable benchmark cases (bench.yaml, cases/)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml
from pydantic import BaseModel, Field, ValidationError

MANIFEST_FILENAME = "preset.yaml"


class PresetError(ValueError):
    """Raised when a preset directory is missing or malformed."""


class PresetManifest(BaseModel):
    """Parsed ``preset.yaml``."""

    name: str
    title: str = ""
    description: str = ""
    language: str = "en"
    version: str = "0.1.0"
    tags: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class Preset:
    """A preset pack resolved on disk."""

    root: Path
    manifest: PresetManifest

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def workflows_dir(self) -> Path:
        return self.root / "workflows"

    @property
    def roles_dir(self) -> Path:
        return self.root / "roles"

    @property
    def knowledge_dir(self) -> Path:
        return self.root / "knowledge"

    @property
    def bench_dir(self) -> Path:
        return self.root / "bench"

    def workflow_files(self) -> list[Path]:
        return _sorted_files(self.workflows_dir, "*.yaml")

    def role_files(self) -> list[Path]:
        return _sorted_files(self.roles_dir, "*.md")

    def knowledge_files(self) -> list[Path]:
        return _sorted_files(self.knowledge_dir, "*.md")


def _sorted_files(directory: Path, pattern: str) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob(pattern) if p.is_file())


def load_preset(root: Path) -> Preset:
    """Load a preset pack from ``root``. Raises PresetError if invalid."""
    manifest_path = root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise PresetError(f"not a preset (missing {MANIFEST_FILENAME}): {root}")
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PresetError(f"invalid YAML in {manifest_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PresetError(f"manifest must be a mapping: {manifest_path}")
    try:
        manifest = PresetManifest.model_validate(data)
    except ValidationError as exc:
        raise PresetError(f"invalid manifest {manifest_path}: {exc}") from exc
    return Preset(root=root, manifest=manifest)


def discover_presets(search_dirs: Iterable[Path]) -> list[Preset]:
    """Scan ``search_dirs`` for preset packs.

    Earlier directories win on name collision (user packs shadow builtins).
    Malformed packs are skipped silently — discovery must never crash a
    listing because one third-party folder is broken.
    """
    seen: dict[str, Preset] = {}
    for base in search_dirs:
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not (child / MANIFEST_FILENAME).is_file():
                continue
            try:
                preset = load_preset(child)
            except PresetError:
                continue
            seen.setdefault(preset.name, preset)
    return sorted(seen.values(), key=lambda p: p.name)
