"""Live QA script — tests Armance end-to-end without TUI.

Scenarios:
  A — Armance context gathering (semantic quality, RAG hint)
  B — Malik recruitment + Serge inclusion
  C — Agent dismissal ([EXECUTE:/dismiss-all])
  D — Re-recruit for workflow testing
  E — Kim interactive chat (LLM)
  F — Workflow design dialogue (S0 → S6)
  G — Workflow execution (brainstorm)
  H — Model discovery filtering
  I — Cost estimation
  R — RAG round-trip (docs awareness)
  L — Language switch (en → es)
  M — Workflow tailoring differentiation
  J — Checkpoint round-trip with AutoApproveCheckpointHandler
  K — Deliverable rendering (.md / .docx bytes on disk)
  N — Rich-engine consensus / Serge auto-invoke (signal-only until P1.1)

Run:
  uv run python scripts/qa_live.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
import textwrap
import time
from pathlib import Path

# Add src to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from armance.config import load_config, ensure_armance_tree
from armance.service.llm_service import TokenLedger, set_ledger
from armance.service.session import start_or_resume, Session
from armance.service.tui_bridge import make_loop_context, dispatch_input
from armance.service.checkpoint import CheckpointResponse

class AutoApproveCheckpointHandler:
    """Non-interactive checkpoint handler for QA.

    Returns canned responses tailored to the checkpoint kind so qa_live
    can run /workflow run, /model, /effort without a TTY:
      - text    -> "approved"
      - select  -> first choice from options['choices']
      - confirm -> "yes"
    """
    async def prompt(self, checkpoint) -> CheckpointResponse:
        kind = getattr(checkpoint, "kind", "text") or "text"
        if kind == "confirm":
            return CheckpointResponse(content="yes")
        if kind == "select":
            choices = (getattr(checkpoint, "options", {}) or {}).get("choices") or []
            return (
                CheckpointResponse(content=str(choices[0])) if choices
                else CheckpointResponse(content="", is_abort=True)
            )
        return CheckpointResponse(content="approved")

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)

# ── colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

_issues: list[str] = []
_passes: list[str] = []


def ok(label: str, note: str = "") -> None:
    msg = f"{GREEN}✓{RESET} {label}" + (f"  — {note}" if note else "")
    print(msg)
    _passes.append(label)


def fail(label: str, detail: str = "") -> None:
    msg = f"{RED}✗{RESET} {BOLD}{label}{RESET}" + (f"\n    {detail}" if detail else "")
    print(msg)
    _issues.append(f"{label}: {detail}")


def warn(label: str, detail: str = "") -> None:
    msg = f"{YELLOW}⚠{RESET} {label}" + (f"\n    {detail}" if detail else "")
    print(msg)
    _issues.append(f"WARN {label}: {detail}")


def section(title: str) -> None:
    print(f"\n{CYAN}{BOLD}{'─'*60}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{'─'*60}{RESET}")


def show_reply(reply: str, maxlen: int = 400) -> None:
    snippet = reply[:maxlen].replace("\n", " ↩ ")
    print(f"  {YELLOW}reply:{RESET} {snippet}{'…' if len(reply) > maxlen else ''}")


# ── main QA runner ───────────────────────────────────────────────────────────

_COMPLEX_AGENTS = {"system-hr", "system-orchestrator"}

# Hard fallbacks if discovery returns nothing
_FALLBACK_FREE = "openai/gpt-oss-20b:free"
_FALLBACK_FREE_COMPLEX = "google/gemma-4-31b-it:free"


async def _pick_free_models() -> tuple[str, str]:
    """Pick the cheapest free models from live OpenRouter discovery.

    Returns (QA_MODEL, QA_MODEL_COMPLEX). Falls back on hardcoded ids
    if discovery is empty (offline / API blip).
    """
    from armance.providers.model_discovery import discover_openrouter_models
    tiers = await discover_openrouter_models()
    free = [m for m in tiers.get("free-first", []) if ":free" in m]
    if not free:
        return _FALLBACK_FREE, _FALLBACK_FREE_COMPLEX
    # Prefer non-omni/reasoning-only ids for default
    def _good_default(mid: str) -> bool:
        bad = ("ocr", "vision", "guard", "moderat", "thinking", "reasoning",
               "ring-", "dolphin", "venice", "omni")
        return not any(b in mid.lower() for b in bad)
    primary = next((m for m in free if _good_default(m)), free[0])
    complex_pool = [m for m in free if _good_default(m) and m != primary]
    secondary = complex_pool[len(complex_pool) // 2] if complex_pool else primary
    return primary, secondary


async def run_qa() -> None:
    armance_root = ROOT
    cfg = load_config(armance_root)
    QA_MODEL, QA_MODEL_COMPLEX = await _pick_free_models()
    print(f"{CYAN}QA models — default: {QA_MODEL} | complex: {QA_MODEL_COMPLEX}{RESET}")
    cfg.default_model = QA_MODEL  # force free model for all QA calls
    ensure_armance_tree(armance_root, cfg)

    state = start_or_resume(armance_root / ".armance", resume=False)
    session = Session(state, armance_root / ".armance")
    ledger = TokenLedger()
    set_ledger(ledger)

    ctx = make_loop_context(
        armance_root / ".armance",
        cfg,
        state,
        session,
        ledger,
        checkpoint_handler=AutoApproveCheckpointHandler(),
    )
    ctx.state.current_agent = "system-context"

    # Patch system agent files: complex agents get stronger model, rest get QA_MODEL
    import re as _re
    agents_dir = armance_root / ".armance" / "agents"
    for agent_path in agents_dir.glob("system-*.md"):
        model = QA_MODEL_COMPLEX if agent_path.stem in _COMPLEX_AGENTS else QA_MODEL
        content = agent_path.read_text()
        content = _re.sub(r"^model:.*$", f"model: {model}", content, flags=_re.MULTILINE)
        agent_path.write_text(content)
    for a in ctx.agents:
        if a.name.startswith("system-"):
            a.model = QA_MODEL_COMPLEX if a.name in _COMPLEX_AGENTS else QA_MODEL

    async def send(text: str) -> tuple[str, str | None]:
        t0 = time.monotonic()
        reply, agent = await dispatch_input(text, ctx)
        elapsed = time.monotonic() - t0
        print(f"  {CYAN}[{agent or '?'} {elapsed:.1f}s]{RESET}")
        show_reply(reply)
        return reply, agent

    # =========================================================================
    section("A — Armance: context gathering quality")
    # =========================================================================

    ctx.state.current_agent = "system-context"

    r, ag = await send("Bonjour !")
    if ag and "context" in (ag or ""):
        ok("A1 armance routes greeting to context agent")
    else:
        warn("A1 agent routing", f"expected system-context, got {ag}")

    if "Armance" in r or "armance" in r.lower() or "bonjour" in r.lower() or "bienvenue" in r.lower():
        ok("A2 armance introduces himself in greeting")
    else:
        warn("A2 armance greeting content", "no self-intro or welcome in reply")

    if ".armance/docs" in r or "docs" in r.lower() or "document" in r.lower():
        ok("A3 armance mentions docs folder in greeting")
    else:
        warn("A3 RAG guidance absent from greeting", "no mention of .armance/docs")

    # Give a thin project description and check Armance does NOT immediately propose /save
    r, ag = await send("Je veux créer une application mobile.")
    if "[EXECUTE:/save]" in r:
        fail("A4 armance proposes /save too early", "thin description → should ask more questions first")
    else:
        ok("A4 armance does not /save on thin description")

    # Add more context
    r, _ = await send(
        "C'est une appli de gestion de temps pour des freelances, en France, "
        "budget serré 3 mois, stack React Native. Le défi : les freelances ne "
        "suivent jamais leur temps, on cherche à comprendre pourquoi."
    )
    if "?" in r:
        ok("A5 armance asks focused follow-up question")
    else:
        warn("A5 armance follow-up", "no question after richer context")

    # =========================================================================
    section("B — Malik: recruitment + Serge")
    # =========================================================================

    ctx.state.current_agent = "system-hr"

    r, ag = await send(
        "@Malik, recrute une équipe pour analyser pourquoi les freelances "
        "ne suivent pas leur temps. Projet mobile, public FR, 3 mois."
    )

    if "cato" in r.lower() or "criticalist" in r.lower() or "critic" in r.lower():
        ok("B1 Malik includes Serge in recruitment plan")
    else:
        fail("B1 Serge absent from Malik's plan", "Malik should always include Serge")

    if "model" in r.lower() or "🟢" in r or "🟡" in r or "🔴" in r:
        ok("B2 Malik shows models with cost indicators")
    else:
        warn("B2 model cost indicators absent", "should show 🟢/🟡/🔴 per agent")

    if "kim" in r.lower() or "workflow" in r.lower():
        ok("B3 Malik mentions Kim/workflows for Serge")
    else:
        warn("B3 Malik doesn't explain Serge's role in workflows")

    # Confirm recruitment
    r, _ = await send("Oui, vas-y !")
    if "[EXECUTE:/recruit]" in r or "recruté" in r.lower() or "recruited" in r.lower() or "créé" in r.lower():
        ok("B4 Malik executes recruitment on confirmation")
    else:
        warn("B4 recruitment execution", f"expected [EXECUTE:/recruit] or confirmation message")

    # Check files created
    agents_dir = armance_root / ".armance" / "agents"
    user_agents = [p for p in agents_dir.glob("*.md") if not p.stem.startswith("system-")]
    if user_agents:
        ok(f"B5 agent files created on disk", f"{len(user_agents)} files: {[p.stem for p in user_agents]}")
        # Reload agents
        from armance.service.tui_bridge import load_user_agents
        ctx.agents = load_user_agents(armance_root / ".armance")
    else:
        fail("B5 no agent files created", "expected .md files in .armance/agents/")

    serge_file = next((p for p in user_agents if "cato" in p.stem.lower() or "critic" in p.stem.lower()), None)
    if serge_file:
        ok("B6 Serge file exists on disk", serge_file.stem)
    else:
        fail("B6 Serge file missing", f"files: {[p.stem for p in user_agents]}")

    # =========================================================================
    section("C — Agent dismissal")
    # =========================================================================

    r, _ = await send("Vire tous les agents, on repart de zéro.")

    if "[EXECUTE:/dismiss-all]" in r or "supprimer" in r.lower() or "dismiss" in r.lower() or "confirmez" in r.lower() or "confirmer" in r.lower():
        ok("C1 Malik proposes dismiss / asks confirmation")
    else:
        fail("C1 no dismiss proposal", f"reply: {r[:200]}")

    # Confirm dismiss
    r, _ = await send("Oui, confirme.")
    if "System:" in r and ("dismissed" in r or "supprimé" in r.lower()):
        ok("C2 dismiss-all executed by system")
    elif "[EXECUTE:/dismiss-all]" in r:
        ok("C2 dismiss-all tag emitted")
    else:
        warn("C2 dismiss execution unclear", f"reply: {r[:200]}")

    # Check files gone
    remaining = [p for p in agents_dir.glob("*.md") if not p.stem.startswith("system-")]
    if not remaining:
        ok("C3 all user agent files deleted from disk")
    else:
        fail("C3 agent files still present after dismiss", f"{[p.stem for p in remaining]}")

    # Reload ctx.agents
    from armance.service.tui_bridge import load_user_agents
    ctx.agents = load_user_agents(armance_root / ".armance")

    # =========================================================================
    section("D — Re-recruit for workflow testing")
    # =========================================================================

    ctx.state.current_agent = "system-hr"
    r, _ = await send(
        "@Malik, recrute 2 experts UX et un criticalist Serge pour le projet freelance app mobile."
    )
    r, _ = await send("Oui, go !")

    ctx.agents = load_user_agents(armance_root / ".armance")
    user_agents = [p for p in agents_dir.glob("*.md") if not p.stem.startswith("system-")]
    if user_agents:
        ok(f"D1 re-recruited {len(user_agents)} agents", f"{[p.stem for p in user_agents]}")
    else:
        fail("D1 re-recruitment failed", "no agent files")

    # =========================================================================
    section("E — Kim: interactive chat (LLM)")
    # =========================================================================

    ctx.state.current_agent = "system-orchestrator"

    r, ag = await send("Kim, explique-moi comment fonctionne un workflow dans Armance.")
    if ag and "orchestrator" in (ag or ""):
        ok("E1 Kim chat routes to system-orchestrator")
    else:
        warn("E1 agent routing", f"got {ag}")

    # Key check: is this a real LLM response or the old state machine?
    state_machine_keywords = ["Quel est l'objectif du workflow", "3 formes possibles", "short / standard / deep"]
    is_state_machine = any(kw in r for kw in state_machine_keywords)
    if is_state_machine and "workflow" in r.lower() and "?" in r:
        warn("E2 Kim may be stuck in DesignWorkflowSkill state machine",
             "Expected free LLM response to explanation question")
    elif len(r) > 100 and ("étape" in r.lower() or "step" in r.lower() or "délibér" in r.lower() or "juge" in r.lower() or "agent" in r.lower()):
        ok("E2 Kim gives real LLM explanation of workflows")
    else:
        warn("E2 Kim explanation quality", f"short or off-topic: {r[:200]}")

    if "cato" in r.lower():
        ok("E3 Kim mentions Serge in workflow explanation")
    else:
        warn("E3 Serge not mentioned in workflow explanation")

    r, _ = await send("Quel workflow me recommandes-tu pour ce projet ?")
    if any(k in r.lower() for k in ["short", "standard", "deep", "court", "profond"]):
        ok("E4 Kim recommends workflow options")
    else:
        warn("E4 Kim recommendation quality", "no workflow options mentioned")

    if "🟢" in r or "🟡" in r or "🟠" in r or "🔴" in r or "$" in r or "free" in r.lower() or "coût" in r.lower() or "cost" in r.lower():
        ok("E5 Kim includes cost indicators in recommendation")
    else:
        warn("E5 cost indicators absent from Kim recommendation")

    # =========================================================================
    section("F — Workflow design dialogue (DesignWorkflowSkill)")
    # =========================================================================

    ctx.state.current_agent = "system-orchestrator"

    r, _ = await send("Je veux créer un workflow 'analyse-freelance' pour analyser notre problème.")
    if any(k in r.lower() for k in ["objectif", "livrable", "décision", "exploration", "workflow"]):
        ok("F1 workflow design dialogue started (S1)")
    else:
        warn("F1 design dialogue start", f"unexpected reply: {r[:200]}")

    r, _ = await send("Un rapport d'analyse avec recommandations UX.")
    if any(k in r.lower() for k in ["short", "standard", "deep", "formes", "forme"]):
        ok("F2 Kim proposes skeleton shapes (S2)")
    else:
        warn("F2 skeleton proposal", f"expected 3 shapes, got: {r[:200]}")

    if "🟢" in r or "🟡" in r or "🟠" in r or "🔴" in r or "$" in r or "free" in r.lower() or "gratuit" in r.lower():
        ok("F3 cost labels visible in skeleton proposal")
    else:
        warn("F3 cost labels absent from skeleton proposal", "expected 🟢/🟡/🟠/🔴 or $ amounts")

    r, _ = await send("standard")
    if "étape" in r.lower() or "step" in r.lower() or "analyse" in r.lower() or "ok" in r.lower():
        ok("F4 standard skeleton selected (S3)")
    else:
        warn("F4 skeleton selection", f"unexpected: {r[:200]}")

    r, _ = await send("ok")
    if "input" in r.lower() or "paramètre" in r.lower() or "ok" in r.lower() or "mode" in r.lower():
        ok("F5 S3→S4 transition")
    else:
        warn("F5 S4 transition", f"got: {r[:200]}")

    r, _ = await send("ok")  # S4→S5 (mode/yolo prompt)
    if "mode" in r.lower() or "yolo" in r.lower() or "coût" in r.lower() or "cost" in r.lower():
        ok("F6 S4→S5 transition (mode/cost display)")
    else:
        warn("F6 S5 display", f"got: {r[:200]}")

    r, _ = await send("ok")  # S5→S6 (confirm write prompt)
    if "enregistre" in r.lower() or "confirme" in r.lower() or "yaml" in r.lower() or ".armance" in r.lower():
        ok("F6b S5→S6 transition (confirm write prompt)")
    else:
        warn("F6b S6 transition", f"got: {r[:200]}")

    r, _ = await send("ok")  # S6→write
    wf_dir = armance_root / ".armance" / "workflows"
    wf_files = list(wf_dir.glob("*.yaml")) if wf_dir.exists() else []
    non_default = [f for f in wf_files if "brainstorm" not in f.stem]
    if non_default:
        ok("F7 workflow YAML created on disk", f"{[f.stem for f in non_default]}")
    else:
        warn("F7 no custom workflow yaml found", f"dir: {wf_dir}, files: {[f.stem for f in wf_files]}")

    # =========================================================================
    section("G — Workflow execution")
    # =========================================================================

    # Find a workflow to run
    all_wf = list(wf_dir.glob("*.yaml")) if wf_dir.exists() else []
    run_target = next((f for f in all_wf if "brainstorm" not in f.stem), None) or next(iter(all_wf), None)

    if not run_target:
        fail("G1 no workflow to run")
    else:
        ok(f"G1 workflow to run: {run_target.stem}")
        ctx.state.current_agent = "system-context"
        ctx.state.project_brief = (
            "Application mobile de suivi de temps pour freelances français. "
            "Stack React Native, budget 3 mois, public freelances FR. "
            "Défi: comprendre pourquoi les freelances ne suivent pas leur temps."
        )

        # Call handler directly to bypass questionary (non-TTY context)
        from armance.service.handlers import _cmd_workflow_run
        r = await _cmd_workflow_run(
            run_target.stem, enrich_sid=None, ctx=ctx,
            skip_preflight=True,
            user_prompt_override=ctx.state.project_brief,
        )
        _ = ctx.state.current_agent
        if "error" in r.lower() and ("not found" in r.lower() or "introuvable" in r.lower()):
            fail("G2 workflow run failed — not found", r[:200])
        elif "error" in r.lower():
            fail("G2 workflow run error", r[:200])
        elif any(k in r.lower() for k in ["résultat", "result", "synthèse", "rapport", "analyse", "délibér", "complet"]):
            ok("G2 workflow execution produced output")
        else:
            warn("G2 workflow output unclear", r[:300])

        # Check reports generated
        reports_dir = armance_root / ".armance" / "reports"
        report_files = list(reports_dir.glob("**/*.md")) if reports_dir.exists() else []
        if report_files:
            ok(f"G3 reports generated", f"{len(report_files)} file(s)")
        else:
            warn("G3 no report files found in .armance/reports/")

    # =========================================================================
    section("H — Model discovery filtering")
    # =========================================================================

    from armance.providers.model_discovery import _is_text_chat_model
    blocked = ["openai/dall-e-3", "openai/whisper-1", "meta/llama-guard-2-8b", "google/gemma-2-9b-it:vision"]
    allowed = ["openai/gpt-4o", "meta/llama-3-70b-instruct", "mistralai/mistral-7b"]
    all_ok = True
    for m in blocked:
        if _is_text_chat_model(m):
            fail(f"H filter: {m} should be blocked")
            all_ok = False
    for m in allowed:
        if not _is_text_chat_model(m):
            fail(f"H filter: {m} should be allowed")
            all_ok = False
    if all_ok:
        ok("H1 model discovery filter correct (blocked OCR/vision/audio, allowed text)")

    # =========================================================================
    section("I — Cost estimation")
    # =========================================================================

    from armance.service.cost import estimate_workflow, PRICES
    # Build fake workflow with known agents
    class _S:
        def __init__(self, id, kind):
            self.id = id; self.kind = kind; self.agents = []; self.mode = "full"
    class _W:
        def __init__(self): self.steps = [_S("s1","task"), _S("j1","judge")]

    fake_agents = ctx.agents if ctx.agents else []
    est = estimate_workflow(_W(), fake_agents, "test prompt")
    if isinstance(est["total_usd"], (int, float)):
        ok("I1 estimate_workflow returns valid USD total", f"${est['total_usd']:.4f}")
    else:
        fail("I1 cost estimation broken")

    # =========================================================================
    section("R — RAG round-trip (docs awareness)")
    # =========================================================================

    docs_dir = armance_root / ".armance" / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    nugget_file = docs_dir / "qa_nugget.md"
    nugget = "PROJECT-CODE-NAME: Zephyr-7491. The fox jumps at midnight."
    nugget_file.write_text(f"# QA Nugget\n\n{nugget}\n", encoding="utf-8")
    try:
        from armance.storage.ingestion import sync_docs
        sync_docs(armance_root / ".armance", config=cfg)
        ctx.state.current_agent = "system-context"
        r, _ = await send("Quel est le nom de code du projet d'après nos documents ?")
        if "zephyr" in r.lower() or "7491" in r:
            ok("R1 RAG nugget reached Armance's reply")
        else:
            warn("R1 RAG nugget absent from reply", r[:200])
    finally:
        try:
            nugget_file.unlink()
            sync_docs(armance_root / ".armance", config=cfg)
        except Exception:
            pass

    # =========================================================================
    section("L — Language switch")
    # =========================================================================

    cfg.language = "es"
    ctx.state.current_agent = "system-context"
    r, _ = await send("Hola, ¿cómo estás?")
    # Spanish markers
    es_markers = ["soy", "está", "hola", "buenos", "puedo", "señor"]
    if any(k in r.lower() for k in es_markers):
        ok("L1 voice overlay routes Armance to Spanish")
    else:
        warn("L1 Spanish overlay not effective", r[:200])
    cfg.language = "en"

    # =========================================================================
    section("M — Workflow tailoring differentiation")
    # =========================================================================

    # Inspect the two YAML files produced in F: their step ids should differ
    # if LLM tailoring works. Otherwise both = literal template.
    wf_dir = armance_root / ".armance" / "workflows"
    user_wfs = [p for p in wf_dir.glob("*.yaml") if "brainstorm" not in p.stem]
    step_id_sets = []
    for p in user_wfs[:4]:
        try:
            import yaml as _y
            d = _y.safe_load(p.read_text()) or {}
            sids = tuple((s.get("id") or "") for s in (d.get("steps") or []))
            step_id_sets.append(sids)
        except Exception:
            pass
    distinct = len(set(step_id_sets))
    if distinct >= 2:
        ok(f"M1 workflows have distinct step ids ({distinct} variants)")
    else:
        warn("M1 all generated workflows share identical step ids", f"{step_id_sets}")

    # =========================================================================
    section("J — Checkpoint round-trip (AutoApproveCheckpointHandler)")
    # =========================================================================
    #
    # Write a tiny workflow with a human_checkpoint step, run it with the
    # auto-approve handler, assert the downstream step receives the checkpoint
    # output as a template variable.

    wf_path = armance_root / ".armance" / "workflows" / "qa_checkpoint.yaml"
    wf_path.parent.mkdir(parents=True, exist_ok=True)
    wf_path.write_text(
        "name: qa_checkpoint\nsteps:\n"
        "  - id: gather\n    kind: human_checkpoint\n    prompt: 'qa-checkpoint?'\n"
        "    save_to_context: false\n"
        "  - id: echo\n    kind: task\n    domain: specialist\n"
        "    depends_on: [gather]\n    prompt_template: 'You answered: {{gather.output}}'\n",
        encoding="utf-8",
    )
    try:
        r, _ = await dispatch_input("/workflow run qa_checkpoint", ctx)
        # AutoApprove returns content='approved' for text kind. Downstream
        # step's prompt should reference it.
        if "approved" in (r or "").lower():
            ok("J1 checkpoint output flows to downstream step")
        else:
            warn("J1 checkpoint output did not reach the downstream step", r[:200])
    except Exception as exc:
        warn("J1 checkpoint workflow run errored", str(exc)[:200])

    # =========================================================================
    section("K — Deliverable rendering (PDF / DOCX / PPTX bytes on disk)")
    # =========================================================================

    exports = armance_root / ".armance" / "exports"
    # Seed a tiny report to render from.
    seed = ctx._last_output or "# QA seed\n\nShort report for K-section rendering."
    ctx._last_output = seed
    for fmt in ("md", "docx"):
        try:
            r, _ = await dispatch_input(f"/deliverable {fmt} qa_k", ctx)
            target = exports / f"qa_k.{fmt}"
            if target.exists() and target.stat().st_size >= 200:
                ok(f"K1 deliverable.{fmt} written ({target.stat().st_size} bytes)")
            else:
                warn(f"K1 deliverable.{fmt} missing or too small", r[:200])
        except Exception as exc:
            warn(f"K1 deliverable.{fmt} errored", str(exc)[:200])

    # =========================================================================
    section("N — Rich-engine consensus / Serge auto-invoke (signal only)")
    # =========================================================================
    #
    # The rich engine (service.workflow_engine.WorkflowEngine) gates
    # consensus + Serge auto-invoke. The handler path uses the simple engine
    # for now (P1.1). We assert the symbols are reachable so a future wiring
    # can be tested end-to-end here.

    try:
        from armance.service.workflow_engine import WorkflowEngine
        has_consensus = hasattr(WorkflowEngine, "_check_consensus_and_maybe_invoke_serge")
        has_xfamily = hasattr(WorkflowEngine, "_validate_cross_family")
        if has_consensus and has_xfamily:
            ok("N1 WorkflowEngine exposes consensus + cross-family hooks")
        else:
            warn("N1 WorkflowEngine missing consensus / cross-family hooks",
                 f"consensus={has_consensus} xfamily={has_xfamily}")
    except Exception as exc:
        warn("N1 WorkflowEngine import failed", str(exc)[:200])

    # =========================================================================
    section("SUMMARY")
    # =========================================================================

    snap = ledger.snapshot()
    total = snap.get("total", {})
    print(f"\n  Total tokens ↑{total.get('tokens_in',0):,} ↓{total.get('tokens_out',0):,}  cost ${total.get('cost_usd',0):.4f}")
    print(f"\n  {GREEN}PASS:{RESET} {len(_passes)}   {RED}ISSUES:{RESET} {len(_issues)}")

    if _issues:
        print(f"\n{RED}{BOLD}Issues found:{RESET}")
        for i, issue in enumerate(_issues, 1):
            print(f"  {i}. {issue}")
    else:
        print(f"\n{GREEN}{BOLD}All checks passed!{RESET}")


if __name__ == "__main__":
    asyncio.run(run_qa())
