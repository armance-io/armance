"""Malik chat safety nets — verify the YAML-without-tag and dismiss filters."""
from __future__ import annotations

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
