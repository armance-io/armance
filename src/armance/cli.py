"""Armance CLI entrypoints: `armance init` and `armance run`."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

import questionary

from armance.config import (
    Config,
    FootprintConfig,
    ProviderConfig,
    ensure_armance_tree,
    ensure_global_setup,
    save_config,
    write_env,
)

logger = logging.getLogger(__name__)

ALL_PROVIDERS = ("openrouter", "claude-code", "custom-openai", "gemini")


# Styling for single-choice select prompts. The default questionary style
# leaves `highlighted` and `pointer` empty, which collapses to a static
# pointer glyph and zero visual feedback when arrows move — users couldn't
# tell which row the cursor was on. Make the active row obvious.
_SELECT_STYLE = questionary.Style([
    ("pointer", "fg:#FFA500 bold"),
    ("highlighted", "fg:#FFA500 bold"),
    ("selected", "fg:#FFA500 bold"),
])

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
    language: str = "en",
) -> tuple[str, str]:
    """Interactive embedding model picker — typeahead autocomplete, fully dynamic.

    Returns (embedding_provider, embedding_model). Returns ("", "") if user skips.
    All user-facing strings come from `nls.init.rag.*`, keyed by `language`.
    """
    from armance.nls import t

    def _tr(key: str, **kw: Any) -> str:
        return t(f"init.rag.{key}", lang=language, **kw)

    print()
    print("─" * 60)
    print("  📚  " + _tr("title"))
    print()
    print(_tr("intro"))
    print()

    print("  " + _tr("querying"), end="", flush=True)
    models = _fetch_embedding_models(selected_providers, providers)
    real_models = [(lbl, p, mid) for lbl, p, mid in models if mid != "__ask__"]
    has_custom = any(mid == "__ask__" for _, _, mid in models)
    count = len(real_models)
    print(" " + (_tr("found", count=count) if count else _tr("none_found")))
    print()

    choice_meta: dict[str, tuple[str, str]] = {}
    skip_label = _tr("skip_label")
    completions: list[str] = [skip_label]
    for label, prov, model_id in real_models:
        free_tag = "  🆓" if "🆓" in label else ""
        display = f"{model_id}  [{prov}]{free_tag}"
        completions.append(display)
        choice_meta[display] = (prov, model_id)

    custom_sentinel = _tr("custom_sentinel")
    if has_custom:
        completions.append(custom_sentinel)

    # custom-openai-only path
    if not real_models and has_custom:
        print(_tr("custom_only_hint"))
        model_id_manual = (questionary.text(_tr("prompt_manual_id")).ask() or "").strip()
        if not model_id_manual:
            print("  " + _tr("disabled_edit_yaml") + "\n")
            return ("", "")
        print("\n  ✅  " + _tr("confirmed", provider="custom-openai", model=model_id_manual) + "\n")
        return ("custom-openai", model_id_manual)

    # no enumerable models at all
    if not real_models and not has_custom:
        print(_tr("no_models_hint"))
        non_claude = [p for p in selected_providers if p != "claude-code"]
        available_prov = non_claude[0] if non_claude else (
            selected_providers[0] if selected_providers else "openrouter"
        )
        if len(non_claude) > 1:
            available_prov = questionary.select(
                _tr("prompt_provider"),
                choices=non_claude,
                style=_SELECT_STYLE,
            ).ask() or available_prov
        model_id_manual = (questionary.text(_tr("prompt_manual_id")).ask() or "").strip()
        if not model_id_manual:
            print("  " + _tr("disabled_edit_yaml") + "\n")
            return ("", "")
        print("\n  ✅  " + _tr("confirmed", provider=available_prov, model=model_id_manual) + "\n")
        return (available_prov, model_id_manual)

    # autocomplete picker
    print("  💡  " + _tr("filter_hint"))
    print()
    chosen = questionary.autocomplete(
        _tr("prompt_autocomplete"),
        choices=completions,
        match_middle=True,
    ).ask()
    chosen = (chosen or "").strip()

    if not chosen or chosen == skip_label:
        print("\n  " + _tr("disabled_edit_keys") + "\n")
        return ("", "")

    if chosen == custom_sentinel or (has_custom and chosen not in choice_meta):
        prefill = chosen if chosen != custom_sentinel else ""
        model_id_manual = (
            questionary.text(_tr("prompt_manual_id_custom"), default=prefill).ask() or ""
        ).strip()
        if not model_id_manual:
            print("  " + _tr("disabled_short") + "\n")
            return ("", "")
        print("\n  ✅  " + _tr("confirmed", provider="custom-openai", model=model_id_manual) + "\n")
        return ("custom-openai", model_id_manual)

    if chosen not in choice_meta:
        print("  ⚠️  " + _tr("unrecognised", name=chosen) + "\n")
        return ("", "")

    prov, model = choice_meta[chosen]
    print("\n  ✅  " + _tr("confirmed", provider=prov, model=model) + "\n")
    return (prov, model)


def _fetch_chat_models(
    provider_name: str,
    providers: list["ProviderConfig"],
) -> list[tuple[str, str]]:
    """Return list of (model_id, tier) for chat/LLM models of a single provider.

    Uses the provider class directly — cfg isn't built yet at init time.
    Empty list when provider can't enumerate (e.g. custom-openai).
    """
    from armance.providers.discovery import _provider_for  # type: ignore
    from armance.config import Config as _Cfg

    # Build a stub cfg shim with .providers so _provider_for picks up the api_key.
    cfg = _Cfg(providers=providers)
    prov = _provider_for(provider_name, cfg)
    if prov is None:
        return []
    try:
        models = asyncio.run(prov.list_models())
    except Exception:
        logger.exception("init: list_models failed for %s", provider_name)
        return []
    return [(m.id, m.tier) for m in models]


_TIER_GEM = {"free": "🟢", "low": "🟡", "medium": "🟠", "high": "🔴"}


def _ask_default_model(
    default_provider: str | None,
    providers: list["ProviderConfig"],
) -> str:
    """Pick the default model via typeahead autocomplete.

    Lists models from the chosen provider's catalogue as `provider / model_id`,
    matching the embedding picker UX. Falls back to free-text when the provider
    can't enumerate (custom-openai) or discovery returns nothing.
    """
    if not default_provider:
        return (questionary.text("Default model").ask() or "").strip()
    models = _fetch_chat_models(default_provider, providers)
    if not models:
        return (
            questionary.text(f"Default model for {default_provider}").ask() or ""
        ).strip()
    completions: list[str] = []
    meta: dict[str, str] = {}
    for mid, tier in models:
        gem = _TIER_GEM.get(tier, "")
        display = f"{default_provider} / {mid}  {gem}".rstrip()
        completions.append(display)
        meta[display] = mid
    chosen = questionary.autocomplete(
        "Default model (type to filter, Enter to confirm)",
        choices=completions,
        match_middle=True,
    ).ask()
    chosen = (chosen or "").strip()
    if not chosen:
        return ""
    if chosen in meta:
        return meta[chosen]
    # User typed something not in the list — accept as raw id.
    return chosen


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
    ensure_global_setup(cfg)
    save_config(cfg)
    write_env(provider_objs)
    ensure_armance_tree(root, cfg)

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

    # Ask language FIRST so subsequent prompts (and the RAG wizard) can be
    # localised. The active NLS language is also flipped via set_language so
    # any t() call inside the wizard picks it up automatically.
    lang_default = _detect_default_language()
    lang_label = questionary.select(
        "Interface language (agents will reply in this language)",
        choices=[label for label, _ in LANGUAGE_CHOICES],
        default=lang_default,
        use_arrow_keys=True,
        style=_SELECT_STYLE,
    ).ask() or lang_default
    language = next((code for label, code in LANGUAGE_CHOICES if label == lang_label), "en")
    from armance.nls import set_language as _set_lang
    _set_lang(language)

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
        ssl_verify: bool = True
        if name == "custom-openai":
            base_url = questionary.text(f"Base URL for {name}").ask() or None
            from armance.nls import t as _t_nls
            ssl_verify = not questionary.confirm(
                _t_nls("init.ssl_skip_prompt", lang=language),
                default=False,
            ).ask()
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
        providers.append(ProviderConfig(name=name, api_key=api_key, base_url=base_url, ssl_verify=ssl_verify))

    default_provider = questionary.select(
        "Default provider",
        choices=[p.name for p in providers],
        use_arrow_keys=True,
        style=_SELECT_STYLE,
    ).ask()
    default_model = _ask_default_model(default_provider, providers)

    budget_effort = questionary.select(
        "Budget effort — cost constraint for agents (adjustable at runtime via /effort)",
        choices=["free-first", "low", "medium", "high", "adaptive", "optimised"],
        default="free-first",
        use_arrow_keys=True,
        style=_SELECT_STYLE,
    ).ask() or "free-first"

    embedding_provider, embedding_model = _ask_embedding(selected, providers, language=language)

    # Carbon-intensity zone — refines the CO2 footprint estimate to the user's
    # electricity grid. Defaults to the world average (WOR).
    from armance.service.footprint_zones import list_zones
    zones = list_zones()
    zone_labels = [f"{z['code']} · {z['gco2e_per_kwh']} gCO2e/kWh" for z in zones]
    zone_label = questionary.select(
        "Country / zone for the CO2 footprint estimate (world average by default)",
        choices=zone_labels,
        default=zone_labels[0],
        use_arrow_keys=True,
        style=_SELECT_STYLE,
    ).ask() or zone_labels[0]
    # Resolve back to the zone code; tolerate a label we don't recognise
    # (mismatched mock / future format) by falling back to the world average.
    try:
        electricity_mix_zone = str(zones[zone_labels.index(zone_label)]["code"])
    except ValueError:
        electricity_mix_zone = "WOR"

    cfg_kwargs: dict = dict(
        providers=providers,
        default_provider=default_provider,
        default_model=default_model,
        budget_effort=budget_effort,
        language=language,
        footprint=FootprintConfig(electricity_mix_zone=electricity_mix_zone),
    )
    if embedding_provider:
        cfg_kwargs["embedding_provider"] = embedding_provider
        cfg_kwargs["embedding_model"] = embedding_model
    else:
        # Explicit "none" sentinel — disable RAG embeddings
        cfg_kwargs["embedding_provider"] = ""
        cfg_kwargs["embedding_model"] = ""

    cfg = Config(**cfg_kwargs)

    ensure_global_setup(cfg)
    save_config(cfg)
    write_env(providers)
    ensure_armance_tree(root, cfg)

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

    cfg = load_config()
    result = sync_docs(armance_root, config=cfg)
    console.print(
        f"[green]index complete[/green]: "
        f"indexed={result['indexed']} skipped={result['skipped']} deleted={result['deleted']}"
    )
    return 0


def _pick_older_session(armance_root: Path, console):
    # -> SessionState | None  (annotation deferred to avoid an eager import
    # at module load — cli.py is the entry path and we want it light.)
    """Show every persisted session, newest first, and let the user pick one.

    Returns the loaded SessionState, or None if the user aborts. Items are
    sorted by `updated_at` desc, so the first row is always the most recent
    even after Y/N/O loops.
    """
    from armance.service.session import list_sessions, load_state
    sessions = list_sessions(armance_root)
    if not sessions:
        console.print("[dim]No older sessions on disk.[/dim]")
        return None
    console.print()
    console.print("[bold]Available sessions[/bold] (newest first):")
    for i, s in enumerate(sessions, start=1):
        parent = f" ← {s['parent_id']}" if s.get("parent_id") else ""
        console.print(
            f"  [cyan]{i:2}[/cyan]  {s['id']}  "
            f"[dim]{s['updated_at']}[/dim]  · {s['turns']} turns"
            f" · ~{s['est_tokens']:,} tokens{parent}"
        )
    try:
        raw = input("Pick a session (number or id, blank to cancel): ").strip()
    except (KeyboardInterrupt, EOFError):
        return None
    if not raw:
        return None
    picked_id: str | None = None
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(sessions):
            picked_id = sessions[idx]["id"]
    else:
        for s in sessions:
            if s["id"].startswith(raw):
                picked_id = s["id"]
                break
    if picked_id is None:
        console.print(f"[red]no match for {raw!r}[/red]")
        return None
    state = load_state(armance_root, picked_id)
    console.print(f"[green]loaded session[/green] {state.id}")
    return state


def cmd_run(
    repo_root: Path | None = None,
    *,
    session_id: str | None = None,
) -> int:
    from rich.console import Console

    from armance.config import load_config, ensure_armance_tree
    from armance.service.llm_service import (
        TokenLedger,
        set_current_session_id,
        set_ledger,
    )
    from armance.service.session import start_or_resume

    console = Console()
    root = repo_root or Path.cwd()
    armance_root = root / ".armance"
    from armance import paths
    if not paths.global_config_path().exists():
        console.print("[red]armance not initialized — run `armance init` first[/red]")
        return 1

    cfg = load_config()
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

    from armance.service.session import (
        latest_session_id,
        load_state,
        session_summary,
    )

    # --session <id>: skip the picker entirely.
    if session_id:
        try:
            state = load_state(armance_root, session_id)
        except Exception:
            console.print(f"[red]session {session_id!r} not found[/red]")
            return 1
        console.print(f"[green]loaded session[/green] {state.id}")
    elif os.environ.get("ARMANCE_NO_RESUME"):
        state = start_or_resume(armance_root, resume=False)
        console.print(f"[green]session[/green] {state.id}")
    else:
        prior_id = latest_session_id(armance_root)
        if not prior_id:
            state = start_or_resume(armance_root, resume=False)
            console.print(f"[green]session[/green] {state.id}")
        else:
            summary = session_summary(armance_root, prior_id)
            console.print()
            console.print(
                f"[dim]Previous session:[/dim] [cyan]{prior_id}[/cyan] · "
                f"{summary.get('turns', 0)} turns · "
                f"~{summary.get('est_tokens', 0):,} tokens · "
                f"last update {summary.get('last_update', '?')}"
            )
            try:
                answer = input("Resume previous? [Y]es / [n]ew / [o]lder: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                answer = "n"
            # Resume = default (empty Enter), Y, yes, oui. 'o' / 'older' jumps
            # to the older-session picker — kept distinct from 'oui' on purpose.
            if answer in ("", "y", "yes", "oui"):
                state = load_state(armance_root, prior_id)
                console.print(f"[green]resumed session[/green] {state.id}")
            elif answer in ("o", "older", "a", "ancien"):
                state = _pick_older_session(armance_root, console)
                if state is None:
                    return 0
            else:
                state = start_or_resume(armance_root, resume=False)
                console.print(f"[green]new session[/green] {state.id}")

    set_current_session_id(state.id)

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

    from armance import paths
    if not paths.global_config_path().exists():
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

    # config (global — clean break)
    from armance import paths
    cfg_path = paths.global_config_path()
    if cfg_path.exists():
        try:
            cfg = load_config()
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

    # deliverable libs (docx/pptx ship by default)
    for lib in ("docx", "pptx"):
        try:
            __import__(lib)
            _row(f"lib:{lib}", True)
        except ImportError:
            _row(f"lib:{lib}", False, f"`pip install python-{lib}` or `uv add python-{lib}`")
    # weasyprint is optional (PDF export); import lazily so a missing native
    # lib never prints its banner during the doctor check.
    try:
        __import__("weasyprint")
        _row("lib:weasyprint (pdf)", True)
    except Exception:
        _row("lib:weasyprint (pdf)", False, "optional — `pip install 'armance[pdf]'`")

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


def _build_web_bundle() -> int:
    """Build the Next.js static export and copy it into armance/web_dist.

    Repo/dev only: needs Node + pnpm and the web/frontend sources. The
    resulting bundle is what `armance web` serves same-origin.
    """
    import os
    import shutil
    import subprocess

    repo_root = Path(__file__).resolve().parents[2]
    frontend = repo_root / "web" / "frontend"
    if not (frontend / "package.json").exists():
        print(
            "Cannot build the UI: frontend sources (web/frontend) are not "
            "present in this install.\n\n"
            "  --build only works from a repo checkout, not from "
            "`uv tool install`/`pipx`/`pip install` (those ship code, not the\n"
            "  frontend toolchain). To get the UI either:\n"
            "    • install a release wheel — the UI is already bundled:\n"
            "        pip install armance\n"
            "    • or build from a clone:\n"
            "        git clone https://github.com/armance-io/armance.git\n"
            "        cd armance && uv sync\n"
            "        uv run armance web --build",
            file=sys.stderr,
        )
        return 1
    env = {**os.environ, "ARMANCE_STATIC_EXPORT": "1"}
    for cmd in (["pnpm", "install", "--frozen-lockfile"], ["pnpm", "build"]):
        try:
            subprocess.run(cmd, cwd=str(frontend), env=env, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"UI build failed ({' '.join(cmd)}): {e}", file=sys.stderr)
            return 1
    out = frontend / "out"
    dest = repo_root / "src" / "armance" / "web_dist"
    if not (out / "index.html").exists():
        print("UI build produced no out/index.html.", file=sys.stderr)
        return 1
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(out, dest)
    print(f"UI bundle built → {dest}")
    return 0


def cmd_web(
    repo_root: Path | None = None,
    remaining: list[str] | None = None,
    *,
    data_dir: Path | None = None,
) -> int:
    """Start the Armance web UI (FastAPI backend + optional browser open)."""
    import argparse
    import subprocess

    web_parser = argparse.ArgumentParser(prog="armance web", add_help=False)
    web_parser.add_argument("--bind", default="127.0.0.1",
                            help="Network interface to bind (default: 127.0.0.1)")
    # Legacy --host alias kept for compatibility
    web_parser.add_argument("--host", default=None,
                            help="Alias for --bind (deprecated, use --bind)")
    web_parser.add_argument("--port", type=int, default=8000)
    web_parser.add_argument("--no-browser", action="store_true")
    web_parser.add_argument(
        "--foreground", action="store_true",
        help="Run in the foreground (blocks; Ctrl+C stops; logs stream to the "
             "terminal). Default runs in the background, logging to "
             ".armance/logs/web-server.log and returning 0.",
    )
    web_parser.add_argument(
        "--build", action="store_true",
        help="Rebuild the static UI bundle (needs Node + pnpm; dev/repo only).",
    )
    web_parser.add_argument(
        "--stop", action="store_true",
        help="Stop the web server running in this folder, then exit.",
    )
    web_args, _ = web_parser.parse_known_args(remaining or [])

    root = repo_root or Path.cwd()
    # The server's runtime files (pidfile, logs) live in `data_dir`. Normally
    # that is the project's <folder>/.armance; the launcher passes the global
    # config dir directly so it does not nest a redundant .armance there.
    data_dir = data_dir if data_dir is not None else root / ".armance"

    # `armance web stop` (positional) is an alias for `armance web --stop`.
    if web_args.stop or "stop" in (remaining or []):
        from armance.web.server_lock import stop_server
        stopped, message = stop_server(data_dir)
        print(message, file=sys.stderr if not stopped else sys.stdout)
        return 0 if stopped else 1

    # One instance per folder: refuse to launch over a live server.
    from armance.web.server_lock import read_lock, write_lock, clear_lock
    existing = read_lock(data_dir)
    if existing is not None:
        print(
            f"Armance web is already running in this folder "
            f"(pid {existing.pid}, port {existing.port}).\n"
            f"  stop it: armance web --stop",
            file=sys.stderr,
        )
        return 1

    if web_args.build:
        rc = _build_web_bundle()
        if rc != 0:
            return rc

    # --host is a legacy alias for --bind
    bind = web_args.host or web_args.bind

    # Port discovery / port hunting: if specified port is in use, try the next ones.
    port = web_args.port
    import socket
    while port < web_args.port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((bind, port))
                break
            except socket.error:
                port += 1
    else:
        print(f"error: could not find an available port starting from {web_args.port}", file=sys.stderr)
        return 1

    if port != web_args.port:
        print(f"⚠  Port {web_args.port} is occupied. Discovered available port: {port}", file=sys.stderr)

    _missing = [m for m in ("fastapi", "uvicorn", "sse_starlette") if __import__("importlib").util.find_spec(m) is None]
    if _missing:
        print(
            f"Web dependencies missing: {', '.join(_missing)}\n\n"
            "Please reinstall armance:\n"
            "  pip install armance\n"
            "or:\n"
            "  uv tool install --reinstall armance",
            file=sys.stderr,
        )
        return 1

    if bind == "0.0.0.0":
        print(
            "⚠  LAN exposure: anyone on this network can read this session. "
            "Driver-only writes.",
            file=sys.stderr,
        )

    url = f"http://127.0.0.1:{port}/"
    open_browser = not web_args.no_browser

    # Epic S · security gate. Resolve the web secret in the parent so the
    # printed URL and the child server agree, then hand it to the child via
    # ARMANCE_WEB_PASSWORD (so the child does not generate its own token).
    from armance.config import load_config as _load_cfg
    from armance.service import security as _security
    try:
        _web_cfg = _load_cfg()
    except Exception:  # noqa: BLE001 — config may be absent; fall back to a token
        from armance.config import Config as _Cfg2
        _web_cfg = _Cfg2()
    _web_secret = _security.resolve_web_secret(_web_cfg)
    _web_secret_auto = _security.was_auto_generated(_web_cfg)
    # The auto-generated token is safe to put in the URL (ephemeral, local).
    # A persistent password must never travel in the query string.
    if _web_secret_auto:
        url = f"http://127.0.0.1:{port}/?token={_web_secret}"

    # Foreground mode blocks in subprocess.run below, so the browser must be
    # opened from a background thread that waits for readiness first. Background
    # mode opens it inline after the readiness wait (see below), since the
    # main thread is free there.
    if open_browser and web_args.foreground:
        import threading
        import time
        import urllib.error
        import urllib.request
        import webbrowser

        # Probe the API health endpoint, not `/`: the SPA shell is only served
        # for `Accept: text/html`, but urllib sends `*/*`, so `/` would 404
        # even when the server is up. /api/healthz always answers 200 once ready.
        ready_url = f"http://127.0.0.1:{port}/api/healthz"

        def _open_when_ready() -> None:
            deadline = time.time() + 15.0
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(ready_url, timeout=1) as resp:
                        if resp.status == 200:
                            webbrowser.open(url)
                            return
                except (urllib.error.URLError, OSError):
                    pass
                time.sleep(0.2)
            print(
                f"web server did not become ready within 15s — open {url} manually.",
                file=sys.stderr,
            )

        threading.Thread(target=_open_when_ready, daemon=True).start()

    import os

    # The backend ships inside the armance package; serve it directly. The
    # bundled frontend (armance/web_dist) is served same-origin by the app,
    # so this single process is the whole UI + API.
    from armance.web.backend import main as _web_main  # noqa: F401

    if _web_main._resolve_static_dir() is None:
        print(
            f"Note: no bundled UI found — running API only on http://{bind}:{port}.\n"
            "  The UI ships in the 0.2 release. A plain `pip install armance`\n"
            "  may still resolve to an older release without the UI. To get it:\n"
            "    • pip install --upgrade --pre armance   (while 0.2 is a beta)\n"
            "    • from a repo clone: `uv run armance web --build` (needs Node + pnpm).",
            file=sys.stderr,
        )

    env = {**os.environ, "ARMANCE_ROOT": str(root),
           "ARMANCE_DATA_DIR": str(data_dir),
           "ARMANCE_WEB_PASSWORD": _web_secret}
    cmd = [
        sys.executable, "-m", "uvicorn",
        "armance.web.backend.main:app",
        "--host", bind,
        "--port", str(port),
    ]

    # Foreground mode keeps the old blocking behaviour (Ctrl+C stops it,
    # logs stream to the terminal). Useful for dev / debugging. We still write
    # the pidfile so the single-instance lock holds, and clear it on exit.
    if web_args.foreground:
        if _web_secret_auto:
            print(
                f"[SECURITY] Web interface access token: {_web_secret}\n"
                f"[SECURITY] Access the UI via: {url}",
            )
        else:
            print("[SECURITY] Web interface protected by your configured password.")
        proc = None
        try:
            proc = subprocess.Popen(cmd, env=env, start_new_session=True)
            write_lock(data_dir, proc.pid, port)
            rc = proc.wait()
        except KeyboardInterrupt:
            if proc is not None:
                proc.terminate()
            rc = 0
        finally:
            clear_lock(data_dir)
        if rc not in (0, None):
            print(f"web server exited with code {rc}", file=sys.stderr)
            return rc
        return 0

    # Default: run the server in the background and return 0. Logs go to
    # .armance/logs/web-server.log instead of the terminal, so the shell is
    # freed and the window stays clean.
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "web-server.log"
    log_file = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 — handed to the child
    try:
        proc = subprocess.Popen(
            cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except Exception as exc:  # noqa: BLE001
        log_file.close()
        print(f"error: failed to start web server: {exc}", file=sys.stderr)
        return 1

    # Wait for readiness so a 0 exit means "the server is actually up".
    import time
    import urllib.error
    import urllib.request

    ready_url = f"http://127.0.0.1:{port}/api/healthz"
    deadline = time.time() + 20.0
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            log_file.close()
            print(
                f"web server exited early (code {proc.returncode}); see {log_path}",
                file=sys.stderr,
            )
            return proc.returncode or 1
        try:
            with urllib.request.urlopen(ready_url, timeout=1) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.2)

    if not ready:
        print(f"web server did not become ready within 20s; see {log_path}", file=sys.stderr)
        return 1

    # Server is up: record the single-instance lock for this folder.
    write_lock(data_dir, proc.pid, port)

    if open_browser:
        import webbrowser
        webbrowser.open(url)

    if _web_secret_auto:
        print(
            f"[SECURITY] Web interface access token: {_web_secret}\n"
            f"[SECURITY] Access the UI via: {url}",
        )
    else:
        print("[SECURITY] Web interface protected by your configured password.")

    print(
        f"✓ Armance web running at http://{bind}:{port}  (pid {proc.pid})\n"
        f"  logs: {log_path}\n"
        f"  stop: armance web --stop",
    )
    return 0


def cmd_install_shortcut() -> int:
    """Create a desktop icon that launches Armance. Best-effort."""
    from armance.service.shortcuts import install_shortcut

    result = install_shortcut()
    print(("✓ " if result.ok else "⚠ ") + result.message)
    return 0 if result.ok else 1


def _open_launcher_browser(path: str, port: int = 8000) -> None:
    """Open the browser on the launcher/setup page once the server is ready.

    Polls the liveness endpoint in a background thread, then opens
    ``http://127.0.0.1:<port><path>``. Best-effort — never blocks the caller.
    """
    import threading
    import urllib.error
    import urllib.request
    import webbrowser

    url = f"http://127.0.0.1:{port}{path}"

    def _wait_and_open() -> None:
        import time

        for _ in range(100):  # ~10s
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5)
                break
            except (urllib.error.URLError, OSError):
                time.sleep(0.1)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_wait_and_open, daemon=True).start()


def cmd_launcher(stop: bool = False) -> int:
    """Bare `armance`: open the launcher (or first-run setup) in the browser.

    Grandma path. The launcher server is homed in the GLOBAL config dir (so a
    first run from any folder never litters a stray ``.armance`` there). No
    global config yet → the browser lands on the setup wizard; otherwise on the
    launcher window.

    Epic S: the page's first API call is gated. We resolve the web secret in the
    parent, pin it via ``ARMANCE_WEB_PASSWORD`` so the child server agrees, and
    open the browser with ``?token=`` when the secret was auto-generated — so
    SEC5 auto-login sets the cookie and the grandma never hits a login wall. A
    configured password is never put in the URL.
    """
    from armance import paths
    from armance.config import Config, load_config
    from armance.service import security

    launcher_home = paths.global_config_dir()

    # `armance --stop`: stop the launcher server, homed in the global dir (so it
    # is reachable from any cwd — symmetric with bare `armance` = launch).
    if stop:
        from armance.web.server_lock import stop_server

        stopped, message = stop_server(launcher_home)
        print(message, file=sys.stderr if not stopped else sys.stdout)
        return 0 if stopped else 1

    configured = paths.global_config_path().exists()
    target = "/launcher" if configured else "/setup"

    try:
        cfg = load_config()
    except Exception:  # noqa: BLE001 — first run: no config yet
        cfg = Config()
    # Determine auto-generation BEFORE pinning the env var (which would
    # otherwise make was_auto_generated see a "configured" secret).
    secret = security.resolve_web_secret(cfg)
    auto = security.was_auto_generated(cfg)
    os.environ["ARMANCE_WEB_PASSWORD"] = secret  # child server uses the same secret

    query = f"?token={secret}" if auto else ""
    _open_launcher_browser(f"{target}{query}")
    return cmd_web(launcher_home, ["--no-browser"], data_dir=launcher_home)


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

    # Bare `armance` (no args) is the grandma path: open the launcher (or the
    # first-run setup wizard) in the browser. Explicit help still prints usage.
    if not argv:
        return cmd_launcher()

    # `armance --stop` (bare): stop the launcher server homed in the global dir.
    if argv[0] == "--stop":
        return cmd_launcher(stop=True)

    if argv[0] in ("-h", "--help", "help"):
        print(
            "usage: armance {init,run,index,doctor,workflow,web,install-shortcut} "
            "[--version]\n"
            "  (run `armance` with no arguments to open the launcher)",
            file=sys.stderr,
        )
        return 0

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
                                 choices=["free-first", "low", "medium", "high", "adaptive", "optimised"])
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
        run_parser = argparse.ArgumentParser(prog="armance run", add_help=True)
        run_parser.add_argument(
            "--session",
            dest="session_id",
            default=None,
            help="Load a specific session id, skipping the resume picker.",
        )
        run_args = run_parser.parse_args(remaining)
        return cmd_run(root, session_id=run_args.session_id)
    if cmd == "index":
        return cmd_index(root)
    if cmd == "doctor":
        return cmd_doctor(root)
    if cmd == "web":
        return cmd_web(root, remaining)
    if cmd == "install-shortcut":
        return cmd_install_shortcut()
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
