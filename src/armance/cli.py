"""Armance CLI entrypoints: `armance init` and `armance run`."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import questionary

from armance.config import (
    Config,
    ProviderConfig,
    ensure_armance_tree,
    save_config,
    write_env,
)

logger = logging.getLogger(__name__)

ALL_PROVIDERS = ("openrouter", "claude-code", "custom-openai", "gemini")

LANGUAGE_CHOICES = [
    ("English", "en"),
    ("Français", "fr"),
    ("Español", "es"),
    ("Deutsch", "de"),
    ("中文", "zh"),
    ("日本語", "ja"),
]


def _detect_default_language() -> str:
    lang = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()
    for label, code in LANGUAGE_CHOICES:
        if lang.startswith(code) or lang.startswith(code + "_"):
            return label
    return "English"


def _fetch_embedding_models(
    selected_providers: list[str],
    providers: list["ProviderConfig"],
) -> list[tuple[str, str, str]]:
    """Query each provider API for available embedding models.

    Returns list of (display_label, provider_name, model_id).
    Blocking wrapper around async discovery calls.
    """
    from armance.providers.model_discovery import (
        discover_openrouter_embedding_models,
        discover_gemini_embedding_models,
    )

    provider_map = {p.name: p for p in providers}
    results: list[tuple[str, str, str]] = []

    async def _gather() -> None:
        for prov_name in selected_providers:
            prov = provider_map.get(prov_name)
            if prov_name == "claude-code":
                # Anthropic SDK has no embeddings endpoint
                continue
            if prov_name == "custom-openai":
                # Cannot enumerate — user must type model id
                results.append((
                    "[custom-openai]  Saisir manuellement l'identifiant du modèle",
                    "custom-openai",
                    "__ask__",
                ))
                continue
            if prov_name == "openrouter":
                api_key = prov.api_key if prov else None
                models = await discover_openrouter_embedding_models(api_key)
                for m in models:
                    free_tag = "  🆓 gratuit" if m["free"] else ""
                    label = f"[openrouter]  {m['id']}{free_tag}"
                    results.append((label, "openrouter", m["id"]))
            elif prov_name == "gemini":
                api_key = prov.api_key if prov else None
                base_url = prov.base_url if prov else None
                if not api_key:
                    continue
                models = await discover_gemini_embedding_models(api_key, base_url)
                for m in models:
                    label = f"[gemini]  {m['id']}  (gratuit dans les quotas Gemini API)"
                    results.append((label, "gemini", m["id"]))

    asyncio.run(_gather())
    return results


def _ask_embedding(
    selected_providers: list[str],
    providers: list["ProviderConfig"],
) -> tuple[str, str]:
    """Interactive embedding model picker — typeahead autocomplete, fully dynamic.

    Returns (embedding_provider, embedding_model). Returns ("", "") if user skips.
    """
    print()
    print("─" * 60)
    print("  📚  Mémoire documentaire (RAG)")
    print()
    print(
        "  Armance peut indexer vos documents (.armance/docs/) pour les retrouver\n"
        "  intelligemment quand vous posez une question.\n"
        "\n"
        "  Comment ça fonctionne :\n"
        "  Un modèle d'« embedding » transforme chaque passage de vos documents\n"
        "  en une empreinte numérique. Quand vous posez une question, Armance\n"
        "  compare les empreintes pour retrouver les passages les plus pertinents.\n"
        "\n"
        "  → Avec embedding : recherche sémantique précise dans vos docs.\n"
        "  → Sans embedding  : les documents sont listés mais non recherchés.\n"
        "                      (vous pourrez activer cela plus tard dans config.yaml)"
    )
    print()

    print("  Interrogation des APIs pour lister les modèles disponibles…", end="", flush=True)
    models = _fetch_embedding_models(selected_providers, providers)
    print(f" {len(models)} modèle(s) trouvé(s)" if models else " aucun modèle trouvé")
    print()

    # Build choice_meta keyed by model_id (used for autocomplete completion display)
    # Format: "model_id  [provider]  🆓" or "model_id  [provider]"
    choice_meta: dict[str, tuple[str, str]] = {}  # display_label → (provider, model_id)
    skip_label = "aucun"
    completions: list[str] = [skip_label]

    for label, prov, model_id in models:
        if model_id == "__ask__":
            continue  # handled separately below
        # Compact autocomplete label: model_id + provider tag
        free_tag = "  🆓" if "🆓" in label else ""
        display = f"{model_id}  [{prov}]{free_tag}"
        completions.append(display)
        choice_meta[display] = (prov, model_id)

    has_custom = any(model_id == "__ask__" for _, prov, model_id in models)
    has_models = bool(choice_meta)

    if not has_models and not has_custom:
        # No models found on any provider → offer manual entry
        print(
            "  ⚠️  Aucun modèle d'embedding trouvé sur vos providers (vérifiez vos clés API).\n"
            "     Vous pouvez quand même en saisir un manuellement ci-dessous,\n"
            "     ou appuyer sur Entrée pour désactiver le RAG (optionnel).\n"
        )
        # Determine provider for manual entry
        available_prov = next(
            (p for p in selected_providers if p not in ("claude-code",)),
            selected_providers[0] if selected_providers else "openrouter",
        )
        if len([p for p in selected_providers if p not in ("claude-code",)]) > 1:
            available_prov = questionary.select(
                "Provider pour ce modèle d'embedding :",
                choices=[p for p in selected_providers if p != "claude-code"],
                use_indicator=True,
            ).ask() or available_prov

        model_id_manual = (
            questionary.text(
                "Identifiant du modèle d'embedding (laisser vide pour désactiver le RAG) :"
            ).ask()
            or ""
        ).strip()
        if not model_id_manual:
            print("  RAG désactivé. Modifiable via .armance/config.yaml.\n")
            return ("", "")
        print(f"\n  ✅  Embedding : [{available_prov}]  {model_id_manual}\n")
        return (available_prov, model_id_manual)

    # Autocomplete picker — user can type to filter
    print("  💡  Tapez pour filtrer la liste (ex: 'free', 'openai', 'gemini').")
    print(f"      Tapez '{skip_label}' ou laissez vide pour désactiver le RAG.\n")

    chosen = questionary.autocomplete(
        "Modèle d'embedding (typeahead) :",
        choices=completions,
        match_middle=True,
    ).ask()

    chosen = (chosen or "").strip()

    if not chosen or chosen == skip_label:
        print(
            "\n  RAG désactivé. Ajustez embedding_provider / embedding_model\n"
            "     dans .armance/config.yaml pour l'activer plus tard.\n"
        )
        return ("", "")

    # custom-openai manual entry
    if has_custom and chosen not in choice_meta:
        # User typed something not in completions → treat as manual model id
        available_prov = next(
            (p for _, p, mid in models if mid == "__ask__"),
            selected_providers[0],
        )
        print(f"\n  ✅  Embedding : [{available_prov}]  {chosen}\n")
        return (available_prov, chosen)

    if chosen not in choice_meta:
        print(f"  ⚠️  Modèle '{chosen}' non reconnu. RAG désactivé.\n")
        return ("", "")

    prov, model = choice_meta[chosen]
    print(f"\n  ✅  Embedding : [{prov}]  {model}\n")
    return (prov, model)


_DEFAULT_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}


def _cmd_init_noninteractive(
    root: Path,
    *,
    providers: list[str],
    api_keys: dict[str, str],
    base_urls: dict[str, str],
    default_provider: str | None,
    default_model: str | None,
    embedding_provider: str | None,
    embedding_model: str | None,
    budget_effort: str,
    language: str,
) -> int:
    """Zero-interaction init. Validates inputs, writes config.yaml + .env, done.

    Designed so an external cowork agent can install + configure Armance from a
    single prompt without any TTY interaction.
    """
    unknown = [p for p in providers if p not in ALL_PROVIDERS]
    if unknown:
        print(f"error: unknown providers: {unknown}. Allowed: {list(ALL_PROVIDERS)}")
        return 1

    provider_objs: list[ProviderConfig] = []
    for name in providers:
        api_key = api_keys.get(name)
        base_url = base_urls.get(name) or _DEFAULT_BASE_URLS.get(name)
        provider_objs.append(ProviderConfig(name=name, api_key=api_key, base_url=base_url))

    if default_provider is None:
        default_provider = providers[0]
    if default_provider not in providers:
        print(f"error: default_provider '{default_provider}' not in {providers}")
        return 1

    cfg_kwargs: dict = dict(
        providers=provider_objs,
        default_provider=default_provider,
        default_model=default_model or "",
        budget_effort=budget_effort,
        language=language,
        embedding_provider=embedding_provider or "",
        embedding_model=embedding_model or "",
    )
    cfg = Config(**cfg_kwargs)
    ensure_armance_tree(root, cfg)
    save_config(root, cfg)
    write_env(root, provider_objs)

    print(f"✅  Armance initialised at {root / '.armance'}")
    print(f"    providers: {', '.join(providers)}")
    print(f"    default:   {default_provider}/{default_model or '(not set)'}")
    if embedding_provider and embedding_model:
        print(f"    embedding: {embedding_provider}/{embedding_model}")
    else:
        print("    embedding: (disabled — library inactive)")
    print(f"    budget:    {budget_effort}")
    print(f"    language:  {language}")
    print()
    print("    Next: armance run")
    return 0


def cmd_init(
    repo_root: Path | None = None,
    *,
    providers: list[str] | None = None,
    api_keys: dict[str, str] | None = None,
    base_urls: dict[str, str] | None = None,
    default_provider: str | None = None,
    default_model: str | None = None,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    budget_effort: str | None = None,
    language: str | None = None,
    yes: bool = False,
) -> int:
    """Initialise .armance/.

    Interactive when called without args; fully non-interactive when `yes=True`
    AND `providers` is given. The non-interactive path is the CLI oneliner
    target used by external agents (cowork integrations).
    """
    root = repo_root or Path.cwd()

    if yes and providers:
        return _cmd_init_noninteractive(
            root,
            providers=providers,
            api_keys=api_keys or {},
            base_urls=base_urls or {},
            default_provider=default_provider,
            default_model=default_model,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            budget_effort=budget_effort or "free-first",
            language=language or "en",
        )

    selected = questionary.checkbox(
        "Select providers to enable (use SPACE bar to toggle, ENTER to confirm)",
        choices=list(ALL_PROVIDERS),
    ).ask()
    if not selected:
        logger.error("no provider selected; aborting init")
        return 1

    providers: list[ProviderConfig] = []
    for name in selected:
        api_key: str | None = None
        base_url: str | None = None
        if name in ("openrouter", "custom-openai", "gemini"):
            api_key = questionary.password(f"API key for {name}").ask() or None
        if name == "custom-openai":
            base_url = questionary.text(f"Base URL for {name}").ask() or None
        if name == "openrouter":
            base_url = (
                questionary.text(
                    "Base URL for openrouter (default https://openrouter.ai/api/v1)"
                ).ask()
                or "https://openrouter.ai/api/v1"
            )
        if name == "gemini":
            base_url = (
                questionary.text(
                    f"Base URL for {name} (default https://generativelanguage.googleapis.com/v1beta)"
                ).ask()
                or "https://generativelanguage.googleapis.com/v1beta"
            )
        providers.append(ProviderConfig(name=name, api_key=api_key, base_url=base_url))

    default_provider = questionary.select(
        "Default provider",
        choices=[p.name for p in providers],
        use_indicator=True,
        use_arrow_keys=True,
    ).ask()
    default_model = questionary.text("Default model").ask() or ""

    budget_effort = questionary.select(
        "Budget effort — cost constraint for agents (adjustable at runtime via /effort)",
        choices=["free-first", "low", "medium", "high", "adaptive"],
        default="free-first",
        use_indicator=True,
        use_arrow_keys=True,
    ).ask() or "free-first"

    lang_default = _detect_default_language()
    lang_label = questionary.select(
        "Interface language (agents will reply in this language)",
        choices=[label for label, _ in LANGUAGE_CHOICES],
        default=lang_default,
        use_indicator=True,
        use_arrow_keys=True,
    ).ask() or lang_default
    language = next((code for label, code in LANGUAGE_CHOICES if label == lang_label), "en")

    embedding_provider, embedding_model = _ask_embedding(selected, providers)

    cfg_kwargs: dict = dict(
        providers=providers,
        default_provider=default_provider,
        default_model=default_model,
        budget_effort=budget_effort,
        language=language,
    )
    if embedding_provider:
        cfg_kwargs["embedding_provider"] = embedding_provider
        cfg_kwargs["embedding_model"] = embedding_model
    else:
        # Explicit "none" sentinel — disable RAG embeddings
        cfg_kwargs["embedding_provider"] = ""
        cfg_kwargs["embedding_model"] = ""

    cfg = Config(**cfg_kwargs)

    ensure_armance_tree(root, cfg)
    save_config(root, cfg)
    write_env(root, providers)

    armance_readme = root / ".armance" / "README.md"
    print()
    print("─" * 60)
    print(f"✅  Armance initialisé dans {root / '.armance'}")
    print()
    print("  Prochaines étapes :")
    print("    1. Déposez vos documents dans  .armance/docs/")
    print("    2. armance run")
    print()
    if armance_readme.exists():
        print("  📖  Pour ajuster la configuration (modèles, budget, langue…) :")
        print("      lisez  .armance/README.md")
    print("─" * 60)
    print()

    logger.info("armance initialized at %s", root)
    return 0


def cmd_index(repo_root: Path | None = None) -> int:
    from rich.console import Console

    from armance.config import load_config
    from armance.storage.ingestion import sync_docs

    console = Console()
    root = repo_root or Path.cwd()
    armance_root = root / ".armance"
    if not armance_root.exists():
        console.print("[red].armance/ not found — run `armance init` first[/red]")
        return 1

    cfg = load_config(root)
    result = sync_docs(armance_root, config=cfg)
    console.print(
        f"[green]index complete[/green]: "
        f"indexed={result['indexed']} skipped={result['skipped']} deleted={result['deleted']}"
    )
    return 0


def cmd_run(repo_root: Path | None = None) -> int:
    from rich.console import Console

    from armance.config import load_config, ensure_armance_tree
    from armance.service.llm_service import TokenLedger, set_ledger
    from armance.service.session import start_or_resume

    console = Console()
    root = repo_root or Path.cwd()
    armance_root = root / ".armance"
    if not (armance_root / "config.yaml").exists():
        console.print("[red]armance not initialized — run `armance init` first[/red]")
        return 1

    cfg = load_config(root)
    ensure_armance_tree(root, cfg)

    # Initialize NLS with the configured language so all user-facing strings
    # come from the right catalogue (en/fr/es/de/zh/ja).
    from armance.nls import set_language
    set_language(getattr(cfg, "language", "en") or "en")

    # No auto-ingest at boot. Armance scans .armance/docs/ and proposes ingestion
    # to the user via [EXECUTE:/library-index:...]. Silent boot-time ingestion
    # was a footgun: it ran with embedding=none fallback, polluted the manifest,
    # and made Armance hallucinate "✅ retained" on docs never actually embedded.

    # No default workflow installed — user creates them via Kim. A
    # workflow without recruited roles is meaningless, so we don't
    # ship a placeholder.

    # Resume picker: if a prior session exists, ask Y/N before TUI launch.
    # Honours ARMANCE_NO_RESUME=1 for non-interactive callers (CI, agents).
    from armance.service.session import (
        latest_session_id,
        load_state,
        session_summary,
    )
    resume = False
    prior_id = latest_session_id(armance_root)
    if prior_id and not os.environ.get("ARMANCE_NO_RESUME"):
        summary = session_summary(armance_root, prior_id)
        console.print()
        console.print(
            f"[dim]Previous session found:[/dim] [cyan]{prior_id}[/cyan] · "
            f"{summary.get('turns', 0)} turns · "
            f"~{summary.get('est_tokens', 0):,} tokens · "
            f"last update {summary.get('last_update', '?')}"
        )
        try:
            answer = input("Resume? [Y/n] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            answer = "n"
        resume = answer in ("", "y", "yes", "o", "oui")

    if resume:
        state = load_state(armance_root, prior_id)
        console.print(f"[green]resumed session[/green] {state.id}")
    else:
        state = start_or_resume(armance_root, resume=False)
        console.print(f"[green]session[/green] {state.id}")

    from armance.service.session import Session
    session = Session(state, armance_root)
    session.metadata.setdefault("docs_indexed", 0)
    ledger = TokenLedger(persist_path=Path(state.ledger_path)) if state.ledger_path else TokenLedger()
    set_ledger(ledger)

    # Launch the Textual TUI
    try:
        import asyncio
        from armance.client.tui.app import run_textual_tui
        return asyncio.run(run_textual_tui(armance_root, cfg, session, ledger))
    except KeyboardInterrupt:
        console.print("\n[dim]interrupted[/dim]")
        return 0
    except Exception as exc:
        console.print(f"[red]TUI error: {exc}[/red]")
        logger.exception("tui failed")
        return 1


def cmd_workflow_run(
    name: str,
    *,
    armance_root: Path | None = None,
    user_prompt: str = "",
    enrich: str | None = None,
) -> int:
    """Run a workflow by name, optionally enriching with prior session notes."""
    from rich.console import Console

    from armance.service.llm_service import TokenLedger, set_ledger
    from armance.service.session import start_or_resume
    from armance.core.models.workflow import load_workflow, execute_workflow

    console = Console()
    root = armance_root or Path.cwd()
    armance = root / ".armance"

    if not (armance / "config.yaml").exists():
        console.print("[red]armance not initialized — run `armance init` first[/red]")
        return 1

    # Load prior session transcript if --enrich provided
    prior_session_notes: str = ""
    if enrich:
        transcript_path = armance / "sessions" / enrich / "transcript.md"
        if transcript_path.exists():
            prior_session_notes = transcript_path.read_text(encoding="utf-8")
            console.print(f"[dim]enriched from session {enrich}[/dim]")
        else:
            console.print(
                f"[yellow]session {enrich} transcript not found at {transcript_path}[/yellow]"
            )

    # Load workflow
    workflow_path = armance / "workflows" / f"{name}.yaml"
    if not workflow_path.exists():
        console.print(f"[red]workflow not found: {workflow_path}[/red]")
        return 1

    workflow = load_workflow(workflow_path)

    # Always start fresh; history auto-loads from ConversationStore
    state = start_or_resume(armance, resume=False)
    ledger = TokenLedger(persist_path=Path(state.ledger_path)) if state.ledger_path else TokenLedger()
    set_ledger(ledger)

    console.print(f"[green]session[/green] {state.id}")

    # Default user_prompt from env or empty
    prompt = user_prompt or os.environ.get("ARMANCE_PROMPT", "")

    # Define a no-op runner (workflow run is non-interactive)
    async def _noop_runner(step, prompt_text):
        return f"[mock output for {step.id}]"

    # Execute workflow
    try:
        results = asyncio.run(
            execute_workflow(
                workflow,
                user_prompt=prompt,
                runner=_noop_runner,
                prior_session_notes=prior_session_notes,
                armance_root=armance,
            )
        )
        for sid, result in results.items():
            console.print(f"  [green]{sid}[/green]: {result.output[:200]}")
        return 0
    except Exception as exc:
        console.print(f"[red]workflow error: {exc}[/red]")
        logger.exception("workflow failed")
        return 1


def _build_workflow_parser(subparsers):
    """Build the ``workflow`` subparser with ``run`` sub-subcommand."""
    parser_workflow = subparsers.add_parser("workflow", help="Workflow management")
    sub = parser_workflow.add_subparsers(dest="workflow_cmd")

    run_p = sub.add_parser("run", help="Run a workflow by name")
    run_p.add_argument("name", help="Workflow name (without .yaml extension)")
    run_p.add_argument(
        "-p", "--prompt",
        dest="user_prompt",
        default="",
        help="User prompt to pass to the workflow",
    )
    run_p.add_argument(
        "--enrich",
        default=None,
        help="Session ID to enrich with prior conversation transcript "
             "(loads .armance/sessions/<id>/transcript.md, "
             "available as {{prior_session.notes}})",
    )
    run_p.add_argument(
        "-r", "--root",
        dest="armance_root",
        type=Path,
        default=None,
        help="Path to .armance root (default: current directory)",
    )
    return parser_workflow


def cmd_doctor(repo_root: Path | None = None) -> int:
    """Health check: config, providers, sqlite-vec, deliverable libs, ledger."""
    from rich.console import Console
    from rich.table import Table

    from armance.config import load_config

    console = Console()
    root = repo_root or Path.cwd()
    armance_root = root / ".armance"
    ok = True

    table = Table(title="armance doctor", show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    def _row(label: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        if not passed:
            ok = False
        status = "[green]OK[/green]" if passed else "[red]FAIL[/red]"
        table.add_row(label, status, detail)

    # config
    cfg_path = armance_root / "config.yaml"
    if cfg_path.exists():
        try:
            cfg = load_config(root)
            _row("config.yaml", True, f"{len(cfg.providers)} provider(s)")
        except Exception as exc:
            _row("config.yaml", False, str(exc))
            cfg = None
    else:
        _row("config.yaml", False, "not found — run `armance init`")
        cfg = None

    # rag writable
    rag_dir = armance_root / "rag"
    try:
        rag_dir.mkdir(parents=True, exist_ok=True)
        probe = rag_dir / ".probe"
        probe.write_text("ok")
        probe.unlink()
        _row("rag dir writable", True, str(rag_dir))
    except Exception as exc:
        _row("rag dir writable", False, str(exc))

    # deliverable libs
    for lib in ("docx", "pptx", "weasyprint"):
        try:
            __import__(lib)
            _row(f"lib:{lib}", True)
        except ImportError:
            _row(f"lib:{lib}", False, f"`pip install python-{lib}` or `uv add python-{lib}`")

    # ledger writable
    sessions_dir = armance_root / "sessions"
    try:
        sessions_dir.mkdir(parents=True, exist_ok=True)
        _row("sessions dir writable", True, str(sessions_dir))
    except Exception as exc:
        _row("sessions dir writable", False, str(exc))

    # provider reachability (network-gated, best-effort)
    if cfg:
        import httpx
        for prov in cfg.providers:
            if prov.base_url:
                try:
                    r = httpx.head(prov.base_url, timeout=3)
                    _row(f"provider:{prov.name}", True, f"HTTP {r.status_code}")
                except Exception as exc:
                    _row(f"provider:{prov.name}", False, str(exc)[:80])

    console.print(table)
    if ok:
        console.print("[green]all checks passed[/green]")
    else:
        console.print("[red]some checks failed — see details above[/red]")
    return 0 if ok else 1


def cmd_web(repo_root: Path | None = None, remaining: list[str] | None = None) -> int:
    """Start the Armance web UI (FastAPI backend + optional browser open)."""
    import argparse
    import subprocess

    web_parser = argparse.ArgumentParser(prog="armance web", add_help=False)
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8000)
    web_parser.add_argument("--no-browser", action="store_true")
    web_args, _ = web_parser.parse_known_args(remaining or [])

    _missing = [m for m in ("fastapi", "uvicorn", "sse_starlette") if __import__("importlib").util.find_spec(m) is None]
    if _missing:
        print(
            f"Web dependencies missing: {', '.join(_missing)}\n\n"
            "Install with:\n"
            "  uv tool install --reinstall 'git+https://github.com/armance-io/armance.git[web]'\n"
            "or if installed via pipx:\n"
            "  pipx inject armance fastapi 'uvicorn[standard]' sse-starlette python-multipart",
            file=sys.stderr,
        )
        return 1

    root = repo_root or Path.cwd()

    if not web_args.no_browser:
        import threading
        import webbrowser
        import time

        def _open() -> None:
            time.sleep(1.5)
            webbrowser.open(f"http://{web_args.host}:{web_args.port}")

        threading.Thread(target=_open, daemon=True).start()

    import os
    env = {**os.environ, "ARMANCE_ROOT": str(root)}
    try:
        subprocess.run(
            [
                sys.executable, "-m", "uvicorn",
                "armance_web.main:app",
                "--host", web_args.host,
                "--port", str(web_args.port),
                "--reload",
            ],
            env=env,
            check=True,
        )
    except KeyboardInterrupt:
        pass
    except subprocess.CalledProcessError as e:
        print(f"web server exited with code {e.returncode}", file=sys.stderr)
        return e.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    import importlib.metadata

    argv = argv if argv is not None else sys.argv[1:]

    # --version flag (before subcommand parsing)
    if argv and argv[0] in ("--version", "-V"):
        try:
            version = importlib.metadata.version("armance")
        except importlib.metadata.PackageNotFoundError:
            version = "0.0.0-dev"
        print(f"armance {version}")
        return 0

    if not argv or argv[0] in ("-h", "--help", "help"):
        print("usage: armance {init,run,index,doctor,workflow,web} [--version]", file=sys.stderr)
        return 0 if argv else 1

    parser = argparse.ArgumentParser(prog="armance", add_help=False)
    parser.add_argument("command")
    parser.add_argument(
        "--root",
        dest="armance_root",
        type=Path,
        default=None,
        help="Path to project root (default: current directory)",
    )

    args, remaining = parser.parse_known_args(argv)
    root = args.armance_root

    cmd = args.command
    if cmd == "init":
        # Non-interactive flags (oneliner mode). When --yes is set with
        # --provider, init runs without any TTY prompt — designed for
        # external cowork agents.
        init_parser = argparse.ArgumentParser(prog="armance init", add_help=True)
        init_parser.add_argument("-y", "--yes", action="store_true",
                                 help="non-interactive; requires --provider")
        init_parser.add_argument("--provider", action="append", default=[],
                                 help="enable provider (repeatable)")
        init_parser.add_argument("--api-key", action="append", default=[],
                                 metavar="provider=KEY",
                                 help="API key per provider, repeatable")
        init_parser.add_argument("--base-url", action="append", default=[],
                                 metavar="provider=URL",
                                 help="custom base URL per provider, repeatable")
        init_parser.add_argument("--default-provider", default=None)
        init_parser.add_argument("--default-model", default=None)
        init_parser.add_argument("--embedding-provider", default=None)
        init_parser.add_argument("--embedding-model", default=None)
        init_parser.add_argument("--budget", default=None,
                                 choices=["free-first", "low", "medium", "high", "adaptive"])
        init_parser.add_argument("--language", default=None,
                                 choices=["en", "fr", "es", "de", "zh", "ja"])
        init_args = init_parser.parse_args(remaining)

        def _kv(items: list[str]) -> dict[str, str]:
            out: dict[str, str] = {}
            for it in items:
                if "=" not in it:
                    print(f"error: '{it}' must be provider=value", file=sys.stderr)
                    sys.exit(1)
                k, v = it.split("=", 1)
                out[k.strip()] = v.strip()
            return out

        return cmd_init(
            root,
            providers=init_args.provider or None,
            api_keys=_kv(init_args.api_key),
            base_urls=_kv(init_args.base_url),
            default_provider=init_args.default_provider,
            default_model=init_args.default_model,
            embedding_provider=init_args.embedding_provider,
            embedding_model=init_args.embedding_model,
            budget_effort=init_args.budget,
            language=init_args.language,
            yes=init_args.yes,
        )
    if cmd == "run":
        return cmd_run(root)
    if cmd == "index":
        return cmd_index(root)
    if cmd == "doctor":
        return cmd_doctor(root)
    if cmd == "web":
        return cmd_web(root, remaining)
    if cmd == "workflow":
        if not remaining or remaining[0] == "run":
            wf_parser = argparse.ArgumentParser(add_help=False)
            wf_parser.add_argument("workflow_cmd", nargs="?", default="run")
            wf_parser.add_argument("name", nargs="?", default=None)
            wf_parser.add_argument("-p", "--prompt", dest="user_prompt", default="")
            wf_parser.add_argument("--enrich", default=None)
            wf_parser.add_argument("-r", "--root", dest="armance_root", type=Path, default=None)
            wf_args, _ = wf_parser.parse_known_args(remaining)
            if wf_args.workflow_cmd == "run":
                if wf_args.name is None:
                    print("usage: armance workflow run <name> [--enrich <session_id>]", file=sys.stderr)
                    return 2
                return cmd_workflow_run(
                    wf_args.name,
                    armance_root=wf_args.armance_root or root,
                    user_prompt=wf_args.user_prompt,
                    enrich=wf_args.enrich,
                )
        print(f"unknown workflow command: {remaining[0] if remaining else 'none'}", file=sys.stderr)
        return 2
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2
