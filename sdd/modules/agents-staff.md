---
governs: [src/armance/service/agents/, ":!src/armance/service/agents/challenger_agent.py",
  ":!src/armance/service/agents/_rag_inject.py", src/armance/service/agent_sandbox.py]
depends: [providers-catalogue, library-rag]
---
# agents-staff

The five permanent staff agents and the recruitment of specialists. Staff personas are fixed, their first names
reserved: Armance hosts and frames, Malik recruits, Kim designs and runs workflows, Mona synthesises and judges, Serge
contradicts (see `serge-adversarial`). Their prompts are `builtin/system-*.md`, resolved global then local. Malik
recruits specialists on the fly, across providers, as panels whose personas disagree along an axis that matters for
the role.

Constraints and non-goals:

- Staff is neither recruitable nor dismissible by Malik.
- Side effects only through `[EXECUTE:/<command>]` tags, scrubbed against a per-role allowlist before interception:
  Armance cannot recruit, Kim cannot save L0, specialists have no tools. No implicit code path.
- No invented cost or model: provider and model are normalised against the catalogue.
- The roster points to persona files; it does not inline every persona on every turn.

Criteria:

- A tag outside the role's allowlist is stripped, an allowed one kept:
  [test_scrub_strips_unauthorised_tag_for_kim](../../tests/unit/service/test_agent_sandbox.py),
  [test_strip_unauthorised_tags_keeps_allowed](../../tests/unit/service/test_agent_sandbox.py).
- Two personas colliding on the same axis make Malik retry, then propose its best effort:
  [test_persona_collision_retry_loop_success_after_retry](../../tests/unit/service/agents/test_recruiter_agent.py),
  [test_persona_collision_exhausts_retries_proposes_best_effort](../../tests/unit/service/agents/test_recruiter_agent.py).
- Malik recruits only a model that is discovered or declared:
  [test_recruit_rejects_model_neither_discovered_nor_declared](../../tests/test_provider_allowlist.py).
- The roster gives each recruited agent its real model family:
  [test_roster_annotates_family_for_malik_health_view](../../tests/unit/service/agents/test_team_roster.py).
- A model swap keeps the persona and never applies to staff:
  [test_swap_changes_model_preserves_persona](../../tests/unit/service/agents/test_agent_swap.py),
  [test_swap_refuses_staff](../../tests/unit/service/agents/test_agent_swap.py).
