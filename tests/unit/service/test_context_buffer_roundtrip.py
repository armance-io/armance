"""Regression: context_buffer must survive across multiple chat turns and /save.

Simulates: user sends 3 messages → /save → L0 has all 3 messages.
The context_buffer in SessionState is the persistence mechanism.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.client.tui.types import LoopContext
from armance.config import Config
from armance.service.session import SessionState


@pytest.fixture()
def tmp_armance(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "agents").mkdir()
    (root / "context").mkdir()
    (root / "sessions").mkdir()
    agent_md = root / "agents" / "system-context.md"
    agent_md.write_text(
        "---\nname: system-context\ndomain: meta\ncharacter: balanced\n"
        "provider: openrouter\nmodel: openai/gpt-4o-mini\nreasoning: medium\n---\nArmance.",
        encoding="utf-8",
    )
    return root


@pytest.fixture()
def cfg() -> Config:
    return Config()


def _make_ctx(armance_root: Path, cfg: Config) -> LoopContext:
    from armance.service.session import Session
    state = SessionState.new()
    state.current_agent = "system-context"
    session = Session(state, armance_root)
    return LoopContext(
        armance_root=armance_root,
        cfg=cfg,
        state=state,
        session=session,
        ledger=MagicMock(),
        statuses=[],
        agents=[],
    )


@pytest.mark.asyncio
async def test_buffer_accumulates_across_chat_turns_and_save(
    tmp_armance: Path, cfg: Config
) -> None:
    """3 chat turns + /save → L0 body contains all 3 turn contents."""
    from armance.service.handlers import _cmd_context_chat, _cmd_save

    ctx = _make_ctx(tmp_armance, cfg)

    llm_reply = MagicMock(text="Compris, je note.")
    mock_compile = MagicMock(text="## Goal\nOn prépare une expo médiévale. Budget de 50 000 euros. Ouverture en juin 2026.")

    with patch("armance.service.agents.host_agent.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.host_agent.call_with_ledger",
               new_callable=AsyncMock) as mock_call:
        
        # Side effect to return chat replies then compilation reply
        mock_call.side_effect = [llm_reply, llm_reply, llm_reply, mock_compile]

        await _cmd_context_chat("On prépare une expo médiévale.", ctx)
        await _cmd_context_chat("Budget de 50 000 euros.", ctx)
        await _cmd_context_chat("Ouverture en juin 2026.", ctx)

        # buffer must have 3 entries in session metadata
        buffer = ctx.session.metadata.get("host_buffer", [])
        assert len(buffer) == 3, (
            f"Expected 3 buffer entries, got {buffer}"
        )

        # Now /save must write L0 with all 3
        result = await _cmd_save([], ctx)

    assert "error" not in result.lower(), f"save error: {result}"

    l0_dir = tmp_armance / "context" / "L0"
    l0_files = list(l0_dir.glob("v*.md"))
    assert len(l0_files) == 1

    content = l0_files[0].read_text(encoding="utf-8")
    assert "expo" in content
    assert "50 000" in content
    assert "juin" in content

