"""System HR agent service.

This module implements the HR agent service that:
- propose_jobs(brief): LLM call → JSON list of JobProposal
- create_agents(role): LLM call → 2-4 personas as YAML; validates uniqueness
- archive(agent): move file to `.archive/`
"""

from __future__ import annotations

import logging
import random
import re
import yaml
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

from armance.core.models.agent import Agent
from armance.config import Config
from armance.service.llm_service import get_client, call_with_ledger

logger = logging.getLogger(__name__)


class PersonaCollisionError(Exception):
    """Raised when Malik generates duplicate personas on the same axis."""
    pass

# International first-name pool — Malik favours cultural diversity
# (FR, EN, JP, DE, ES, IT, BR, IN, NG, KR, TR, AR, RU, NL, SE, MX, ZA, GR…)
FIRST_NAMES = [
    "Amara", "Anaïs", "Andrés", "Anya", "Arjun", "Astrid", "Ayaan", "Beatriz",
    "Bilal", "Camille", "Chiamaka", "Daiki", "Dimitri", "Elena", "Esra",
    "Farouk", "Gabriela", "Hana", "Hiroshi", "Imani", "Inés", "Jamal",
    "Jana", "Khalil", "Kofi", "Lakshmi", "Lars", "Léa", "Linh",
    "Lorenzo", "Luiza", "Mateo", "Mei", "Mikael", "Nadia", "Nikolai", "Niko",
    "Noor", "Olamide", "Priya", "Rafael", "Ravi", "Rina", "Sakura", "Sanjay",
    "Sven", "Takeshi", "Tariq", "Thandi", "Yara", "Yasmin", "Yusuf", "Zara",
]


class JobProposal(BaseModel):
    """A proposed job (specialized role)."""

    name: str
    description: str
    agents_needed: List[str] = Field(default_factory=list)  # Malik picks contextual personalities




_KNOWN_PROVIDERS = {"openrouter", "claude-code", "gemini", "custom-openai"}


def _normalise_domain(raw: str) -> str:
    """Slugify a domain string to a short ASCII identifier.

    Malik's LLM often writes domains as French prose like
    `historien des temps modernes`, `coordinateur événementiel`. These
    leak through to workflow YAML and break the executor (which matches
    by exact domain). Normalise to a stable kebab-case ASCII slug, and
    keep only the first 2 meaningful tokens to stay readable.

    Examples:
      - "Historien des temps modernes" → "historien-temps"
      - "coordinateur événementiel"    → "coordinateur-evenementiel"
      - "Project Manager"              → "project-manager"
      - "historian"                    → "historian"
    """
    import re
    import unicodedata

    if not raw:
        return ""
    # Strip accents, lowercase.
    nfkd = unicodedata.normalize("NFKD", raw)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    # Replace non-alnum with hyphens.
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_str).strip("-")
    if not slug:
        return ""
    # Drop common French stop-tokens that bloat the slug without adding
    # semantic content.
    _STOPS = {"de", "des", "du", "la", "le", "les", "un", "une", "et", "en", "a"}
    tokens = [t for t in slug.split("-") if t and t not in _STOPS]
    if not tokens:
        return slug  # all-stop, give up and return as-is
    # Keep at most the 2 most significant tokens (1-2 words, never verbose).
    return "-".join(tokens[:2])


def _normalise_provider_model(
    provider: str, model: str, *, default_provider: str,
) -> tuple[str, str]:
    """Repair common LLM mistakes when emitting (provider, model) pairs.

    Patterns handled:
      - `provider: openrouter/google`, `model: gemma-4-31b-it`
        → `provider: openrouter`, `model: google/gemma-4-31b-it` (then the
          validator either accepts or rejects against the discovered catalogue).
      - `provider: ` empty / missing → use `default_provider`.
      - `model:` already includes `provider/`-style id but provider field is
        wrong → strip provider prefix, keep the rest.
    Returns the (provider, model) pair to use.
    """
    p = (provider or "").strip().lower()
    m = (model or "").strip()
    if not p:
        p = default_provider or "openrouter"

    # Case 1: `provider: <known>/<vendor>` → extract canonical provider,
    # prepend vendor to model id.
    if "/" in p:
        head, _, tail = p.partition("/")
        if head in _KNOWN_PROVIDERS:
            p = head
            if tail and not m.startswith(f"{tail}/") and "/" not in m:
                m = f"{tail}/{m}"
    elif p not in _KNOWN_PROVIDERS:
        # Unknown bare provider — fallback to default.
        p = default_provider or "openrouter"

    return p, m


