"""Agent lifecycle service — CRUD operations for specialist agents.

Implements the full agent lifecycle per ``docs/spec/20_agent_lifecycle.md``:
- create_agent, get_agent, list_agents, update_agent, delete_agent
- promote_agent, demote_agent, archive_agent

Agent data is persisted in two places:
1. Markdown agent files under ``.armance/agents/<name>.md`` (or ``<name>-v<N>.md``)
2. A JSON registry at ``.armance/agents/registry.json``

All writes use atomic temp+rename to prevent corruption.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from armance.core.models.agent import Agent
from armance.storage import paths

logger = logging.getLogger(__name__)


class AgentLifecycleError(Exception):
    """Base exception for agent lifecycle operations."""


class AgentNotFoundError(AgentLifecycleError):
    """Agent not found by name."""


class DuplicateAgentError(AgentLifecycleError):
    """Agent name already exists."""


class AgentLifecycleService:
    """Service managing the full CRUD lifecycle of specialist agents.

    Example::

        service = AgentLifecycleService(armance_root=Path(".armance"))
        agent = service.get_agent("historian-aisha")
        service.promote_agent("historian-aisha", "textiles")
    """

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_agent(self, agent: Agent) -> None:
        """Create a new agent.

        Validates uniqueness of agent name and required fields.
        Writes the agent markdown file and updates the registry atomically.

        Raises:
            DuplicateAgentError: if an agent with the same name already exists.
            ValueError: if required fields are missing.
        """
        self._validate_agent(agent)

        # Check uniqueness
        existing = self._find_agent_file(agent.name)
        if existing is not None:
            raise DuplicateAgentError(f"Agent '{agent.name}' already exists at {existing}")

        # Set timestamps if not already set
        now = agent.now_iso()
        agent.created_at = agent.created_at or now
        agent.updated_at = agent.updated_at or now

        # Write agent file
        agent_path = paths.agent_path(self.armance_root, agent.name)
        agent.save(agent_path)

        # Update registry
        registry = paths.ensure_agents_registry(self.armance_root)
        registry["agents"].append({
            "name": agent.name,
            "role": agent.role or agent.domain,
            "status": agent.status,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        })
        paths.write_agents_registry(self.armance_root, registry)
        logger.info("Created agent: %s", agent.name)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_agent(self, agent_id: str) -> Agent | None:
        """Load an agent by name.

        Returns:
            The Agent object, or None if not found.
        """
        agent_file = self._find_agent_file(agent_id)
        if agent_file is None:
            return None
        try:
            return Agent.load(agent_file)
        except (ValueError, FileNotFoundError) as exc:
            logger.warning("Failed to load agent %s: %s", agent_id, exc)
            return None

    def list_agents(self, include_archived: bool = False) -> list[Agent]:
        """List all agents.

        Args:
            include_archived: If True, also include archived agents.

        Returns:
            List of Agent objects.
        """
        agents_dir = paths.agents_dir(self.armance_root)
        agents: list[Agent] = []

        if agents_dir.exists():
            for agent_file in sorted(agents_dir.glob("*.md")):
                # Skip registry.json and version files
                if agent_file.name == "registry.json":
                    continue
                if re.match(r"^.+-v\d+\.md$", agent_file.name):
                    continue
                try:
                    agent = Agent.load(agent_file)
                    if not include_archived and agent.status == "archived":
                        continue
                    agents.append(agent)
                except (ValueError, FileNotFoundError) as exc:
                    logger.warning("Skipping malformed agent file %s: %s", agent_file, exc)

        # Also check archive directory if include_archived=True
        if include_archived:
            archive_dir = paths.archive_dir(self.armance_root)
            if archive_dir.exists():
                for agent_file in sorted(archive_dir.glob("*.md")):
                    try:
                        agent = Agent.load(agent_file)
                        agents.append(agent)
                    except (ValueError, FileNotFoundError) as exc:
                        logger.warning("Skipping malformed archive file %s: %s", agent_file, exc)

        return agents

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_agent(
        self,
        agent_id: str,
        *,
        persona: str | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        role: str | None = None,
        force_version: bool = False,
    ) -> Agent:
        """Update an agent's attributes.

        If the agent has DM turns > 0 or ``force_version`` is True, the
        update triggers a versioned overwrite (old file archived, new file
        created with incremented version).

        Args:
            agent_id: Agent name.
            persona: New persona.
            model: New LLM model.
            system_prompt: New system prompt body.
            role: New role/domain.
            force_version: Force version bump regardless of DM turns.

        Returns:
            The updated Agent.

        Raises:
            AgentNotFoundError: if agent does not exist.
        """
        agent = self.get_agent(agent_id)
        if agent is None:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found")

        # Check if versioned overwrite is needed
        needs_version = force_version or self._has_dm_turns(agent_id)

        if needs_version:
            agent = self._versioned_update(agent, persona=persona, model=model,
                                           system_prompt=system_prompt, role=role)
        else:
            # In-place edit
            if persona is not None:
                agent.persona = persona
            if model is not None:
                agent.model = model
            if system_prompt is not None:
                agent.system_prompt = system_prompt
            if role is not None:
                agent.domain = role
                agent.role = role
            agent.updated_at = agent.now_iso()
            agent_path = paths.agent_path(self.armance_root, agent.name)
            agent.save(agent_path)

        # Update registry
        self._update_registry(agent)
        logger.info("Updated agent: %s (versioned=%s)", agent_id, needs_version)
        return agent

    # ------------------------------------------------------------------
    # Delete (soft — archive)
    # ------------------------------------------------------------------

    def delete_agent(self, agent_id: str) -> None:
        """Soft-delete an agent by archiving it.

        Alias for ``archive_agent``. Use ``archive_agent`` for hard delete
        with ``--hard`` flag.

        Raises:
            AgentNotFoundError: if agent does not exist.
        """
        self.archive_agent(agent_id)

    # ------------------------------------------------------------------
    # Promote / Demote
    # ------------------------------------------------------------------

    def promote_agent(self, agent_id: str, topic: str) -> Agent:
        """Promote an agent to lead on a topic.

        Args:
            agent_id: Agent name.
            topic: Topic slug (e.g. "textiles").

        Returns:
            The updated Agent.

        Raises:
            AgentNotFoundError: if agent does not exist.
        """
        agent = self.get_agent(agent_id)
        if agent is None:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found")

        if topic not in agent.lead_for:
            agent.lead_for.append(topic)

        agent.updated_at = agent.now_iso()
        agent_path = paths.agent_path(self.armance_root, agent.name)
        agent.save(agent_path)
        self._update_registry(agent)
        logger.info("Promoted agent %s to lead on '%s'", agent_id, topic)
        return agent

    def demote_agent(self, agent_id: str, topic: str) -> Agent:
        """Demote an agent from a lead topic.

        Args:
            agent_id: Agent name.
            topic: Topic slug.

        Returns:
            The updated Agent.

        Raises:
            AgentNotFoundError: if agent does not exist.
        """
        agent = self.get_agent(agent_id)
        if agent is None:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found")

        if topic in agent.lead_for:
            agent.lead_for.remove(topic)

        agent.updated_at = agent.now_iso()
        agent_path = paths.agent_path(self.armance_root, agent.name)
        agent.save(agent_path)
        self._update_registry(agent)
        logger.info("Demoted agent %s from lead on '%s'", agent_id, topic)
        return agent

    # ------------------------------------------------------------------
    # Replace (atomic fire + rehire)
    # ------------------------------------------------------------------

    def replace_agent(self, agent_id: str, new_persona: str) -> tuple[str, Agent]:
        """Replace an agent with a new specialist in a single transaction.

        Archives the old agent, then creates a new one with the same role/domain
        but a fresh name and the requested persona. Atomicity matters because
        between the two operations the role's axis would be incomplete.

        Args:
            agent_id: Agent name to replace.
            new_persona: New persona for the replacement.

        Returns:
            Tuple of (old_agent_name, new Agent).

        Raises:
            AgentNotFoundError: if agent does not exist.
            ValueError: if required fields are missing.
        """
        old_agent = self.get_agent(agent_id)
        if old_agent is None:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found")

        # Generate a fresh name: keep role prefix, pick a new first name
        role = old_agent.domain or old_agent.role or "specialist"
        new_name = self._generate_replacement_name(role, new_persona)

        # Archive the old agent (soft archive preserves DM)
        self.archive_agent(agent_id)

        # Create the new agent with same role but new persona
        new_agent = Agent(
            name=new_name,
            domain=role,
            persona=new_persona,
            provider=old_agent.provider,
            model=old_agent.model,
            system_prompt=old_agent.system_prompt,
            provider_family=old_agent.provider_family,
        )
        self.create_agent(new_agent)

        logger.info("Replaced agent '%s' with '%s' (persona: %s)", agent_id, new_name, new_persona)
        return agent_id, new_agent

    def _generate_replacement_name(self, role: str, persona: str) -> str:
        """Generate a fresh agent name for replacement.

        Uses the role prefix and picks a new first name from a pool.
        """
        import random

        first_names: dict[str, list[str]] = {
            "historian": ["aisha", "lars", "mei", "elena", "omar"],
            "designer": ["kojo", "yuki", "nora", "eli", "sora"],
            "engineer": ["maya", "leo", "zara", "finn", "ira"],
            "strategist": ["aria", "kai", "lena", "rex", "tova"],
            "judge": ["mona", "sol", "nadia", "ian", "reva"],
            "challenger": ["serge", "lea", "darius", "uma", "fen"],
            "orchestrator": ["kim", "rex", "ami", "jay", "nova"],
            "hr": ["armance", "malik", "kim", "mona", "serge"],
        }
        names = first_names.get(role.lower(), ["nova", "rex", "ami", "jay", "ira", "lea", "uma"])
        # Pick a name that doesn't collide with existing agents
        existing = {a.name for a in self.list_agents(include_archived=True)}
        for name in random.sample(names, len(names)):
            candidate = f"{role}-{name}"
            if candidate not in existing:
                return candidate
        # Fallback: append a random suffix
        suffix = random.randint(100, 999)
        return f"{role}-{names[0]}-{suffix}"

    # ------------------------------------------------------------------
    # Archive
    # ------------------------------------------------------------------

    def archive_agent(self, agent_id: str, *, hard: bool = False) -> Agent:
        """Archive an agent.

        Soft archive moves the file to ``.armance/.archive/``.
        Hard archive (``hard=True``) deletes the file entirely.

        Args:
            agent_id: Agent name.
            hard: If True, delete instead of archive.

        Returns:
            The archived Agent with status set to "archived".

        Raises:
            AgentNotFoundError: if agent does not exist.
        """
        agent = self.get_agent(agent_id)
        if agent is None:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found")

        agent.status = "archived"
        agent.updated_at = agent.now_iso()

        if hard:
            # Hard delete — remove file entirely
            agent_file = self._find_agent_file(agent_id)
            if agent_file:
                agent_file.unlink()
            logger.info("Hard-deleted agent: %s", agent_id)
        else:
            # Soft archive — move to .archive/
            archive_path = paths.archive_agent_path(
                self.armance_root, agent_id
            )
            agent_file = self._find_agent_file(agent_id)
            if agent_file:
                archive_path.parent.mkdir(parents=True, exist_ok=True)
                archive_path.write_text(
                    agent.to_markdown(), encoding="utf-8"
                )
                agent_file.unlink()
            logger.info("Archived agent: %s", agent_id)

        # Update registry
        self._update_registry(agent)
        return agent

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_agent(self, agent: Agent) -> None:
        """Validate required agent fields."""
        if not agent.name or not agent.name.strip():
            raise ValueError("Agent name is required")
        if not agent.domain or not agent.domain.strip():
            raise ValueError("Agent domain is required")
        if agent.domain != "meta" and not agent.name.startswith("system-") and (not agent.persona or not agent.persona.strip()):
            raise ValueError("Agent persona is required")
        if not agent.provider or not agent.provider.strip():
            raise ValueError("Agent provider is required")
        if not agent.model or not agent.model.strip():
            raise ValueError("Agent model is required")

    def _find_agent_file(self, name: str) -> Path | None:
        """Find the active agent file for a given name.

        Returns the path to the active file (highest version or unsuffixed).
        """
        agents_dir = paths.agents_dir(self.armance_root)
        if not agents_dir.exists():
            return None

        # Check for unsuffixed file first
        base_path = agents_dir / f"{name}.md"
        if base_path.exists():
            return base_path

        # Check for versioned files, return highest version
        version_files = list(agents_dir.glob(f"{name}-v*.md"))
        if version_files:
            # Sort by version number (extract from filename)
            def version_key(p: Path) -> int:
                m = re.search(r"-v(\d+)\.md$", p.name)
                return int(m.group(1)) if m else 0
            version_files.sort(key=version_key)
            return version_files[-1]

        return None

    def _has_dm_turns(self, agent_id: str) -> bool:
        """Check if the agent has any DM conversation turns."""
        conversations_dir = self.armance_root / "conversations" / "dm"
        if not conversations_dir.exists():
            return False

        # Look for dm:<agent_id> directory or file
        for item in conversations_dir.iterdir():
            if item.name.startswith(f"dm:{agent_id}"):
                # Check if there are any turn files
                if item.is_dir():
                    if any(item.glob("*.md")):
                        return True
                elif item.suffix == ".md":
                    content = item.read_text(encoding="utf-8")
                    # Count turns (lines starting with role:)
                    if content.strip():
                        return True
        return False

    def _versioned_update(
        self,
        agent: Agent,
        *,
        persona: str | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        role: str | None = None,
    ) -> Agent:
        """Perform a versioned overwrite of an agent file.

        Archives the current version and creates a new versioned file.
        """
        old_version = agent.version
        agent.version += 1
        agent.parent_version = old_version
        agent.updated_at = agent.now_iso()

        # Apply updates
        if persona is not None:
            agent.persona = persona
        if model is not None:
            agent.model = model
        if system_prompt is not None:
            agent.system_prompt = system_prompt
        if role is not None:
            agent.domain = role
            agent.role = role

        # Archive old version
        old_file = self._find_agent_file(agent.name)
        if old_file:
            archive_dir = paths.archive_dir(self.armance_root)
            archive_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            archive_name = f"{agent.name}-v{old_version}_{date_str}.md"
            archive_path = archive_dir / archive_name
            archive_path.write_text(old_file.read_text(encoding="utf-8"), encoding="utf-8")
            old_file.unlink()
            logger.info("Archived old version: %s-v%s", agent.name, old_version)

        # Write new versioned file
        new_path = paths.agent_version_path(self.armance_root, agent.name, agent.version)
        agent.save(new_path)

        return agent

    def _update_registry(self, agent: Agent) -> None:
        """Update the agent registry entry."""
        registry = paths.ensure_agents_registry(self.armance_root)

        # Find and update existing entry, or add new
        found = False
        for entry in registry.get("agents", []):
            if entry.get("name") == agent.name:
                entry.update({
                    "role": agent.role or agent.domain,
                    "status": agent.status,
                    "version": agent.version,
                    "updated_at": agent.updated_at,
                    "lead_for": agent.lead_for,
                })
                found = True
                break

        if not found:
            registry.setdefault("agents", []).append({
                "name": agent.name,
                "role": agent.role or agent.domain,
                "status": agent.status,
                "version": agent.version,
                "created_at": agent.created_at,
                "updated_at": agent.updated_at,
                "lead_for": agent.lead_for,
            })

        paths.write_agents_registry(self.armance_root, registry)
