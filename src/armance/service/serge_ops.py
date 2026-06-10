"""Serge (system-challenger) chat shell.

Serge is the adversarial criticalist. He supports /load-run to pull past
workflow runs into context for red-teaming, but has no save/deliverable tags.
"""
from __future__ import annotations

import logging
import re

from armance.nls import t
from armance.service.agent_sandbox import scrub_reply
from armance.service.loop_context import LoopContext

logger = logging.getLogger(__name__)

_LOAD_TAG = re.compile(r"\[EXECUTE:/load-run:([^:]+):([^\]]+)\]")


async def cmd_serge_chat(text: str, ctx: LoopContext) -> str:
    """Serge — adversarial chat with /load-run support."""
    from armance.core.models.agent import Agent
    from armance.service.agents.host_agent import HostAgentService

    agent_name = "system-challenger"
    serge_path = ctx.armance_root / "agents" / f"{agent_name}.md"
    if not serge_path.exists():
        from armance import paths
        serge_path = paths.global_agents_dir() / f"{agent_name}.md"
    if not serge_path.exists():
        return t("common.error", error="Serge agent file missing")

    serge_agent = Agent.load(serge_path)
    service = HostAgentService(
        agent=serge_agent,
        armance_root=ctx.armance_root,
        config=ctx.cfg,
        sandbox_role="specialist",
    )
    service.set_state(ctx.session.metadata)
    service.conversation = ctx.session.conversation

    pending = list(ctx.session.metadata.get("serge_pending_run_load", []))
    if pending:
        from armance.service.workflow_runs import load_run
        blocks: list[str] = []
        for entry in pending:
            wf, rid = entry.split("::", 1)
            files = load_run(ctx.armance_root, wf, rid)
            if not files:
                continue
            body = "\n\n".join(
                f"### `{name}`\n{content[:6000]}" for name, content in files.items()
            )
            blocks.append(f"## Workflow run `{wf}/{rid}`\n\n{body}")
        if blocks:
            service._pending_raw_inject = "\n\n---\n\n".join(blocks)
        ctx.session.metadata["serge_pending_run_load"] = []

    try:
        reply = await service.dialogue(text)
    except Exception as exc:
        logger.exception("Serge dialogue failed")
        return t("common.error", error=str(exc))

    ctx.session.metadata.update(service.get_state())
    reply = scrub_reply(reply, agent_role="specialist")

    load_match = _LOAD_TAG.search(reply)
    if load_match:
        wf, rid = load_match.group(1).strip(), load_match.group(2).strip()
        pending = list(ctx.session.metadata.get("serge_pending_run_load", []))
        pending.append(f"{wf}::{rid}")
        ctx.session.metadata["serge_pending_run_load"] = pending
        reply = _LOAD_TAG.sub("", reply).strip()

    ctx.session.save()
    ctx._last_output = reply
    return reply
