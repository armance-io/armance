"""Clean-break: base staff resolves from the GLOBAL agents dir.

Regression guard for the grandma-launcher split — base meta-agents install
into the global config dir (``ensure_global_setup``), and the runtime must find
them there from any project folder. Local recruited specialists still win as an
override.
"""
from __future__ import annotations

from pathlib import Path

from armance import paths
from armance.config import Config, ProviderConfig, ensure_global_setup
from armance.service.chat_handlers.common import resolve_agent_path


def test_base_staff_resolves_from_global(isolate_global_config: Path, tmp_path: Path) -> None:
    cfg = Config(
        providers=[ProviderConfig(name="openrouter")],
        default_provider="openrouter",
        default_model="m",
    )
    ensure_global_setup(cfg)  # installs base agents into the GLOBAL dir

    project = tmp_path / "proj" / ".armance"
    project.mkdir(parents=True)  # a fresh project folder, no local base agents

    resolved = resolve_agent_path(project, "system-context")
    assert resolved is not None
    assert resolved == paths.global_agents_dir() / "system-context.md"


def test_local_specialist_overrides_global(isolate_global_config: Path, tmp_path: Path) -> None:
    cfg = Config(default_provider="openrouter", default_model="m")
    ensure_global_setup(cfg)

    project = tmp_path / "proj" / ".armance"
    (project / "agents").mkdir(parents=True)
    local_override = project / "agents" / "system-context.md"
    local_override.write_text("name: system-context\n", encoding="utf-8")

    resolved = resolve_agent_path(project, "system-context")
    assert resolved == local_override
