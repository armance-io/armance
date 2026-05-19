"""Default chat path: routes a turn to the right meta-agent shell, or
runs a single user-recruited specialist (with sandboxed scrub)."""
from __future__ import annotations

import logging

from armance.nls import t
from armance.service.agent_sandbox import scrub_reply
from armance.service.agents.specialist_runner import SpecialistRunner, run_specialist
from armance.service.chat_handlers.common import intercept_load_run_tag, set_status
from armance.service.loop_context import LoopContext

logger = logging.getLogger(__name__)


# Coordination shells whose turns content specialists must NOT see — they
# carry recruitment plans, workflow design dialogue, framing chatter, not
# project content.
_COORD_AGENTS = {"system-context", "system-hr", "system-orchestrator"}


async def cmd_chat(text: str, ctx: LoopContext) -> str:
    """Route a chat turn.

    Order: Armance / Malik / Kim / Mona → meta-agent shells. Everything
    else goes through the specialist runner.
    """
    agent_name = ctx.state.current_agent or "armance"
    set_status(ctx, agent_name, "working")

    if agent_name in ("context", "system-context"):
        from armance.service.chat_handlers.armance import cmd_context_chat
        return await cmd_context_chat(text, ctx)
    if agent_name in ("hr", "system-hr"):
        from armance.service.chat_handlers.malik import cmd_hr_chat
        return await cmd_hr_chat(text, ctx)
    if agent_name in ("orchestrator", "system-orchestrator"):
        from armance.service.chat_handlers.kim import cmd_orchestrator_chat
        # Lazy import to avoid circular dependency on handlers.
        from armance.service.handlers import _cmd_workflow_run
        return await cmd_orchestrator_chat(text, ctx, workflow_runner=_cmd_workflow_run)
    if agent_name in ("judge", "system-judge"):
        from armance.service.mona_ops import cmd_mona_chat
        return await cmd_mona_chat(text, ctx)

    try:
        from armance.core.models.task import Task

        agent_obj = next((a for a in ctx.agents if a.name == agent_name), None)
        domain = agent_obj.domain if agent_obj else agent_name.split("_")[0]
        task = Task(prompt=text, domain=domain, mode="light", requested_agent=agent_name)
        history = [
            {"role": t.role, "content": t.content}
            for t in ctx.session.conversation.turns
            if t.role == "user" or (t.agent or "") not in _COORD_AGENTS
        ]
        ctx.session.conversation.append("user", text, agent=agent_name)

        if agent_obj is not None:
            view = f"dm:{agent_name}"
            runner = SpecialistRunner(
                ctx.armance_root,
                ctx.cfg,
                reports_root=ctx.armance_root / "reports",
            )
            report = await runner.run(agent_obj, task, history=history, view=view)
            reply = scrub_reply(report.content, agent_role="specialist")
            reply = intercept_load_run_tag(reply, ctx)
        else:
            fallback = ctx.agents[0] if ctx.agents else None
            if fallback is None:
                reply = t("common.no_agents_loaded")
            else:
                fb = await run_specialist(
                    fallback,
                    task,
                    ctx.armance_root,
                    ctx.cfg,
                    reports_root=ctx.armance_root / "reports",
                    history=history,
                )
                reply = fb.content
        set_status(ctx, agent_name, "completed")
    except Exception as exc:
        set_status(ctx, agent_name, "error")
        logger.exception("chat failed")
        reply = t("common.error", error=str(exc))
    ctx.session.conversation.append("assistant", reply, agent=agent_name)
    ctx.session.save()
    ctx._last_output = reply
    return reply
