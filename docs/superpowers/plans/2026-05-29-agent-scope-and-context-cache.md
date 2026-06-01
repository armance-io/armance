# Agent Scope Boundaries + Context Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop cross-agent context leak (specialists seeing recruitment/model chatter) and replace all-or-nothing L0 freezing with an incremental, on-disk context cache that Armance promotes to L0 on confirmation.

**Architecture:** (1) A new `agent_visibility` policy module gates which conversation turns each agent sees in the DM/chat path — dropping the unconditional "all user turns" leak. (2) A first-class on-disk `cache.md` (managed by `ContextService`) becomes the shared incremental brief, injected wherever L0 is injected (host + specialist prompts), filled only by Armance, and frozen into a new L0 version on `/save` or at the Ctrl+Q gate.

**Tech Stack:** Python ≥3.11, `pytest` + `pytest-asyncio`, no real network. No users in prod → no migration / back-compat.

**Spec:** `docs/superpowers/specs/2026-05-29-agent-scope-and-context-cache-design.md`

**Commit convention:** Conventional Commits + DCO. Every commit MUST be signed off:
`git commit -s` (adds `Signed-off-by: GrIc <guillaume@richard-pro.fr>`). GPG signing
currently times out in this env — use `git -c commit.gpgsign=false commit -s ...`.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/armance/service/agent_visibility.py` | Single-source turn-visibility policy `visible_turns(turns, viewer)` | **Create** |
| `src/armance/storage/paths.py` | Add `context_cache_path(armance_root)` | Modify (~after `context_dir`, line 59-61) |
| `src/armance/service/context_service.py` | Cache read/append/clear; cache-aware quick-freeze | Modify |
| `src/armance/service/chat_handlers/specialist.py` | Use `visible_turns`; delete inline filter + `_COORD_AGENTS` | Modify (lines ~18-20, ~55-59) |
| `src/armance/service/chat_handlers/malik.py` | Use `visible_turns`; delete `_filter_history` | Modify (lines ~54, ~86-93) |
| `src/armance/service/agents/specialist_runner.py` | Inject cache in `_build_layered_context` | Modify (lines ~229-250) |
| `src/armance/service/agents/host_agent.py` | `_buffer` writes persist to cache; inject cache into Armance prompt; fullness signal; freeze consumes cache | Modify (lines ~89-118, ~182-185, ~397-510, ~1070-1077) |
| `src/armance/client/tui/screens/main.py` | Ctrl+Q gate reads `cache.md` not `host_buffer` | Modify (lines ~393-422) |
| `tests/service/test_agent_visibility.py` | Visibility policy unit tests | **Create** |
| `tests/service/test_context_cache.py` | Cache read/append/clear + freeze + injection tests | **Create** |

---

## Task 1: Visibility policy module

**Files:**
- Create: `src/armance/service/agent_visibility.py`
- Test: `tests/service/test_agent_visibility.py`

Reuses the existing `_MALIK_AGENTS` notion. The framing channel everyone
inherits is `system-context` (Armance). A turn is visible to viewer `X` iff
`turn.agent == X` OR `turn.agent` is a framing channel OR (viewer is Malik AND
`turn.agent` ∈ Malik's recruitment set). `Turn` model: `role: str`,
`content: str`, `agent: str` (see `core/models/conversation.py`).

- [ ] **Step 1: Write the failing test**

```python
# tests/service/test_agent_visibility.py
from __future__ import annotations

from armance.core.models.conversation import Turn
from armance.service.agent_visibility import visible_turns


def _t(role: str, content: str, agent: str) -> Turn:
    return Turn(role=role, content=content, agent=agent)


def test_specialist_sees_own_and_framing_not_recruitment():
    turns = [
        _t("user", "conference on climate", "system-context"),   # framing
        _t("assistant", "what audience?", "system-context"),     # framing
        _t("user", "change Samir model to gpt-oss", "system-hr"),  # Malik-directed
        _t("assistant", "updated", "system-hr"),
        _t("user", "present yourself", "Samir"),                 # own dm
    ]
    out = visible_turns(turns, "Samir")
    contents = [m["content"] for m in out]
    assert "conference on climate" in contents          # framing inherited
    assert "present yourself" in contents               # own turn
    assert "change Samir model to gpt-oss" not in contents  # recruitment leak blocked
    assert "updated" not in contents
    assert all(set(m.keys()) == {"role", "content"} for m in out)


