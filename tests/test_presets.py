"""Preset packs — loader, discovery, apply idempotence, CLI."""
from __future__ import annotations

from pathlib import Path

import pytest

from armance.core.models.preset import (
    PresetError,
    discover_presets,
    load_preset,
)
from armance.service import preset_ops


def make_pack(base: Path, name: str = "demo", version: str = "0.1.0") -> Path:
    root = base / name
    (root / "workflows").mkdir(parents=True)
    (root / "knowledge").mkdir()
    (root / "roles").mkdir()
    (root / "preset.yaml").write_text(
        f"name: {name}\ntitle: Demo pack\ndescription: test pack\n"
        f"language: fr\nversion: {version}\n",
        encoding="utf-8",
    )
    (root / "workflows" / "wf-a.yaml").write_text(
        "name: wf-a\nsteps:\n  - id: s1\n    kind: task\n    role: r\n"
        "    prompt_template: '{{user_prompt}}'\n",
        encoding="utf-8",
    )
    (root / "knowledge" / "domain.md").write_text("# Domaine\n", encoding="utf-8")
    (root / "roles" / "expert.md").write_text("# Expert\n", encoding="utf-8")
    return root


class TestLoader:
    def test_load_ok(self, tmp_path: Path) -> None:
        preset = load_preset(make_pack(tmp_path))
        assert preset.name == "demo"
        assert preset.manifest.language == "fr"
        assert [p.name for p in preset.workflow_files()] == ["wf-a.yaml"]
        assert [p.name for p in preset.knowledge_files()] == ["domain.md"]
        assert [p.name for p in preset.role_files()] == ["expert.md"]

    def test_missing_manifest(self, tmp_path: Path) -> None:
        with pytest.raises(PresetError, match="missing preset.yaml"):
            load_preset(tmp_path)

    def test_bad_manifest(self, tmp_path: Path) -> None:
        root = tmp_path / "bad"
        root.mkdir()
        (root / "preset.yaml").write_text("title: no name\n", encoding="utf-8")
        with pytest.raises(PresetError, match="invalid manifest"):
            load_preset(root)

    def test_discover_shadowing(self, tmp_path: Path) -> None:
        user = tmp_path / "user"
        builtin = tmp_path / "builtin"
        make_pack(user, "demo", version="9.9.9")
        make_pack(builtin, "demo", version="0.1.0")
        make_pack(builtin, "other")
        presets = discover_presets([user, builtin])
        by_name = {p.name: p for p in presets}
        assert set(by_name) == {"demo", "other"}
        assert by_name["demo"].manifest.version == "9.9.9"

    def test_discover_skips_broken(self, tmp_path: Path) -> None:
        base = tmp_path / "b"
        make_pack(base, "good")
        broken = base / "broken"
        broken.mkdir()
        (broken / "preset.yaml").write_text(":\n  - [", encoding="utf-8")
        assert [p.name for p in discover_presets([base])] == ["good"]


class TestApply:
    def test_apply_then_reapply_idempotent(self, tmp_path: Path) -> None:
        preset = load_preset(make_pack(tmp_path / "packs"))
        project = tmp_path / "project"
        project.mkdir()

        report = preset_ops.apply_preset(preset, project)
        assert sorted(report.installed) == [
            "docs/presets/demo/domain.md",
            "docs/presets/demo/roles/expert.md",
            "workflows/wf-a.yaml",
        ]
        assert (project / ".armance" / "workflows" / "wf-a.yaml").is_file()
        assert (project / ".armance" / "docs" / "presets" / "demo" / "domain.md").is_file()
        assert (project / ".armance" / "presets" / "demo.json").is_file()

        again = preset_ops.apply_preset(preset, project)
        assert again.installed == []
        assert len(again.unchanged) == 3
        assert again.conflicts == []

    def test_apply_never_overwrites(self, tmp_path: Path) -> None:
        preset = load_preset(make_pack(tmp_path / "packs"))
        project = tmp_path / "project"
        wf = project / ".armance" / "workflows" / "wf-a.yaml"
        wf.parent.mkdir(parents=True)
        wf.write_text("name: user-tuned\nsteps: []\n", encoding="utf-8")

        report = preset_ops.apply_preset(preset, project)
        assert "workflows/wf-a.yaml" in report.conflicts
        assert wf.read_text(encoding="utf-8").startswith("name: user-tuned")
        assert "conflicts" in report.summary()


class TestCli:
    @pytest.fixture()
    def fake_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        packs = tmp_path / "packs"
        make_pack(packs, "demo")
        monkeypatch.setattr(preset_ops, "preset_search_dirs", lambda: [packs])
        return tmp_path

    def test_list(self, fake_dirs: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from armance.cli_preset import cmd_preset

        assert cmd_preset(["list"]) == 0
        assert "demo" in capsys.readouterr().out

    def test_show_unknown(self, fake_dirs: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from armance.cli_preset import cmd_preset

        assert cmd_preset(["show", "nope"]) == 1
        assert "unknown preset" in capsys.readouterr().err

    def test_apply_with_root(self, fake_dirs: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from armance.cli_preset import cmd_preset

        project = fake_dirs / "proj"
        project.mkdir()
        assert cmd_preset(["apply", "demo", "--root", str(project)]) == 0
        assert (project / ".armance" / "workflows" / "wf-a.yaml").is_file()
        assert "applied" in capsys.readouterr().out

    def test_main_dispatch(self, fake_dirs: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from armance.cli import main

        assert main(["preset", "list"]) == 0
        assert "demo" in capsys.readouterr().out


class TestBuiltinDir:
    def test_builtin_dir_resolves_inside_package(self) -> None:
        path = preset_ops.builtin_presets_dir()
        assert path.parts[-2:] == ("assets", "presets")
