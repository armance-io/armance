"""Malik chat safety nets — verify the YAML-without-tag and dismiss filters."""
from __future__ import annotations

import pytest

from armance.service.chat_handlers.malik import (
    _handle_dismiss_all,
    _inject_recruit_tag_if_yaml_only,
)


def test_inject_recruit_tag_when_user_asks_to_recruit() -> None:
    reply = (
        "Voici l'équipe complète :\n\n"
        "```yaml\n"
        "agents:\n"
        "  - name: Alex\n"
        "    domain: historian\n"
        "    provider: openrouter\n"
        "    model: free\n"
        "```\n"
    )
    out = _inject_recruit_tag_if_yaml_only(reply, "Recrute les, vas y")
    assert "[EXECUTE:/recruit]" in out


def test_no_inject_when_tag_already_present() -> None:
    reply = "[EXECUTE:/recruit]\nagents:\n  - name: A\n"
    out = _inject_recruit_tag_if_yaml_only(reply, "go")
    assert out.count("[EXECUTE:/recruit]") == 1


def test_no_inject_when_user_did_not_ask() -> None:
    reply = "```yaml\nagents:\n  - name: A\n    domain: x\n```"
    out = _inject_recruit_tag_if_yaml_only(reply, "Peux-tu m'expliquer ce rôle ?")
    assert "[EXECUTE:/recruit]" not in out


def test_no_inject_when_no_yaml() -> None:
    reply = "Salut, voici une réponse en prose."
    out = _inject_recruit_tag_if_yaml_only(reply, "recrute Alex")
    assert "[EXECUTE:/recruit]" not in out


def test_dismiss_all_skips_underscore_prefixed_files(tmp_path) -> None:
    """`_armance_concepts` and other underscore-prefixed files are internal
    assets, not user-recruited agents. Dismiss-all must skip them."""
    from armance.service.loop_context import LoopContext

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "system-hr.md").write_text("system")
    (agents_dir / "_armance_concepts.md").write_text("internal")
    (agents_dir / "alex.md").write_text("user agent")

    class _FakeSession:
        def __init__(self):
            self.metadata = {}

        def save(self):
            pass

    ctx = LoopContext.__new__(LoopContext)
    ctx.armance_root = tmp_path
    ctx.agents = []
    ctx.session = _FakeSession()

    reply_in = "[EXECUTE:/dismiss-all]"
    reply = _handle_dismiss_all(reply_in, ctx)

    assert (agents_dir / "system-hr.md").exists()
    assert (agents_dir / "_armance_concepts.md").exists()
    assert not (agents_dir / "alex.md").exists()
    assert "alex" in reply
    assert "_armance_concepts" not in reply


def test_dismiss_all_prunes_registry_entries(tmp_path) -> None:
    """Registry entries for dismissed agents must be removed too.
    Also prunes orphan staff-named entries (e.g. legacy Astrid · host)
    that have no corresponding .md file."""
    import json

    from armance.service.loop_context import LoopContext

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "system-hr.md").write_text("system")
    (agents_dir / "alex.md").write_text("user agent")
    # Pre-existing registry with: alex (live), zoe (orphan, no .md),
    # Astrid (rogue staff-named orphan), system-hr (must survive).
    registry = {
        "agents": [
            {"name": "alex", "role": "historian", "status": "active", "version": 1,
             "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
             "lead_for": []},
            {"name": "zoe", "role": "communicant", "status": "active", "version": 1,
             "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
             "lead_for": []},
            {"name": "Astrid", "role": "hote", "status": "active", "version": 1,
             "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
             "lead_for": []},
        ]
    }
    (agents_dir / "registry.json").write_text(json.dumps(registry))

    class _FakeSession:
        def __init__(self):
            self.metadata = {}

        def save(self):
            pass

    ctx = LoopContext.__new__(LoopContext)
    ctx.armance_root = tmp_path
    ctx.agents = []
    ctx.session = _FakeSession()

    _handle_dismiss_all("[EXECUTE:/dismiss-all]", ctx)

    final = json.loads((agents_dir / "registry.json").read_text())
    names = {a["name"] for a in final["agents"]}
    # alex deleted via .md unlink, zoe & Astrid pruned as orphans
    assert names == set()


@pytest.mark.asyncio
async def test_build_models_context_seeds_default_model_when_provider_undiscoverable(
    monkeypatch,
) -> None:
    """`custom-openai` cannot enumerate models; `_build_models_context` must
    surface `cfg.default_model` so Malik has at least one canonical id to
    propose instead of telling the user to add new providers."""
    from armance.service.chat_handlers.malik import _build_models_context

    class _Prov:
        def __init__(self, name): self.name = name

    class _Cfg:
        providers = [_Prov("custom-openai")]
        default_provider = "custom-openai"
        default_model = "Qwen/Qwen2.5-7B-Instruct"
        budget_effort = "free-first"

    class _Ctx:
        cfg = _Cfg()

    async def _fake_discover_all(cfg):
        return {"custom-openai": []}

    monkeypatch.setattr(
        "armance.providers.discovery.discover_all", _fake_discover_all,
    )
    out = await _build_models_context(_Ctx())
    assert "Qwen/Qwen2.5-7B-Instruct" in out
    assert "no models discovered" not in out


async def test_build_models_context_surfaces_declared_allowlist(
    monkeypatch,
) -> None:
    """Lot D (§3.4) — an allowlisted model absent from /models must reach
    Malik's context marked as user-declared, so he never rejects it and the
    user never has to re-teach it in NL."""
    from armance.service.chat_handlers.malik import _build_models_context

    class _Prov:
        def __init__(self, name, models=None):
            self.name = name
            self.models = models or []

    class _Cfg:
        providers = [_Prov("custom-openai:lab", models=["secret-72b"])]
        default_provider = "custom-openai:lab"
        default_model = ""
        budget_effort = "free-first"

    class _Ctx:
        cfg = _Cfg()

    async def _fake_discover_all(cfg):
        return {"custom-openai:lab": []}  # endpoint lists nothing

    monkeypatch.setattr(
        "armance.providers.discovery.discover_all", _fake_discover_all,
    )
    out = await _build_models_context(_Ctx())
    assert "secret-72b" in out
    assert "custom-openai:lab" in out
    assert "no models discovered" not in out