def test_malik_sees_recruitment_crosstalk():
    turns = [
        _t("user", "recruit a scientist", "system-hr"),
        _t("assistant", "proposed Elena", "system-hr"),
        _t("user", "present yourself", "Samir"),  # specialist dm, not Malik's
    ]
    out = visible_turns(turns, "system-hr")
    contents = [m["content"] for m in out]
    assert "recruit a scientist" in contents
    assert "proposed Elena" in contents
    assert "present yourself" not in contents


def test_armance_sees_everything():
    turns = [
        _t("user", "a", "system-context"),
        _t("user", "b", "system-hr"),
        _t("user", "c", "Samir"),
    ]
    out = visible_turns(turns, "system-context")
    assert [m["content"] for m in out] == ["a", "b", "c"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/service/test_agent_visibility.py -v`
Expected: FAIL — `ModuleNotFoundError: armance.service.agent_visibility`

- [ ] **Step 3: Write minimal implementation**

```python
# src/armance/service/agent_visibility.py
"""Per-agent conversation-turn visibility policy.

Single source of truth for which past turns an agent may see in the DM/chat
path. Enforces competence boundaries: a turn directed at one agent (e.g. a
recruitment request to Malik) must NOT leak into another agent's history.

NOTE: this gates ONLY the conversational `history` list passed to the chat
path. The workflow path injects context through the system prompt and passes
NO history — it is intentionally untouched.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from armance.core.models.conversation import Turn

# Armance's framing channel — project-level context every agent inherits.
_FRAMING_AGENTS = {"system-context", "context", "armance"}

# Recruitment-relevant agents Malik may see cross-talk from. Mirrors the
# legacy malik.py _MALIK_AGENTS = {"system-hr", "malik"} (normalised to "hr"),
# plus framing, so Malik keeps its recruitment + framing context.
_MALIK_AGENTS = {"hr"}


def _norm(agent: str | None) -> str:
    return (agent or "").lower().replace("system-", "")


def visible_turns(turns: list["Turn"], viewer: str) -> list[dict[str, str]]:
    """Filter `turns` to those within `viewer`'s competence scope.

    Returns role/content dicts ready for the LLM messages list.
    """
    viewer_norm = _norm(viewer)
    is_armance = viewer_norm in {"context", "armance"} or viewer in _FRAMING_AGENTS
    is_malik = viewer_norm == "hr"

    out: list[dict[str, str]] = []
    for turn in turns:
        agent_norm = _norm(turn.agent)
        visible = (
            is_armance
            or turn.agent == viewer
            or agent_norm == viewer_norm
            or agent_norm in {_norm(a) for a in _FRAMING_AGENTS}
            or (is_malik and agent_norm in _MALIK_AGENTS)
        )
        if visible:
            out.append({"role": turn.role, "content": turn.content})
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/service/test_agent_visibility.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/armance/service/agent_visibility.py tests/service/test_agent_visibility.py
git -c commit.gpgsign=false commit -s -m "feat(service): add agent_visibility turn-scope policy"
```

---

## Task 2: Wire visibility into the specialist chat path

**Files:**
- Modify: `src/armance/service/chat_handlers/specialist.py` (lines ~18-20 `_COORD_AGENTS`, ~55-59 inline filter)

The current code (specialist.py ~55):
```python
history = [
    {"role": t.role, "content": t.content}
    for t in ctx.session.conversation.turns
    if t.role == "user" or (t.agent or "") not in _COORD_AGENTS
]
```
This is the P1 leak (`t.role == "user"` passes everything). Replace with the policy.

- [ ] **Step 1: Write the failing test**

```python
# tests/service/test_agent_visibility.py  (append)
def test_specialist_path_filter_matches_policy():
    """Regression for the incident: a specialist must not see a user turn
    that was directed at Malik."""
    from armance.core.models.conversation import Turn
    from armance.service.agent_visibility import visible_turns
    turns = [
        Turn(role="user", content="climate conference", agent="system-context"),
        Turn(role="user", content="change Mateo model", agent="system-hr"),
        Turn(role="user", content="hello Mateo", agent="Mateo"),
    ]
    out = [m["content"] for m in visible_turns(turns, "Mateo")]
    assert "change Mateo model" not in out
    assert "climate conference" in out
    assert "hello Mateo" in out
```

- [ ] **Step 2: Run test to verify it fails (or passes — it tests the policy)**

Run: `uv run pytest tests/service/test_agent_visibility.py::test_specialist_path_filter_matches_policy -v`
Expected: PASS (policy already correct). This test pins the contract the handler must use.

- [ ] **Step 3: Edit `specialist.py`**

Delete the `_COORD_AGENTS` constant block (lines ~18-20, the comment + set).
Add import near the top:
```python
from armance.service.agent_visibility import visible_turns
```
Replace the `history = [...]` comprehension with:
```python
        history = visible_turns(ctx.session.conversation.turns, agent_name)
```

- [ ] **Step 4: Run the chat-handler + visibility tests**

Run: `uv run pytest tests/service/test_agent_visibility.py tests/ -k "specialist or visibility" -v`
Expected: PASS. No reference to `_COORD_AGENTS` remains:
`grep -rn "_COORD_AGENTS" src/` → empty.

- [ ] **Step 5: Commit**

```bash
git add src/armance/service/chat_handlers/specialist.py tests/service/test_agent_visibility.py
git -c commit.gpgsign=false commit -s -m "fix(chat): gate specialist history via agent_visibility (P1 leak)"
```

---

## Task 3: Wire visibility into the Malik chat path

**Files:**
- Modify: `src/armance/service/chat_handlers/malik.py` (line ~54 call, ~86-93 `_filter_history`)

Current `_filter_history` (malik.py ~86) has the same `turn.role == "user"` leak.

- [ ] **Step 1: Confirm policy covers Malik (test already exists)**

Run: `uv run pytest tests/service/test_agent_visibility.py::test_malik_sees_recruitment_crosstalk -v`
Expected: PASS.

- [ ] **Step 2: Edit `malik.py`**

At call site (line ~54):
```python
        history = _filter_history(ctx, agent_name)
```
Replace with:
```python
        from armance.service.agent_visibility import visible_turns
        history = visible_turns(ctx.session.conversation.turns, agent_name)
```
Delete the `_filter_history` function (lines ~86-93). `_MALIK_AGENTS`
(line ~23, `{"system-hr", "malik"}`) is referenced ONLY by `_filter_history`
(verified: `grep -n "_MALIK_AGENTS" src/armance/service/chat_handlers/malik.py`
returns lines 23 + 91 only) — so delete that constant too. Re-run the grep
after editing to confirm it returns empty.

- [ ] **Step 3: Run the malik tests**

Run: `uv run pytest tests/ -k "malik or hr or visibility" -v`
Expected: PASS. `grep -rn "_filter_history" src/` → empty.

- [ ] **Step 4: Commit**

```bash
git add src/armance/service/chat_handlers/malik.py
git -c commit.gpgsign=false commit -s -m "fix(chat): gate Malik history via agent_visibility (P1 leak)"
```

---

## Task 4: Cache storage path + ContextService cache API

**Files:**
- Modify: `src/armance/storage/paths.py` (after `context_dir`, ~line 61)
- Modify: `src/armance/service/context_service.py`
- Test: `tests/service/test_context_cache.py`

Cache is a single markdown file `.armance/context/cache.md`. Append adds a
blank-line-separated note; read returns the whole body; clear empties it.

- [ ] **Step 1: Write the failing test**

```python
# tests/service/test_context_cache.py
from __future__ import annotations

from pathlib import Path

from armance.service.context_service import ContextService
from armance.storage.paths import context_cache_path


def test_cache_roundtrip(tmp_path: Path):
    root = tmp_path / ".armance"
    svc = ContextService(root)
    assert svc.read_cache() == ""          # empty / missing → ""
    svc.cache_append("forest restoration near town")
    svc.cache_append("audience: civil society")
    body = svc.read_cache()
    assert "forest restoration near town" in body
    assert "audience: civil society" in body
    assert context_cache_path(root).exists()
    svc.clear_cache()
    assert svc.read_cache() == ""


def test_cache_full_threshold(tmp_path: Path):
    svc = ContextService(tmp_path / ".armance")
    assert svc.cache_is_full() is False
    svc.cache_append("x" * 1600)
    assert svc.cache_is_full() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/service/test_context_cache.py -v`
Expected: FAIL — `ImportError: cannot import name 'context_cache_path'`

- [ ] **Step 3a: Add the path helper**

In `src/armance/storage/paths.py`, after the `context_dir` function (line ~61):
```python
def context_cache_path(armance_root: Path) -> Path:
    """Pending shared-context cache (incremental brief, pre-freeze)."""
    return context_dir(armance_root) / "cache.md"
```

- [ ] **Step 3b: Add cache API to `ContextService`**

In `src/armance/service/context_service.py`, add to the class (after
`append_quick_freeze`, ~line 58). Add `CACHE_FULL_CHARS = 1500` as a class
constant near the top of the class body:
```python
    CACHE_FULL_CHARS = 1500  # cache proposes a freeze past this size

    def _cache_path(self):
        from armance.storage.paths import context_cache_path
        return context_cache_path(self.armance_root)

    def read_cache(self) -> str:
        """Return the pending cache body, or '' if missing/unreadable."""
        path = self._cache_path()
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            logger.debug("cache read failed", exc_info=True)
            return ""

    def cache_append(self, note: str) -> None:
        """Append a worth-saving note to the cache (Armance only)."""
        note = (note or "").strip()
        if not note:
            return
        path = self._cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.read_cache()
        body = f"{existing}\n\n{note}".strip() if existing else note
        try:
            path.write_text(body + "\n", encoding="utf-8")
        except Exception:
            logger.exception("cache append failed")

    def clear_cache(self) -> None:
        path = self._cache_path()
        try:
            if path.exists():
                path.unlink()
        except Exception:
            logger.debug("cache clear failed", exc_info=True)

    def cache_is_full(self) -> bool:
        return len(self.read_cache()) >= self.CACHE_FULL_CHARS
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/service/test_context_cache.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/armance/storage/paths.py src/armance/service/context_service.py tests/service/test_context_cache.py
git -c commit.gpgsign=false commit -s -m "feat(context): add on-disk cache.md layer to ContextService"
```

---

## Task 5: Inject cache into specialist context (chat + workflow)

**Files:**
- Modify: `src/armance/service/agents/specialist_runner.py` (`_build_layered_context`, ~line 229-250)
- Test: `tests/service/test_context_cache.py` (append)

Cache appended right after L0 so every specialist — chat or workflow — sees the
shared brief. The workflow path is exercised because `_build_layered_context`
runs in both.

- [ ] **Step 1: Write the failing test**

```python
# tests/service/test_context_cache.py  (append)
def test_layered_context_includes_cache(tmp_path: Path):
    from armance.core.models.agent import Agent
    from armance.service.agents.specialist_runner import SpecialistRunner

    root = tmp_path / ".armance"
    ContextService(root).cache_append("forest restoration is the takeaway")

    runner = SpecialistRunner(root, config=None)
    agent = Agent(
        name="Samir", role="communicant", domain="communication",
        provider="openrouter", model="x",
    )
    ctx = runner._build_layered_context(agent)
    assert "forest restoration is the takeaway" in ctx
```

(If `Agent(...)` requires more fields, mirror an existing fixture in
`tests/` — search `grep -rn "Agent(" tests/ | head`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/service/test_context_cache.py::test_layered_context_includes_cache -v`
Expected: FAIL — cache string absent from context.

- [ ] **Step 3: Edit `_build_layered_context`**

In `specialist_runner.py`, inside `_build_layered_context`, right after the L0
block (after line ~234, before the L1 block):
```python
        # Shared incremental brief: pending cache notes (Armance-owned).
        cache_body = self.context_service.read_cache()
        if cache_body:
            parts.append(f"## Shared notes (pending context)\n\n{cache_body}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/service/test_context_cache.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/armance/service/agents/specialist_runner.py tests/service/test_context_cache.py
git -c commit.gpgsign=false commit -s -m "feat(context): inject cache into specialist layered context"
```

---

## Task 6: Armance writes to cache + injects it + freeze consumes it

**Files:**
- Modify: `src/armance/service/agents/host_agent.py` (buffer accumulation ~182-185, `_build_system_prompt` ~1070, `freeze` ~408 & ~510)

Repurpose the in-memory `_buffer` so accumulation ALSO persists to `cache.md`,
Armance's prompt shows the cache, and `freeze` reads the cache (then clears it).
The in-memory `_buffer` stays for the same-process flow; `cache.md` is the
durable shared copy.

- [ ] **Step 1: Write the failing test**

```python
# tests/service/test_context_cache.py  (append)
import pytest


@pytest.mark.asyncio
async def test_freeze_consumes_cache(tmp_path, monkeypatch):
    """freeze() should fold cache.md into L0 and then clear the cache."""
    from armance.service.context_service import ContextService
    from armance.service.agents import host_agent as ha

    root = tmp_path / ".armance"
    svc = ContextService(root)
    svc.cache_append("audience: civil society; topic: forest restoration")

    # Stub the LLM compile so no network: return a fixed body.
    class _Resp:
        text = "## Goal\nForest restoration conference for civil society.\n"
        finish_reason = "stop"

    async def _fake_call(*a, **k):
        return _Resp()

    monkeypatch.setattr(ha, "call_with_ledger", _fake_call)

    # Build a minimal host agent. Mirror an existing host_agent test fixture
    # (search: grep -rn "HostAgentService(" tests/).
    host = ha.HostAgentService.__new__(ha.HostAgentService)
    host.armance_root = root
    host.agent = type("A", (), {
        "provider": "openrouter", "model": "x", "name": "Armance",
        "effective_system_prompt": lambda self, **k: "sys",
    })()
    host.config = None
    host._buffer = []
    from armance.core.models.conversation import Conversation
    host.conversation = Conversation(agent="Armance")

    await host.freeze()
    assert svc.read_cache() == ""                     # cache cleared
    assert svc.read_l0_body()                          # L0 written
```

(Adjust the `__new__` fixture to match the real constructor if a simpler
factory exists in `tests/` — search `grep -rn "HostAgentService" tests/`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/service/test_context_cache.py::test_freeze_consumes_cache -v`
Expected: FAIL — cache not consumed by freeze (still references `_buffer` only).

- [ ] **Step 3a: Persist buffer notes to cache on accumulation**

In `host_agent.py` ~line 182-185, replace:
```python
        stripped = user_text.strip()
        if stripped and not self._is_greeting(stripped):
            self._buffer.append(stripped)
```
with:
```python
        stripped = user_text.strip()
        if stripped and not self._is_greeting(stripped):
            self._buffer.append(stripped)
            try:
                from armance.service.context_service import ContextService
                ContextService(self.armance_root).cache_append(stripped)
            except Exception:
                logger.debug("cache append from buffer failed", exc_info=True)
```

- [ ] **Step 3b: freeze() reads cache; clears it after write**

In `freeze` (~line 408), replace:
```python
        buffer_content = "\n".join(self._buffer).strip()
```
with:
```python
        ctx_svc_cache = ctx_svc.read_cache()
        buffer_content = (ctx_svc_cache or "\n".join(self._buffer)).strip()
```
And at the buffer clear (~line 510) `self._buffer.clear()`, add right after:
```python
        ctx_svc.clear_cache()
```

- [ ] **Step 3c: Inject cache into Armance's own prompt**

In `_build_system_prompt` (~line 1070), after the project-brief block, add:
```python
        # Pending shared cache (incremental notes not yet frozen into L0).
        try:
            from armance.service.context_service import ContextService
            _cache = ContextService(self.armance_root).read_cache()
            if _cache:
                sections.append(
                    "## Pending context cache (not yet saved)\n"
                    f"{_cache}\n"
                    "When this looks like a coherent milestone (or it grows large), "
                    "propose saving it: recap what you'd add, then emit "
                    "[EXECUTE:/save] ONLY after the user confirms."
                )
        except Exception:
            logger.debug("cache inject failed", exc_info=True)
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/service/test_context_cache.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/armance/service/agents/host_agent.py tests/service/test_context_cache.py
git -c commit.gpgsign=false commit -s -m "feat(context): Armance writes/reads cache; freeze folds and clears it"
```

---

## Task 7: Ctrl+Q gate reads cache.md

**Files:**
- Modify: `src/armance/client/tui/screens/main.py` (`_quit_with_save_prompt`, ~393-422)

The gate currently reads `host_buffer` from session metadata. Switch it to the
durable cache so non-empty cache → save-or-dismiss, empty → silent quit.

- [ ] **Step 1: Edit `_quit_with_save_prompt`**

Replace the body (lines ~396-417) so it reads/clears the cache:
```python
        from armance.service.context_service import ContextService
        svc = ContextService(self.armance_root)
        cache = svc.read_cache()
        if not cache:
            self.app.exit(0)
            return
        try:
            from armance.service.checkpoint import Checkpoint
            handler = self._loop_ctx.checkpoint_handler if self._loop_ctx else None
            if handler is None:
                self.app.exit(0)
                return
            resp = await handler.prompt(
                Checkpoint(id="quit.save", prompt=_t("quit.save_prompt"), kind="confirm")
            )
            if not resp.is_abort and resp.content == "yes":
                try:
                    svc.append_quick_freeze(cache)
                    svc.clear_cache()
                    self.session.save()
                    self.notify(_t("quit.saved"), severity="information", timeout=2)
                except Exception:
                    logger.exception("quit save failed")
            else:
                # Dismiss: drop the cache, keep the last L0 version.
                svc.clear_cache()
        except Exception:
            logger.exception("quit prompt failed")
        self.app.exit(0)
```
Remove the now-dead `buffer = list(self.session.metadata.get("host_buffer", []))`
line and the `self.session.metadata["host_buffer"] = []` line.

- [ ] **Step 2: Verify the TUI module imports cleanly**

Run: `uv run python -c "import armance.client.tui.screens.main"`
Expected: no error.

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS (no regressions). Note any pre-existing failures unrelated to
this change and report them rather than "fixing" silently.

- [ ] **Step 4: Commit**

```bash
git add src/armance/client/tui/screens/main.py
git -c commit.gpgsign=false commit -s -m "feat(tui): Ctrl+Q save/dismiss gate reads context cache"
```

---

## Task 8: Final verification + incident regression check

**Files:** none (verification only)

- [ ] **Step 1: Lint the layering invariant**

Run: `grep -rn "from armance.client" src/armance/core src/armance/service`
Expected: empty (no upper-layer imports).

- [ ] **Step 2: Confirm both leaky filters are gone**

Run: `grep -rn "_COORD_AGENTS\|_filter_history" src/`
Expected: empty.

- [ ] **Step 3: Full offline suite**

Run: `uv run pytest tests/ -q`
Expected: PASS.

- [ ] **Step 4: Manual incident trace (documented, not automated)**

Re-read `tmp/runtime/conversations/f3904b57203c.md`. Confirm by inspection that
with `visible_turns`, when "Samir / present yourself" is asked, the
`user→system-hr` "change Samir model" turns are excluded from his history, and
the cache holds the project framing instead. No code change — this is the
acceptance argument for P1.

- [ ] **Step 5: Final commit (if any doc/notes updated)**

```bash
git -c commit.gpgsign=false commit -s -am "chore: convergence scope+cache verification" || true
```

---

## Self-review notes

- **Spec coverage:** P1 (Tasks 1-3), cache artifact + API (Task 4), shared-brief
  injection host+specialist+workflow (Tasks 5-6), fullness/recap-propose (Task 6
  prompt + `cache_is_full`), freeze folds+clears (Task 6), Ctrl+Q gate (Task 7),
  workflow-path-untouched (asserted in Task 5, verified Task 8). All covered.
- **No migration:** no `host_buffer` seeding — per "no users" decision the
  in-memory buffer simply co-writes to cache; nothing reads the old metadata key
  for context anymore.
- **Type consistency:** `visible_turns(turns, viewer) -> list[dict]`,
  `read_cache()->str`, `cache_append(note)`, `clear_cache()`, `cache_is_full()->bool`,
  `context_cache_path(root)->Path` — names identical across all tasks.
- **Open risk flagged for executor:** the host_agent freeze test fixture uses
  `__new__` to dodge the real constructor; if a cleaner test factory exists in
  `tests/`, prefer it. Same for the `Agent(...)` fixture in Task 5.
