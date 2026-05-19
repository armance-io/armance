"""Kim chat safety nets — workflow YAML without [EXECUTE:/workflow-design]."""
from __future__ import annotations

from armance.service.chat_handlers.kim import _inject_design_tag_if_yaml_only


_YAML_BLOCK = (
    "Voici le workflow :\n\n"
    "```yaml\n"
    "name: dossier-historique\n"
    "strategy: approfondie\n"
    "steps:\n"
    "  - id: research\n"
    "    kind: task\n"
    "    domain: historian\n"
    "    depends_on: []\n"
    "```\n"
)


def test_injects_design_tag_when_user_asks_to_save() -> None:
    out = _inject_design_tag_if_yaml_only(_YAML_BLOCK, "Ok, sauvegarde ce workflow")
    assert "[EXECUTE:/workflow-design]" in out


def test_no_inject_when_tag_already_present() -> None:
    text = "[EXECUTE:/workflow-design]\n" + _YAML_BLOCK
    out = _inject_design_tag_if_yaml_only(text, "go")
    assert out.count("[EXECUTE:/workflow-design]") == 1


def test_no_inject_when_user_did_not_ask_to_save() -> None:
    out = _inject_design_tag_if_yaml_only(
        _YAML_BLOCK, "Peux-tu m'expliquer cette strategie ?",
    )
    assert "[EXECUTE:/workflow-design]" not in out


def test_no_inject_when_no_workflow_yaml() -> None:
    out = _inject_design_tag_if_yaml_only(
        "Pas de YAML ici, juste du texte.", "vas-y, lance",
    )
    assert "[EXECUTE:/workflow-design]" not in out


def test_injects_for_french_save_synonym() -> None:
    out = _inject_design_tag_if_yaml_only(_YAML_BLOCK, "Parfait, valide ça")
    assert "[EXECUTE:/workflow-design]" in out
