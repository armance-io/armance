# Armance — Bug-Fixing Guide for Correctional Agents

> Audience: AI agents (Gemini Flash, Haiku, GPT-mini, etc.) tasked with
> fixing a bug reported by the user during V1 convergence testing.
> You may be smart, you may be small. Either way, **respect the rules
> below or your patch will be rejected.**

This file is the contract. Read it before touching code. If you don't
understand a rule, do not "fix it your way" — flag it back to the user.

---

## 0. Mental model in one paragraph

Armance is a small Python CLI that runs a multi-agent brainstorming firm
on the user's machine. It's already in production-ish shape. The
codebase is **deliberately tight**: ~21k LOC, 4 architectural layers,
strict NLS, zero hard-coded user-facing strings, side effects only via
`[EXECUTE:/...]` tags. A "regression" here means more than a broken
feature — introducing duplication, hard-coded strings, or layer
violations breaks the project's *evolvability* even when tests pass.

---

## 1. The seven inviolable rules

If your patch breaks any of these, the user will reject it. No exceptions.

### Rule 1 — Layers

```
client  →  transport  →  service  →  core
```

Lower layers may not import from upper layers. Check:

```bash
grep -rn "from armance.client" src/armance/core src/armance/service     # must be empty
grep -rn "from armance.providers" src/armance/core                     # must be empty (registry is the exception)
```

If you find yourself adding such an import, **stop**. Use dependency
injection or a Protocol callback instead.

### Rule 2 — No hard-coded user-facing strings

Anything the user reads goes through:

```python
from armance.nls import t
t("section.key", arg=value)
```

Keys live in `src/armance/nls_catalogues/{en,fr}.yaml`. If you add a new
user-facing string:
1. Add the key in **both** `en.yaml` and `fr.yaml`.
2. Use `t("...")` in the call site.
3. Logs and Python exceptions stay English — they're not user-facing.

### Rule 3 — Side effects through `[EXECUTE:/...]` tags

When an agent's LLM reply needs to trigger an action, the agent emits a
tag. The tag is intercepted by Python. **Do not** add a hidden code path
that mutates state based on regex on the user's input. Existing tags:

Tags are role-scoped via `service.agent_sandbox._ROLE_TAG_ALLOWLIST`:

| Role | Allowed tags |
|---|---|
| armance | `/save`, `/library-{index,load,unload,unindex,status}` |
| malik | `/recruit`, `/dismiss-all[:<name>]`, `/library-status` |
| kim | `/workflow-design`, `/workflow-run:<name>`, `/library-status` |
| mona | `/save-deliverable:<basename>`, `/load-run:<wf>:<run_id>`, `/library-status` |
| specialist | `/load-run:<wf>:<run_id>` (only) |

Need a new action? Add a new tag, register it in `_ROLE_TAG_ALLOWLIST`,
add an intercept. Don't bypass.

### Rule 4 — No hard-coded magic values

Especially for things that vary per user:

- Embedding dimensions → probed at runtime by `_probe_embedding_dim`. Never `dim = 1536`.
- Model ids → never hard-code "gpt-4o" or any model in a feature path. Use `cfg.default_model`.
- Token prices → live in `cfg.prices` or `cost.lookup_price`.
- File paths → use `armance.storage.paths`.

### Rule 5 — File size cap

Target: ≤ 300 LOC per Python file. `service/handlers.py` is the open
exception (chat shells couple to workflow engine; deferred split).
If your patch grows a file past 300 LOC, **extract**. Pattern:
`service/*_ops.py` — one file per concern (`library_ops`, `save_ops`,
`role_ops`, `task_ops`). Keep imports minimal.

### Rule 6 — `from __future__ import annotations` at top of every module

Always. No exceptions.

### Rule 7 — Tests stay green

Before you commit:

```bash
uv run pytest tests/ -q
uv run ruff check src/
bash scripts/check_invariants.sh
```

All three must pass:
- pytest: **889 passed** (8 skipped is normal).
- ruff: `All checks passed!`
- invariants: `ALL CHECKS PASSED (31 ok)`

