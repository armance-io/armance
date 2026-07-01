"""Role + agent management + feedback-loop / iterate-from handlers.

Extracted from service/handlers.py. Covers:
  - /role list|show
  - /agents (list shortcut)
  - /agent edit|replace|promote|demote|archive|list
  - /feedback-loop <run-id>
  - /iterate-from <run-id> [workflow]
"""
from __future__ import annotations

import logging
import re
from typing import Any

from armance.nls import t
from armance.service.loop_context import LoopContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# /role
# ---------------------------------------------------------------------------


async def cmd_role(args: list[str], ctx: LoopContext) -> str:
    if not args:
        return t("role.usage")
    action = args[0].lower()
    if action == "list":
        return await _role_list(ctx)
    if action == "show":
        name = args[1] if len(args) > 1 else ""
        return await _role_show(name, ctx)
    if action in ("add", "edit", "create"):
        return t("role.add_hint")
    return t("role.unknown_action", action=action)


async def _role_list(ctx: LoopContext) -> str:
    roles_dir = ctx.armance_root / "roles"
    roles: dict[str, str] = {}
    if roles_dir.exists():
        for path in roles_dir.glob("*.md"):
            try:
                content = path.read_text(encoding="utf-8")
                name_match = re.search(r"name:\s*(\w+)", content)
                if name_match:
                    roles[name_match.group(1)] = path.stem
            except Exception:
                continue
    if not roles:
        return t("role.list_empty")
    lines = ["roles:"]
    for _, display in sorted(roles.items()):
        lines.append(f"  {display}")
    return "\n".join(lines)


async def _role_show(name: str, ctx: LoopContext) -> str:
    if not name:
        return t("role.show_usage")
    role_file = ctx.armance_root / "roles" / f"{name}.md"
    if not role_file.exists():
        return t("role.not_found", name=name)

    content = role_file.read_text(encoding="utf-8")
    lines = [f"role: {name}", content]

    agents_dir = ctx.armance_root / "agents"
    agents = []
    if agents_dir.exists():
        for path in agents_dir.glob("*.md"):
            try:
                from armance.core.models.agent import Agent
                agent = Agent.load(path)
                if agent.role == name:
                    agents.append(agent)
            except Exception:
                continue
    if agents:
        lines.append("\nagents:")
        for a in agents:
            persona_val = a.persona if hasattr(a, "persona") else "balanced"
            lines.append(f"  - {a.name} ({persona_val})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# /agents and /agent
# ---------------------------------------------------------------------------


async def cmd_agents(args: list[str], ctx: LoopContext) -> str:
    from armance.service.agents.list_agents_skill import ListAgentsSkill
    include_archived = "--archived" in args
    skill = ListAgentsSkill(
        armance_root=ctx.armance_root, include_archived=include_archived
    )
    return skill.run()


async def cmd_agent(args: list[str], ctx: LoopContext) -> str:
    """Dispatch /agent edit|replace|promote|demote|archive|list."""
    if not args:
        return t("agent_cmd.usage")
    sub = args[0].lower()
    sub_args = " ".join(args[1:])

    if sub == "list":
        from armance.service.agents.list_agents_skill import ListAgentsSkill
        include_archived = "--archived" in sub_args
        return ListAgentsSkill(
            armance_root=ctx.armance_root, include_archived=include_archived
        ).run()
    if sub == "edit":
        from armance.service.agents.edit_agent_skill import EditAgentSkill
        return EditAgentSkill(armance_root=ctx.armance_root).run(sub_args)
    if sub == "replace":
        from armance.service.agents.replace_agent_skill import ReplaceAgentSkill
        return ReplaceAgentSkill(armance_root=ctx.armance_root).run(sub_args)
    if sub == "promote":
        from armance.service.agents.promote_agent_skill import PromoteAgentSkill
        return PromoteAgentSkill(armance_root=ctx.armance_root).run(sub_args)
    if sub == "demote":
        from armance.service.agents.demote_agent_skill import DemoteAgentSkill
        return DemoteAgentSkill(armance_root=ctx.armance_root).run(sub_args)
    if sub == "archive":
        from armance.service.agents.archive_agent_skill import ArchiveAgentSkill
        try:
            return ArchiveAgentSkill(armance_root=ctx.armance_root).run(sub_args)
        except ValueError as exc:
            return t("agent_cmd.error", error=str(exc))

    return t("agent_cmd.unknown_action", sub=sub)


# ---------------------------------------------------------------------------
# /feedback-loop and /iterate-from
# ---------------------------------------------------------------------------


_active_feedback_loop: Any = None


async def cmd_feedback_loop(args: list[str], ctx: LoopContext) -> str:
    """Propose merging a workflow synthesis into L0."""
    global _active_feedback_loop
    from armance.service.skills.feedback_loop import FeedbackLoopSkill
    if not args:
        if _active_feedback_loop is not None:
            return t("feedback.usage_with_pending")
        return t("feedback.usage")
    arg_str = " ".join(args)
    if _active_feedback_loop is None:
        _active_feedback_loop = FeedbackLoopSkill(
            armance_root=ctx.armance_root, config=ctx.cfg
        )
    reply = _active_feedback_loop.run(arg_str)
    if _active_feedback_loop._state == "idle":
        _active_feedback_loop = None
    return reply


async def cmd_iterate_from(args: list[str], ctx: LoopContext) -> str:
    """Spawn workflow N+1 from workflow N's synthesis."""
    if not args:
        return t("iterate.usage")
    from armance.service.skills.iterate_from import IterateFromSkill
    return IterateFromSkill(armance_root=ctx.armance_root, config=ctx.cfg).run(
        " ".join(args)
    )