class RecruiterAgentService:
    """Service for the system-HR agent."""

    def __init__(
        self,
        agent: Agent,
        armance_root: Path,
        config: Config,
    ) -> None:
        self.agent = agent
        self.armance_root = armance_root
        self.config = config
        self.last_new_names: list[str] = []
        self.last_updated_names: list[str] = []
        self.last_skipped_collisions: list[str] = []
        self.last_staff_updates: list[str] = []

    async def propose_jobs(self, brief: str) -> List[JobProposal]:
        """Given a project brief, propose relevant jobs (specialized roles)."""
        if not brief.strip():
            raise ValueError("Project brief cannot be empty")

        client = get_client(self.agent.provider, self.config)
        system_prompt = self.agent.effective_system_prompt(
            caveman_level="none",
            repo_root=self.armance_root,
        )

        prompt = f"""Given this project brief, propose 2-3 relevant jobs (specialized roles):

Project brief: {brief}

Output format (YAML):
jobs:
  - name: <job_name>
    description: <2-3 sentence description>
  - name: <job_name>
    description: <2-3 sentence description>
"""

        response = await call_with_ledger(
            client,
            self.agent.name,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            self.agent.model,
            ledger=None,
        )

        # Parse YAML from response
        jobs = self._parse_jobs_yaml(response.text)
        return jobs

    def _validate_ascii_name(self, name: str) -> str:
        """Transliterate a name to ASCII and strip non-alphabetic chars."""
        import unicodedata
        normalized = unicodedata.normalize('NFKD', name)
        ascii_name = normalized.encode('ascii', 'ignore').decode('ascii')
        ascii_name = "".join(c for c in ascii_name if c.isalpha())
        if not ascii_name:
            raise ValueError(f"Name '{name}' contains no valid ASCII letters")
        return ascii_name

    def _validate_persona_uniqueness(self, agents: List[Agent]) -> None:
        """Ensure no two specialists have the same persona label."""
        personas = [a.persona for a in agents if a.persona]
        if len(personas) != len(set(personas)):
            seen = set()
            duplicates = []
            for p in personas:
                if p in seen:
                    duplicates.append(p)
                seen.add(p)
            raise PersonaCollisionError(f"Duplicate personas found on axis: {duplicates}")

    def _generate_agent_name(self, persona: str, index: int, used: set[str] | None = None) -> str:
        """Pick an international first-name avoiding collisions.

        `used` is a set of names already taken in the current role / repo.
        Falls back to deterministic round-robin if every pool entry is taken.
        """
        used = used or set()
        candidates = [n for n in FIRST_NAMES if n not in used]
        if candidates:
            # Sort the random selection from validated ASCII candidates
            clean_candidates = []
            for c in candidates:
                try:
                    clean_candidates.append(self._validate_ascii_name(c))
                except ValueError:
                    pass
            if clean_candidates:
                return random.choice(clean_candidates)
        # Pool exhausted or no clean candidate: deterministic suffix
        base_name = FIRST_NAMES[index % len(FIRST_NAMES)]
        try:
            base_name = self._validate_ascii_name(base_name)
        except ValueError:
            base_name = "Agent"
        return f"{base_name}-{index}"

    async def create_agents(self, role_name: str, brief: str = "") -> List[Agent]:
        """Create 2-4 agents with CONTEXTUAL personalities for a role.

        Delegates to _create_agents_contextual for robust validation and retry logic.
        """
        return await self._create_agents_contextual(role_name, brief)

    def parse_recruit_request(self, text: str) -> dict | None:
        """Parse a free-form recruit request.

        Returns a dict like
            {"role": "designer", "brief": "spécialisé style scandinave",
             "personas": ["audacious"]}
        or None when the text doesn't look like a recruit request.

        Recognised personas: audacious / balanced / prudent
        (FR: audacieux / équilibré / prudent).
        """
        t = text.strip()
        if not t:
            return None
        low = t.lower()

        # Map FR/EN persona keywords
        persona_map = {
            "audacious": "audacious", "audacieux": "audacious", "audacieuse": "audacious",
            "bold": "audacious", "risqué": "audacious",
            "balanced": "balanced", "équilibré": "balanced", "equilibre": "balanced",
            "balanced-out": "balanced", "neutral": "balanced",
            "prudent": "prudent", "prudente": "prudent", "conservative": "prudent",
            "careful": "prudent",
        }
        personas: list[str] = []
        for kw, c in persona_map.items():
            if re.search(rf"\b{re.escape(kw)}\b", low):
                if c not in personas:
                    personas.append(c)

        # Strip leading verbs
        stripped = re.sub(
            r"^(?:please\s+|s'?il\s+(?:te|vous)\s+pla[iî]t\s+)?"
            r"(?:peux[- ]tu\s+|pouvez[- ]vous\s+|can\s+you\s+|could\s+you\s+)?"
            r"(?:me\s+)?(?:recrute[rz]?|hire|embauche[rz]?|trouve[rz]?[- ]moi|find\s+me|"
            r"recruit|get\s+me|propose[rz]?|brings?\s+in|amène[rz]?[- ]moi)\s+",
            "",
            t,
            flags=re.IGNORECASE,
        )
        if stripped == t:
            # No recruit verb found
            return None

        # Drop "un / une / a / an / le / la / the"
        body = re.sub(r"^(?:un|une|le|la|les|a|an|the)\s+", "", stripped, flags=re.IGNORECASE)
        # role = first word, brief = rest
        m = re.match(r"([a-zA-ZÀ-ÿ\-]+)\s*(.*)", body.strip())
        if not m:
            return None
        role = m.group(1).strip().lower()
        brief = m.group(2).strip()
        # Strip persona keywords from brief
        for kw in persona_map:
            brief = re.sub(rf"\b{re.escape(kw)}\b", "", brief, flags=re.IGNORECASE)
        brief = re.sub(r"\s+", " ", brief).strip(" ,.;")
        return {
            "role": role,
            "brief": brief,
            # Empty list = let Malik pick contextual stances. Only honour
            # explicit user-specified personas (e.g. "audacieux", "left-wing").
            "personas": personas,
        }

    async def create_agents_custom(
        self,
        role: str,
        brief: str,
        personas: list[str],
    ) -> List[Agent]:
        """Create a panel of agents for a custom recruit.

        If `personas` is empty (or only the default audacious/balanced/prudent
        triplet), Malik asks the LLM to pick CONTEXTUAL personas for the role
        (e.g. positivist/revisionist/cultural for a medieval historian).
        Otherwise the explicitly-requested personas are honoured.
        """
        # Detect "no contextual override" — caller didn't specify, or provided
        # only the generic temperament triplet. In both cases, let Malik pick.
        default_triplet = {"audacious", "balanced", "prudent"}
        wants_contextual = (
            not personas
            or set(personas).issubset(default_triplet)
        )

        if wants_contextual:
            # Ask LLM for a contextual panel
            return await self._create_agents_contextual(role, brief)

        # Honour explicit user-specified personas (e.g. "left-wing")
        agents: List[Agent] = []
        used: set[str] = {"Armance", "Malik", "Kim", "Mona"}
        agents_dir = self.armance_root / "agents"
        if agents_dir.exists():
            for path in agents_dir.glob("*.md"):
                used.add(path.stem.split("-", 1)[0])

        focus = brief.strip() or f"general {role} expertise"
        for i, pers in enumerate(personas):
            name = self._generate_agent_name(pers, i, used)
            used.add(name)
            sys_prompt = (
                f"You are {name}, a {pers} {role}. "
                f"Your specialty: {focus}. "
                f"Bring this {pers} angle to every contribution. "
                f"Defer to colleagues when their persona or expertise fits "
                f"the question better."
            )
            agent = Agent.model_validate({
                "name": name,
                "role": role,
                "persona": pers,
                "provider": self.config.default_provider,
                "model": self.config.default_model,
                "reasoning": "medium",
                "system_prompt": sys_prompt,
            })
            agents.append(agent)
        return agents

    async def _create_agents_contextual(
        self,
        role: str,
        brief: str,
    ) -> List[Agent]:
        """Ask Malik (LLM) for a 2-4 agent panel with complementary contextual stance labels."""
        client = get_client(self.agent.provider, self.config)
        system_prompt = self.agent.effective_system_prompt(
            caveman_level="none",
            repo_root=self.armance_root,
        )
        focus = brief.strip() or f"the {role} domain"
        
        base_prompt = f"""Recruit a panel of 2-4 {role} specialists with COMPLEMENTARY perspectives.

Brief: {focus}

Pick a CONTEXTUAL axis of disagreement appropriate to {role} (e.g. medieval historian → positivist/revisionist/cultural; architect → modernist/classicist/vernacular; electrician → safety-first/innovation/cost-efficient). Do NOT use audacious/prudent/balanced unless no domain axis exists.

Ensure the panel covers complementary angles: e.g. regulations vs innovation, theory vs practice, speed vs quality, safety vs cost. The panel should debate productively.

All first names MUST use only ASCII letters (a-z, A-Z). No snake_case.

Output YAML only:
agents:
  - name: <first_name>
    role: {role}
    persona: <short stance label, free text, ≤14 chars>
    provider: {self.config.default_provider}
    model: {self.config.default_model}
    reasoning: medium
    system_prompt: |
      <4-8 lines describing who they are, how they think, what they push for and against>
"""
        retries = 0
        max_retries = 2
        collision_context = ""
        
        while True:
            prompt = base_prompt
            if collision_context:
                prompt += f"\n\nCRITICAL RESOLUTION RE-PROMPT:\n{collision_context}"
                
            try:
                response = await call_with_ledger(
                    client,
                    self.agent.name,
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    self.agent.model,
                    ledger=None,
                )
                agents = self._parse_agents_yaml(response.text, role)
                # Run validations
                # 1. ASCII validation (done during parse, but let's double check names)
                for agent in agents:
                    agent.name = self._validate_ascii_name(agent.name)
                # 2. Uniqueness of names (raises ValueError if duplicate)
                self._validate_uniqueness(agents)
                # 3. Persona uniqueness
                self._validate_persona_uniqueness(agents)
                
                return agents
                
            except (PersonaCollisionError, ValueError) as exc:
                retries += 1
                if retries > max_retries:
                    # After max retries: emit a recruit.validation.failed event
                    # accept the best-effort panel, surface to user.
                    logger.warning("recruit.validation.failed: Proposing best-effort panel due to validation failures: %s", exc)
                    # Downsize as last resort: keep only unique personas if it was a PersonaCollisionError
                    if 'agents' in locals():
                        if isinstance(exc, PersonaCollisionError):
                            unique_agents = []
                            seen_personas = set()
                            for agent in agents:
                                if agent.persona not in seen_personas:
                                    unique_agents.append(agent)
                                    seen_personas.add(agent.persona)
                            agents = unique_agents
                        return agents
                    # If agents are not available (parsing failed), raise the exception
                    raise exc
                
                # Format collision context for re-prompt
                if isinstance(exc, PersonaCollisionError):
                    collision_context = (
                        f"You generated specialists with duplicate personas. "
                        f"Re-generate the panel ensuring each persona is distinct on the axis. "
                        f"Validation error: {exc}"
                    )
                else:
                    collision_context = (
                        f"You generated invalid names or duplicate names. "
                        f"Ensure each specialist has a unique ASCII-only first name (e.g. Tomas, not Tomás). "
                        f"Validation error: {exc}"
                    )
                logger.info("Malik validation failed (retry %d/%d): %s", retries, max_retries, exc)

    async def archive(self, agent: Agent) -> Path:
        """Move agent file to `.archive/`."""
        agents_dir = self.armance_root / "agents"
        archive_dir = self.armance_root / ".archive"

        # Create archive directory if needed
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Move file
        source_path = agents_dir / f"{agent.name}.md"
        dest_path = archive_dir / f"{agent.name}.md"

        if source_path.exists():
            content = source_path.read_text(encoding="utf-8")
            dest_path.write_text(content, encoding="utf-8")
            source_path.unlink()
            logger.info("Archived agent: %s", agent.name)
            return dest_path
        else:
            raise FileNotFoundError(f"Agent file not found: {source_path}")

    def _parse_jobs_yaml(self, text: str) -> List[JobProposal]:
        """Parse YAML response containing jobs.

        Robust to multiple LLM output styles:
          - fenced ```yaml ... ```
          - bare YAML with `jobs:` / `roles:`
          - free-form numbered/bulleted lists like "1. **name** — description"
        """
        yaml_text: str | None = None
        fence_match = re.search(r"```(?:yaml)?\s*\n(.*?)\n```", text, re.DOTALL)
        if fence_match:
            yaml_text = fence_match.group(1).strip()
        else:
            # Try keyed YAML in declared order
            for key in ("jobs:", "roles:"):
                idx = text.find(key)
                if idx != -1:
                    yaml_text = text[idx:].strip()
                    break

        if yaml_text is None:
            # Last resort: try the whole text as YAML
            yaml_text = text.strip()

        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError:
            data = None

        # If structured YAML parsing failed, try free-form list extraction
        if not isinstance(data, dict):
            free = self._extract_free_form_jobs(text)
            if free:
                return free
            raise ValueError("Could not parse jobs from response")

        # Accept any of the known keys
        for key in ("jobs", "roles"):
            if key in data and isinstance(data[key], list):
                return [JobProposal.model_validate(item) for item in data[key]]

        # Free-form list fallback
        free = self._extract_free_form_jobs(text)
        if free:
            return free
        raise ValueError("Response missing 'jobs' key")

    def _extract_free_form_jobs(self, text: str) -> list[JobProposal]:
        """Extract jobs from numbered/bulleted natural-language lists.

        Matches patterns like:
            1. **name** — description
            - name: description
            * name — description
        """
        out: list[JobProposal] = []
        # Match numbered, bullet, or dash entries with name and description
        line_pat = re.compile(
            r"^\s*(?:\d+[\.\)]|[-*•])\s*"
            r"(?:\*\*)?(?P<name>[A-Za-zÀ-ÿ][\w\-]+(?:\s+[\w\-]+)?)(?:\*\*)?"
            r"\s*[—:\-–]\s*(?P<desc>.+?)\s*$",
            re.MULTILINE,
        )
        seen: set[str] = set()
        for m in line_pat.finditer(text):
            name = m.group("name").strip().lower().replace(" ", "-")
            desc = m.group("desc").strip()
            if name in seen or len(name) < 2 or len(desc) < 5:
                continue
            seen.add(name)
            out.append(JobProposal(name=name, description=desc))
            if len(out) >= 5:
                break
        return out


    def _parse_roles_yaml(self, text: str) -> List[JobProposal]:
        """Parse YAML response containing roles."""
        fence_match = re.search(r"```(?:yaml)?\s*\n(.*?)\n```", text, re.DOTALL)
        if fence_match:
            yaml_text = fence_match.group(1).strip()
        else:
            idx = text.find("roles:")
            if idx == -1:
                raise ValueError("Could not parse roles from response")
            yaml_text = text[idx:].strip()

        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse roles YAML: {e}")

        if not data or "roles" not in data:
            raise ValueError("Response missing 'roles' key")

        return [JobProposal.model_validate(p) for p in data["roles"]]

    def _find_agent_file(self, name: str) -> Path | None:
        agents_dir = self.armance_root / "agents"
        if not agents_dir.exists():
            return None
        base_path = agents_dir / f"{name}.md"
        if base_path.exists():
            return base_path
        # Look for versioned files first ({name}-v*.md), then any suffix.
        version_files = list(agents_dir.glob(f"{name}-v*.md"))
        if version_files:
            def version_key(p: Path) -> int:
                m = re.search(r"-v(\d+)\.md$", p.name)
                return int(m.group(1)) if m else 0
            version_files.sort(key=version_key)
            return version_files[-1]
        # Fallback: any {name}-{anything}.md (e.g. Theo-culturel.md from old recruitment).
        suffix_files = [
            p for p in agents_dir.glob(f"{name}-*.md")
            if not p.name.startswith("system-")
        ]
        if suffix_files:
            suffix_files.sort(key=lambda p: p.stat().st_mtime)
            return suffix_files[-1]
        return None

    def _parse_agents_yaml(self, text: str, role_name: str) -> List[Agent]:
        """Parse YAML response containing agents.

        Robust to the output styles smaller models emit, mirroring
        `_parse_jobs_yaml`: fenced ```yaml```, a bare `agents:` block, or a
        free-form numbered/bulleted list. A YAML that fails to load (e.g. an
        unquoted colon in a description on haiku) no longer hard-raises — we
        fall back to free-form extraction so recruit still produces a team.
        """
        # Strategy 1: code fences. Strategy 2: bare `agents:` block.
        yaml_text: str | None = None
        fence_match = re.search(r"```(?:yaml)?\s*\n(.*?)\n```", text, re.DOTALL)
        if fence_match:
            yaml_text = fence_match.group(1).strip()
        else:
            idx = text.find("agents:")
            if idx != -1:
                yaml_text = text[idx:].strip()

        data: object = None
        if yaml_text is not None:
            try:
                data = yaml.safe_load(yaml_text)
            except yaml.YAMLError:
                data = None  # recover via free-form extraction below

        # Strategy 3: free-form list fallback (covers both "no agents: key" and
        # "YAML didn't load"). Build synthetic agent entries from the named
        # lines; the entry-building loop fills provider/model/persona defaults.
        if not isinstance(data, dict) or "agents" not in data:
            free = self._extract_free_form_jobs(text)
            if not free:
                raise ValueError("Could not parse agents from response")
            data = {"agents": [{"name": j.name, "persona": j.description[:60]} for j in free]}

        # Names already taken in repo (avoid global collisions)
        used: set[str] = set()
        agents_dir = self.armance_root / "agents"
        if agents_dir.exists():
            for path in agents_dir.glob("*.md"):
                # Stem like "tom-audacious" -> first segment "tom"
                stem = path.stem.split("-", 1)[0]
                used.add(stem)
        # Reserve meta first names
        used.update({"Armance", "Malik", "Kim", "Mona"})

        agents: List[Agent] = []
        for i, entry in enumerate(data["agents"]):
            # Canonicalise to `role`. Accept legacy `domain` from older YAML.
            raw_role = entry.get("role") or entry.get("domain") or role_name
            entry["role"] = _normalise_domain(str(raw_role)) or role_name
            entry.pop("domain", None)  # remove legacy field
            
            # Use 'persona' or legacy 'character' key
            persona = entry.get("persona") or entry.get("character") or "balanced"
            if "character" in entry:
                entry.pop("character")
            entry["persona"] = persona

            # Use LLM-supplied name if it looks like a real first name
            # (single token, no underscore/dash, starts with uppercase letter).
            # Otherwise pick from the diverse international pool.
            supplied = entry.get("name")
            is_update = False
            if isinstance(supplied, str):
                existing_file = self._find_agent_file(supplied)
                if existing_file:
                    try:
                        existing_agent = Agent.load(existing_file)
                        current_role = _normalise_domain(
                            entry.get("role") or entry.get("domain") or role_name
                        )
                        existing_role = _normalise_domain(
                            existing_agent.domain or existing_agent.role or ""
                        )
                        # Accept as update if same normalised role OR if this is
                        # a model/persona swap on an existing agent (same name).
                        if existing_role == current_role or existing_role.split("-")[0] == current_role.split("-")[0]:
                            is_update = True
                    except Exception:
                        pass

            # Staff roles (host, recruiter, operator, vice-president,
            # criticalist) are not creatable as user agents — `recruit_agents`
            # redirects them to update the matching system-*.md instead. We
            # still need a valid name to pass schema validation here, so just
            # accept whatever Malik supplied (or generate one); the redirect
            # discards it.
            #
            # Names must be a single ASCII token so the user can `@-mention`
            # the agent. If Malik supplied a full name with a title or
            # surname ("Dr. Élise Moreau", "Prof. Arun Singh", "Dott.
            # Marta López") we keep the FIRST token that is NOT an
            # abbreviated title. Heuristic: any token ending with a period
            # is treated as an abbreviation/honorific and skipped — works
            # for every Latin-script locale without a per-language list.
            # CJK and other no-space scripts arrive as a single token and
            # hit the same downstream ASCII transliteration.
            first_token = ""
            if isinstance(supplied, str) and supplied:
                for tok in supplied.replace("_", " ").split():
                    if tok.endswith("."):
                        continue
                    first_token = tok
                    break
            looks_real = bool(
                first_token
                and first_token[0].isupper()
                and (first_token not in used or is_update)
            )
            if looks_real:
                try:
                    entry["name"] = self._validate_ascii_name(first_token)
                except ValueError:
                    looks_real = False
            if not looks_real:
                entry["name"] = self._generate_agent_name(persona, i, used)
            used.add(entry["name"])

            # Inject mandatory Pydantic fields if the LLM omitted them
            if "provider" not in entry:
                entry["provider"] = self.config.default_provider
            if "model" not in entry:
                # Use default model from config, fallback to a sensible default if empty
                entry["model"] = self.config.default_model or "anthropic/claude-3.5-sonnet:beta"

            # Normalise provider + model: weak LLMs sometimes write
            # `provider: openrouter/google`, `model: gemma-4-31b-it`.
            # Canonical form is `provider: openrouter`, `model: google/gemma-4-31b-it:free`.
            entry["provider"], entry["model"] = _normalise_provider_model(
                entry["provider"], entry["model"],
                default_provider=self.config.default_provider,
            )

            agents.append(Agent.model_validate(entry))

        return agents

    def _validate_uniqueness(self, agents: List[Agent]) -> None:
        """Validate agent names are unique within the role."""
        names = [a.name for a in agents]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate agent names found: {names}")

        # Check against existing agents
        agents_dir = self.armance_root / "agents"
        existing = set()
        if agents_dir.exists():
            for path in agents_dir.glob("*.md"):
                existing.add(path.stem)

        for agent in agents:
            if agent.name in existing:
                logger.warning("Agent %s already exists, will be overwritten", agent.name)

    def generate_agent_filename(self, agent: Agent) -> str:
        """Generate a kebab-case filename for an agent: {name}-{persona}.md"""
        persona = agent.persona or "balanced"
        return f"{agent.name}-{persona}.md"

    def format_agent_markdown(self, agent: Agent) -> str:
        """Format agent markdown with complete frontmatter and role-specific content."""
        role = agent.role or agent.domain or "general"
        persona = agent.persona or "balanced"
        name = agent.name or "Agent"

        md = f"""---
name: {name}
role: {role}
persona: {persona}
provider: {agent.provider}
model: {agent.model}
reasoning: {agent.reasoning or 'none'}
---
You are {name}, a {persona} {role}. Your role is to challenge assumptions about {role} selection, techniques, and methods for {role} projects.
"""
        # Append any additional system prompt content
        if agent.system_prompt:
            # Skip the frontmatter part if already included
            prompt_body = agent.system_prompt
            # Remove existing frontmatter if present
            if "---" in prompt_body:
                parts = prompt_body.split("---", 2)
                if len(parts) >= 3:
                    prompt_body = parts[2].strip()
            if prompt_body:
                md += f"\n{prompt_body}\n"

        return md

    def recruit_agents(
        self,
        yaml_text: str,
        role_name: str,
        agents_dir: Path,
    ) -> tuple[list[Agent], list[str]]:
        """Parse agents from YAML, persist them, update registry, and return created agents.

        This is the single entry point for the service layer to create agents
        from a Malik recruitment response. Callers (handlers, etc.) must NOT
        write agent files or update the registry directly.

        Returns:
            Tuple of (created_agents, created_names).
        """

        # Parse agents from YAML
        new_agents = self._parse_agents_yaml(yaml_text, role_name)
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Build a snapshot of existing (name -> role) so we can detect:
        #   - same name + same role  → overwrite (model swap, persona tweak)
        #   - same name + diff role  → reject (collision, Malik must pick another name)
        existing: dict[str, str] = {}
        if agents_dir.exists():
            for p in agents_dir.glob("*.md"):
                if p.stem.startswith("system-") or p.stem.startswith("_"):
                    continue
                try:
                    ex = Agent.load(p)
                    existing[ex.name] = (ex.role or ex.domain or "").strip().lower()
                except Exception:
                    continue

        # Roles owned by permanent staff. Recruiting one of these is meaningless;
        # the user wants to swap the model on the existing system-*.md file.
        # Keys are English canonical; Malik's prompt forces English in YAML
        # regardless of the user's interface language.
        _STAFF_ROLE_TO_FILE = {
            "host":            "system-context",
            "recruiter":       "system-hr",
            "operator":        "system-orchestrator",
            "vice-president":  "system-judge",
            "criticalist":     "system-challenger",
        }

        created: list[Agent] = []
        created_names: list[str] = []
        skipped_collisions: list[str] = []
        staff_updates: list[str] = []
        new_names: list[str] = []
        updated_names: list[str] = []

        for agent in new_agents:
            new_role = (agent.role or agent.domain or "").strip().lower()

            # Staff-role redirect: update the system-*.md model field, do not
            # create a new user agent (covers all five staff slots including
            # criticalist; the legacy same-name = update path is now redundant
            # for staff but still applies to user agents).
            if new_role in _STAFF_ROLE_TO_FILE:
                system_stem = _STAFF_ROLE_TO_FILE[new_role]
                system_path = agents_dir / f"{system_stem}.md"
                if system_path.exists():
                    try:
                        existing_staff = Agent.load(system_path)
                        existing_staff.provider = agent.provider or existing_staff.provider
                        existing_staff.model = agent.model or existing_staff.model
                        if agent.reasoning is not None:
                            existing_staff.reasoning = agent.reasoning
                        existing_staff.save(system_path)
                        staff_updates.append(f"{system_stem}({agent.model})")
                        logger.info(
                            "recruit: staff model swap %s → model=%s (role=%s, requested name %r ignored)",
                            system_stem, agent.model, new_role, agent.name,
                        )
                    except Exception:
                        logger.exception("staff model swap failed for %s", system_stem)
                    continue
                # If the system file is missing, fall through and let the normal
                # path create a user agent (defensive — should not happen in
                # practice since ensure_armance_tree installs all five).

            prior_role = existing.get(agent.name)
            if prior_role is not None:
                norm_prior = _normalise_domain(prior_role)
                norm_new = _normalise_domain(new_role)
                is_same_role = (norm_prior == norm_new) or (norm_prior.split("-")[0] == norm_new.split("-")[0])
                if not is_same_role:
                    logger.warning(
                        "recruit: name collision for %r — existing role %r != new role %r. "
                        "Skipping write to protect the existing agent.",
                        agent.name, prior_role, new_role,
                    )
                    skipped_collisions.append(agent.name)
                    continue

            # Write agent file via Agent.save (atomic). Same name + same role
            # means the user asked Malik to update model/persona — overwrite.
            agent_path = agents_dir / f"{agent.name}.md"
            # Remove stale {name}-{persona}.md files that may coexist with the
            # canonical {name}.md — leftover from first recruitment with suffix.
            for stale in agents_dir.glob(f"{agent.name}-*.md"):
                if stale != agent_path and not stale.name.startswith("system-"):
                    logger.info("recruit: removing stale file %s (superseded by %s)", stale.name, agent_path.name)
                    stale.unlink(missing_ok=True)
            agent.save(agent_path)
            logger.info(
                "recruit: saved %s → %s (model=%s)",
                agent.name, agent_path.name, agent.model,
            )
            created.append(agent)
            created_names.append(agent.name)
            if prior_role is None:
                new_names.append(agent.name)
            else:
                updated_names.append(agent.name)

            self._create_agent_in_registry(agent)

        self.last_new_names = new_names
        self.last_updated_names = updated_names
        self.last_skipped_collisions = skipped_collisions
        self.last_staff_updates = staff_updates

        if skipped_collisions:
            logger.warning(
                "recruit: %d agent(s) skipped due to name×role collision: %s",
                len(skipped_collisions), skipped_collisions,
            )
        if staff_updates:
            logger.info(
                "recruit: %d staff model swap(s) applied: %s",
                len(staff_updates), staff_updates,
            )
        return created, created_names

    def _create_agent_in_registry(self, agent: Agent) -> None:
        """Add or update an agent entry in the registry.json."""
        from armance.storage import paths

        registry = paths.ensure_agents_registry(self.armance_root)
        now_iso = agent.now_iso()

        found = False
        for entry in registry.get("agents", []):
            if entry.get("name") == agent.name:
                entry.update({
                    "role": agent.role or agent.domain,
                    "status": agent.status,
                    "version": agent.version,
                    "updated_at": now_iso,
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
                "created_at": now_iso,
                "updated_at": now_iso,
                "lead_for": agent.lead_for,
            })

        paths.write_agents_registry(self.armance_root, registry)