If your change breaks a test, fix the test ONLY if the test was wrong.
Otherwise fix your patch.

---

## 2. Patch shape

Good patches are small, named, and reversible.

### Commit message

Conventional Commits format. Scope is the top-level module:

```
fix(library): unload now clears persistent state too
feat(malik): mix providers across recruitment panel
refactor(handlers): extract /task ops to task_ops.py
docs: explain feuillet vs charger to user-level
test(qa_live): J/K/N checkpoint round-trip
```

### One PR = one logical change

Don't bundle "fix bug X" with "refactor module Y". The user will ask for
two PRs.

---

## 3. Where to look first

Use this table before grepping blindly. The codebase is small enough
that this nearly always identifies the right module.

| Symptom | Look first at |
|---|---|
| TUI crashes on start | `client/tui/screens/main.py`, `client/tui/widgets/*` |
| Slash command misbehaves | `service/handlers.py` (find `_cmd_<name>` or the appropriate `*_ops.py`) |
| Agent says the wrong thing | `service/agents/<role>_agent.py` + the agent's `.md` in `service/agents/builtin/` |
| Library shows wrong state | `storage/library_state.py`, `storage/library_availability.py`, `storage/rag_status.py` |
| Indexation fails / dim mismatch | `storage/ingestion.py` (probe + reset_db_if_embedding_changed), `storage/rag_index.py` |
| Wrong language in UI | `nls_catalogues/{en,fr}.yaml` + the call site uses `t("key")` |
| Provider auth fails | `providers/<name>.py` + `cli.py` doctor + `.armance/.env` reading |
| Cost off / missing | `service/cost.py`, `providers/model_discovery.py`, `service/llm_service.TokenLedger.record` |
| Workflow stuck or wrong | `core/models/workflow.py` (simple engine) + `service/workflow_hooks.py` (consensus / cross-family) |
| TUI freezes during action | check if a sync function is called from the async loop — wrap in `asyncio.to_thread` |
| Embedding model id changed | `embedding_meta.json` should auto-reset DB; check `_reset_db_if_embedding_changed` |

---

## 4. Specific anti-patterns to never introduce

| ❌ Don't | ✅ Do |
|---|---|
| `print("error...")` user-facing | `return t("common.error", error=...)` |
| `if "indexed" in agent_reply: do_thing()` | Add `[EXECUTE:/...]` tag + intercept |
| `embedding_dim = 1536` | `dim = _probe_embedding_dim(client, model, vector_dir)` |
| `questionary.text("Provider:")` in handlers | `ctx.checkpoint_handler.prompt(Checkpoint(kind="text", ...))` |
| `from armance.providers.openrouter import X` in core | `core.protocols.llm.register_client(...)` + lazy import |
| Copy-pasting a 30-line block into 3 places | Extract a helper. KISS, not WET. |
| `# TODO: fix later` | Either fix now or open an issue with the file path. Avoid silent TODOs. |
| Editing both `en.yaml` only | Always edit BOTH `en.yaml` and `fr.yaml`. |
| `try: ... except: pass` swallowing errors | At minimum `logger.exception("...")`. Better: handle specifically. |
| Re-introducing a second workflow engine | There is exactly ONE (`core.execute_workflow`) + safety-net hooks in `service/workflow_hooks.py`. The old `WorkflowEngine` was deleted as dead code. Don't bring it back. |
| Letting Armance / Malik / Kim answer the user's project question | They frame / recruit / orchestrate. **Only Mona** engages with content. Per-role tag allow-list in `service/agent_sandbox.py` enforces it. Specialists also engage with content but have no tools (except `/load-run`). |
| Shipping a default `brainstorm.yaml` (or any default workflow) | Workflows without recruited roles are meaningless. The user creates them via Kim. Do not re-add a placeholder. |
| Overwriting `.armance/exports/<wf>/run-<ts>/` on re-run | Runs are versioned. Every `/workflow run` mints a new dir. `service/workflow_runs.py` is the only place that writes there. |
| Adding a new `[EXECUTE:/...]` tag without updating `_ROLE_TAG_ALLOWLIST` | The sandbox scrubber will silently strip the tag. Always extend the allow-list in `service/agent_sandbox.py` when you add a tag. |

