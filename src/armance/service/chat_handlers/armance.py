"""Armance (system-context) — chat shell.

Routes user turns through HostAgentService, which owns Armance's CONTEXT-FIRST
prompt, library/docs injection, buffer accumulation, and `[EXECUTE:/save]`
intercept.
"""
from __future__ import annotations

import logging

from armance.nls import t
from armance.service.chat_handlers.common import resolve_agent_path, set_status
from armance.service.loop_context import LoopContext

logger = logging.getLogger(__name__)


async def cmd_context_chat(text: str, ctx: LoopContext) -> str:
    """Run one Armance turn via HostAgentService."""
    from armance.core.models.agent import Agent
    from armance.service.agents.host_agent import HostAgentService

    agent_name = ctx.state.current_agent or "system-context"
    if agent_name == "context":
        agent_name = "system-context"

    agent_path = (
        resolve_agent_path(ctx.armance_root, agent_name)
        or resolve_agent_path(ctx.armance_root, "system-context")
    )
    if agent_path is None:
        return t("meta_agent.armance_missing")

    context_agent = Agent.load(agent_path)
    cas = HostAgentService(
        agent=context_agent,
        armance_root=ctx.armance_root,
        config=ctx.cfg,
        event_bus=ctx.event_bus,
    )
    cas.set_state(ctx.session.metadata)
    cas.conversation = ctx.session.conversation
    cas._project_brief = ctx.state.project_brief
    cas._team_roster = ctx.agents

    try:
        reply = await cas.dialogue(text)
        set_status(ctx, agent_name, "completed")
    except Exception as exc:
        set_status(ctx, agent_name, "error")
        logger.exception("context chat failed")
        reply = t("common.error", error=str(exc))

    ctx.session.metadata.update(cas.get_state())

    # Promote brief once Armance has seen it.
    if cas._has_seen_brief and not ctx.state.project_brief:
        for turn in cas.conversation.turns:
            if turn.role == "user":
                ctx.state.project_brief = turn.content
                break

    ctx.session.save()
    ctx._last_output = reply
    return reply
