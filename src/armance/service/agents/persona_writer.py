"""Persona writer — turn a recruited agent's YAML seed into a rich system_prompt.

When Malik recruits an agent, her YAML only carries the seed (name, role,
persona label, one-line description). The body of the .md file is empty.
Specialists then sound generic in conversation.

This module asks the configured LLM to draft a 150-300-word system_prompt
that incarnates the agent — voice, way of reasoning, references, biases,
what irritates them, what they defend — anchored to the project brief.
Result is written into the agent's .md body.

One LLM call per agent. Async so a recruitment of 7 agents fans out.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from armance.core.models.agent import Agent
from armance.core.models.task import Task
from armance.service.agents.specialist_runner import run_specialist

logger = logging.getLogger(__name__)


_PERSONA_PROMPT_TEMPLATE = """\
You write a system prompt for a specialist agent who will join a brainstorming
team. The prompt must let the agent INCARNATE a distinct personality, not
recite generic helpfulness. Target 150-300 words, plain Markdown.
{lang_instruction}
Do not use bullet lists unless one short list serves the persona.

Mandatory ingredients (weave them into prose, do NOT label them):
  - Voice: how this character speaks (register, rhythm, recurring tics).
  - Angle: the specific lens they bring to the project's topic.
  - 2-3 named references / authors / works they cite naturally.
  - One assumed bias and one thing that genuinely irritates them.
  - One thing they will always defend.
  - One concrete operating rule: a thing they always check before answering.

Anchor the persona to the project brief. The agent should sound like a real
contributor with skin in the game, not a generic LLM. Avoid clichés
("passionate", "I'm here to help"). Avoid mentioning Armance, workflows,
Mona, Serge, or other meta-agents — the agent only knows their own role.

End with a single line:
{ending_line}

---

Agent identity:
  - Name: {name}
  - Role: {domain}
  - Persona label: {persona}
  - Malik's one-line seed: {description}

Project brief (the team's shared context):
{brief}

Write the system prompt now. Output ONLY the prompt body, no preamble, no
fences, no explanation.
"""


async def write_persona_for(
    agent: Agent,
    project_brief: str,
    armance_root: Path,
    cfg,
) -> str:
    """Generate the rich system prompt and write it into the agent's .md.

    Returns the generated prompt (or empty string on failure). The agent
    file is updated in-place; the YAML frontmatter is preserved.
    """
    lang = getattr(cfg, "language", "en") or "en"
    if lang == "fr":
        lang_instruction = "The entire system prompt must be written in French. Use the second person ('Tu es')."
        ending_line = "> Tu réponds toujours dans la langue de l'utilisateur."
    elif lang == "es":
        lang_instruction = "The entire system prompt must be written in Spanish. Use the second person ('Eres / Tú eres')."
        ending_line = "> Siempre respondes en el idioma del usuario."
    elif lang == "de":
        lang_instruction = "The entire system prompt must be written in German. Use the second person ('Du bist')."
        ending_line = "> Antworte immer in der Sprache des Benutzers."
    elif lang == "zh":
        lang_instruction = "The entire system prompt must be written in Chinese. Use the second person ('你是')."
        ending_line = "> 始终使用用户的语言回答。"
    elif lang == "ja":
        lang_instruction = "The entire system prompt must be written in Japanese. Use the second person ('あなたは')."
        ending_line = "> 常にユーザーの言語で答えてください。"
    else:
        lang_instruction = "The entire system prompt must be written in English. Use the second person ('You are')."
        ending_line = "> Always reply in the user's language."

    prompt = _PERSONA_PROMPT_TEMPLATE.format(
        lang_instruction=lang_instruction,
        ending_line=ending_line,
        name=agent.name,
        domain=agent.role or agent.domain or "specialist",
        persona=agent.persona or "balanced",
        description=agent.description or "(no seed)",
        brief=(project_brief or "(no project brief yet)").strip(),
    )

    # Use the configured default model for the writer, NOT the agent's own
    # model — Malik's models are often free/small and produce flat persona
    # prose. A short call to the default model gives much better results.
    writer_agent = Agent(
        name="persona-writer",
        domain="meta",
        persona="craftsman",
        provider=getattr(cfg, "default_provider", "openrouter"),
        model=getattr(cfg, "default_model", "")
        or getattr(agent, "model", "")
        or "openai/gpt-4o-mini",
        system_prompt=(
            "You are a writer specialised in persona prompts for AI agents. "
            "You produce concise, sharply characterised system prompts."
        ),
    )
    task = Task(
        prompt=prompt, domain="meta", mode="light", requested_agent="persona-writer",
    )

    try:
        report = await run_specialist(
            writer_agent,
            task,
            armance_root,
            cfg,
            reports_root=armance_root / "reports",
        )
        body = (report.content or "").strip()
    except Exception:
        logger.exception("persona-writer failed for %s", agent.name)
        return ""

    if not body:
        return ""

    # Re-write the agent file: keep the YAML frontmatter intact, replace body.
    agent_path = armance_root / "agents" / f"{agent.name}.md"
    if agent_path.exists():
        agent.system_prompt = body
        agent.save(agent_path)
        logger.info(
            "Wrote rich persona for %s (model=%s, %d chars)",
            agent.name, agent.model, len(body),
        )
    else:
        logger.warning(
            "persona-writer: agent file %s not found — skipping save (model=%s)",
            agent_path, agent.model,
        )
    return body


async def write_personas(
    agents: list[Agent],
    project_brief: str,
    armance_root: Path,
    cfg,
) -> list[str]:
    """Fan out one persona-writer call per agent in parallel."""
    if not agents:
        return []
    tasks = [
        write_persona_for(a, project_brief, armance_root, cfg) for a in agents
    ]
    return await asyncio.gather(*tasks, return_exceptions=False)