---

## 5. Debugging checklist

When the user reports a bug:

1. **Reproduce locally.** If you can't, ask for the exact prompt + `.armance/logs/llm_exchanges.jsonl` lines + sidebar state.
2. **Read the error.** Python tracebacks usually point at the right file. Ruff sometimes catches it before runtime.
3. **Check `_armance_concepts.md` and `ONBOARDING.md`** if the bug seems to be a misunderstanding of how Armance works.
4. **Write a failing test first** if the bug is in pure logic (not TUI rendering).
5. **Make the smallest possible patch.** No drive-by refactors.
6. **Run all three checks (Rule 7).**
7. **Commit with a tight message.**

---

## 6. When you don't understand

If the user reports a bug and you don't know what to do:

1. Read [`ONBOARDING.md`](ONBOARDING.md) — the 14-section onboarding ramp.
2. Read [`roadmap/02_architecture.md`](roadmap/02_architecture.md) — module map.
3. Look at the file the bug is in. Read the surrounding 50 lines, not just the failing line.
4. **Do not invent helpers, classes, or abstractions** that "feel right". The codebase prefers a few well-placed functions over deep class hierarchies.
5. If after all that you're still unsure: write a short comment on what you observed, do nothing destructive, and tell the user "I think the bug is in X, but I'd rather not patch blind."

That last option is the right one more often than agents think.

---

## 7. What "fixed" means

A bug is fixed when:

- The reported symptom no longer reproduces.
- All tests pass (`pytest tests/ -q` → 889).
- Ruff is clean.
- Invariants pass (31/31).
- You wrote zero new hard-coded user-facing strings.
- You introduced zero new layer violations.
- Your patch is ≤ 1 PR / 1 logical change.

If any of those is "no", you haven't fixed the bug yet.

---

## 8. Stable interfaces you must not break

These are public surfaces. Changing them breaks downstream things.

| Surface | Where |
|---|---|
| `armance.service.tui_bridge.dispatch_input(text, ctx) -> (reply, agent_name)` | TUI + future web entry |
| `armance.service.checkpoint.Checkpoint{id, prompt, kind, options}` | All interactive prompts |
| `armance.service.checkpoint.CheckpointResponse{content, is_abort}` | All interactive returns |
| `armance.core.protocols.llm.LLMClient` (embed, complete, stream_complete) | All providers |
| `armance.storage.library_state.{mark_read, unmark_read, effective_read_set}` | Library load/unload |
| `armance.service.agent_sandbox.{scrub_reply, _ROLE_TAG_ALLOWLIST}` | Per-role tag enforcement |
| `armance.service.workflow_runs.{create_run, write_step_output, write_synthesis, finalise, list_runs, load_run}` | Versioned workflow artefacts |
| `armance.service.context_service.ContextService.append_quick_freeze` | Ctrl+C×2 save path (no LLM) |
| `armance.storage.library_availability.{is_library_available, library_summary}` | Lib detection |
| Slash command names: `/help /quit /switch /model /effort /save /workflow /task /report /judge /export /deliverable /role /agent /agents /library /feedback-loop /iterate-from` | User-typed |
| `[EXECUTE:/...]` tag list (see Rule 3) | Agent prompts |

If a fix legitimately requires changing one of these, **flag it explicitly to the user before patching**. Don't sneak it in.

---

## 9. Where to push back

You will sometimes be asked to "just add a quick try/except" or "just
hard-code this string for now". The user trusts you to push back. Reply:

> *"That would violate Rule N from BUG_FIXING_GUIDE.md (rationale: ...).
> I propose instead: <alternative>. OK to proceed?"*

A short pushback is cheaper than a silent regression.

---

Welcome, fixing agent. Now go read the bug report.
