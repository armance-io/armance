"""Helpers shared across meta-agent chat handlers."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from armance.nls import t
from armance.service.loop_context import AgentStatus, LoopContext

logger = logging.getLogger(__name__)





def resolve_agent_path(armance_root: Path, stem: str) -> Path | None:
    """Resolve a meta-agent's .md path.

    Clean break (grandma launcher): base staff lives in the GLOBAL agents dir.
    Resolution order: per-project override (local ``.armance/agents``) →
    global base agents.
    """
    from armance import paths

    local = armance_root / "agents" / f"{stem}.md"
    if local.exists():
        return local
    global_agent = paths.global_agents_dir() / f"{stem}.md"
    return global_agent if global_agent.exists() else None


def set_status(ctx: LoopContext, name: str, state: str) -> None:
    """Record an agent state transition on the loop context."""
    for s in ctx.statuses:
        if s.name == name:
            s.state = state
            return
    ctx.statuses.append(AgentStatus(name=name, state=state))


_LOAD_RUN_RE = re.compile(r"\[EXECUTE:/load-run:([^:]+):([^\]]+)\]")


def intercept_load_run_tag(reply: str, ctx: LoopContext) -> str:
    """Strip + queue [EXECUTE:/load-run:<wf>:<rid>] for the next turn.

    Used by Mona and content specialists. Artefacts land in the agent's
    next prompt via session metadata queue.
    """
    m = _LOAD_RUN_RE.search(reply)
    if not m:
        return reply
    wf, rid = m.group(1).strip(), m.group(2).strip()
    pending = list(ctx.session.metadata.get("mona_pending_run_load", []))
    pending.append(f"{wf}::{rid}")
    ctx.session.metadata["mona_pending_run_load"] = pending
    ctx.session.save()
    reply = _LOAD_RUN_RE.sub("", reply).strip()
    reply += "\n\n" + t("mona.run_queued", workflow=wf, run_id=rid)
    return reply
