"""Conversation storage in Markdown format.

Per Spec §11_session.md — History is stored in .armance/conversations/<session_id>.md.
Format:
# Conversation: <session_id>

## [<timestamp>] <role> (<agent>)
<content>
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from armance.core.models.conversation import Conversation
from armance.core.models.turn import Turn


class ConversationStore:
    """Handles persistence of multi-turn conversations to Markdown."""

    def __init__(self, armance_root: Path) -> None:
        self.root = armance_root / "conversations"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.md"

    def save(self, session_id: str, conversation: Conversation, metadata: dict | None = None) -> Path:
        """Write conversation to Markdown file with optional YAML frontmatter."""
        lines: list[str] = []
        if metadata:
            import yaml
            lines.append("---")
            lines.append(yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip())
            lines.append("---\n")

        lines.append(f"# Conversation: {session_id}\n")
        
        for turn in conversation.turns:
            ts = turn.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            agent_str = f" ({turn.agent})" if turn.agent else ""
            lines.append(f"## [{ts}] {turn.role}{agent_str}")
            lines.append(turn.content.strip())
            lines.append("")

        path = self._path(session_id)
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def load(self, session_id: str) -> tuple[Conversation, dict]:
        """Read conversation + metadata from Markdown file."""
        path = self._path(session_id)
        if not path.exists():
            return Conversation(agent="system-context"), {}

        text = path.read_text(encoding="utf-8")
        metadata = {}
        content_text = text

        if text.startswith("---"):
            import yaml
            end = text.find("\n---", 3)
            if end != -1:
                fm_text = text[3:end].strip()
                metadata = yaml.safe_load(fm_text) or {}
                content_text = text[end + 4:].strip()

        turns: list[Turn] = []
        # Simple regex-based parser for the custom MD format
        blocks = re.split(r"\n## \[", content_text)
        for block in blocks:
            block = block.strip()
            if not block or block.startswith("# Conversation:"):
                continue
            
            # Restore the [ delimiter if it was split
            if not block.startswith("["):
                block = "[" + block

            m = re.match(r"\[(.*?)\] (.*?)(?: \((.*?)\))?\n(.*)", block, re.DOTALL)
            if m:
                ts_str, role, agent, content = m.groups()
                try:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    ts = datetime.now()
                
                turns.append(Turn(
                    role=role.strip(),
                    content=content.strip(),
                    timestamp=ts,
                    agent=agent.strip() if agent else None
                ))
        
        current_agent = metadata.get("current_agent", "system-context")
        if turns and not metadata.get("current_agent"):
            current_agent = turns[-1].agent or "system-context"

        return Conversation(agent=current_agent, turns=turns), metadata
