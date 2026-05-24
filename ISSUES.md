# Armance — Issues index

> Flat index of every open user story (feature) and every known bug or
> limitation. **One file per issue** under `issues/features/` or
> `issues/bugs/`. This file is the canonical entry point.
>
> Linked from: [`README.md`](README.md), [`ONBOARDING.md`](ONBOARDING.md),
> [`BUG_FIXING_GUIDE.md`](BUG_FIXING_GUIDE.md), [`roadmap/04_roadmap.md`](roadmap/04_roadmap.md).

## How to use this index

- **Picking up work** — open the linked file. It is self-contained:
  symptom, cause, fix sketch (with file paths), acceptance criteria.
- **Adding a new issue** — create
  `issues/{features,bugs}/<kebab-slug>.md` from the template at the
  bottom of this file, then add one line in the table below.
- **Closing an issue** — when the fix lands, delete the file *and*
  remove its row from the table. The git history is the closed-issue
  log; this index stays current-only.

---

## Features (user stories)

| Issue | Status | Summary |
|---|---|---|
| [`workflow-live-pipeline`](issues/features/workflow-live-pipeline.md) | proposed | Repurpose dead sidebar `Tasks` into live workflow view; agent spinner; background runs with agent-busy semantics. |
| [`workflow-runtime-ux`](issues/features/workflow-runtime-ux.md) | partial | Stories 1 (staff scope) + 2 (parallel execution). Story 3 superseded by `workflow-live-pipeline`. |
| [`auto-embed-discovery`](issues/features/auto-embed-discovery.md) | proposed | Drop the embedding question from `armance init`; Armance proposes a model when documents first appear. |
| [`web-layer`](issues/features/web-layer.md) | proposed | FastAPI + Next.js port; same service layer; ~1.4k LOC under `web/`. Build guide. |
| [`web-layer-stories`](issues/features/web-layer-stories.md) | proposed | Vision and user stories for the V2 web layer. Companion to the build guide. |
| [`reorder-host-kim-malik-flow`](issues/features/reorder-host-kim-malik-flow.md) | partial | Armance → Kim → Malik instead of Armance → Malik → Kim. Mitigation shipped, full reorder pending. |
| [`forward-tag-first-class`](issues/features/forward-tag-first-class.md) | proposed | Promote `@<agent>, …` forwarding to a `[FORWARD:@<agent>]` tag with per-role allow-list. |

## Bugs and known limitations

| Issue | Severity | Summary |
|---|---|---|
| [`small-model-caveman-drift`](issues/bugs/small-model-caveman-drift.md) | medium | Meta-agents drift to telegraphic register on small models / long transcripts. v22 prompts mitigate; latent risk remains. |
| [`sidebar-tasks-dead-section`](issues/bugs/sidebar-tasks-dead-section.md) | low | Sidebar `Tasks` section is empty by design. Removed by `workflow-live-pipeline` Phase 1a. |
| [`spinner-spins-without-tokens`](issues/bugs/spinner-spins-without-tokens.md) | low | The agent spinner (once shipped) will tick during the network / cold-start window. Tracked alongside its feature. |
| [`provider-rate-limit-during-background-run`](issues/bugs/provider-rate-limit-during-background-run.md) | low | Concurrent calls from a background workflow + the user chat may hit provider 429. Accepted for V2. |

---

## Template for a new issue

```markdown
# <Short title>

> Status: <proposed | partial | in-progress | blocked>.
> Linked to: <other issue or roadmap section, optional>.

## Symptom
What the user / developer sees.

## Cause
Why it happens (for bugs) or which user need is currently unmet (for features).

## Fix sketch / Implementation
| File | Action |
|---|---|
| ... | ... |

## Acceptance
- [ ] Concrete, testable criterion.
- [ ] Another one.

## Out of scope
What this issue deliberately does NOT cover.
```
