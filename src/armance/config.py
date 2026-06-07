"""Armance configuration models and loaders.

Config is the union of:
- non-secret values stored in .armance/config.yaml
- secrets (API keys) stored in .env (loaded via python-dotenv)

Env values override yaml values for any field that maps to an env var.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ProviderName = Literal["openrouter", "claude-code", "custom-openai", "gemini"]
LanguageCode = Literal["en", "fr", "es", "de", "zh", "ja"]

DEFAULT_CHUNK_MAX_TOKENS = 4000
DEFAULT_CAVEMAN_PROTOCOL = "src/armance/protocols/caveman_ultra.txt"


class ProviderConfig(BaseModel):
    name: ProviderName
    api_key: str | None = None
    base_url: str | None = None
    ssl_verify: bool = True  # set False to skip TLS cert check (corporate MITM proxies)


class FootprintConfig(BaseModel):
    """Environmental footprint tracking settings.

    ``electricity_mix_zone`` is an ISO 3166-1 alpha-3 EcoLogits zone code.
    Common values: WOR (world avg), FRA, USA, DEU, GBR.
    V3 swap point: feed a GCP region carbon-intensity source here instead.
    """

    enabled: bool = True
    electricity_mix_zone: str = "WOR"
    show_water: bool = True


class WebConfig(BaseModel):
    """Web interface settings (Epic S · security gate).

    ``password`` is an optional persistent passcode for the web UI. When
    empty, `armance web` auto-generates a transient per-process token (see
    armance.service.security). It can also be overridden at runtime via the
    ``ARMANCE_WEB_PASSWORD`` environment variable.
    """

    password: str = ""


class Config(BaseModel):
    providers: list[ProviderConfig] = Field(default_factory=list)
    default_provider: str = ""
    default_model: str = ""
    chunk_max_tokens: int = DEFAULT_CHUNK_MAX_TOKENS
    caveman_protocol_path: str = DEFAULT_CAVEMAN_PROTOCOL
    budget_cap_usd: float | None = None
    budget_effort: str = "free-first"  # free-first (default), low, medium, high, adaptive, optimised
    embedding_provider: str = ""
    embedding_model: str = ""
    log_level: str = "INFO"  # INFO, DEBUG, etc
    language: LanguageCode = "en"  # UI + agent voice language
    prices: dict[str, dict[str, float]] = Field(default_factory=dict)
    footprint: FootprintConfig = Field(default_factory=FootprintConfig)
    web: WebConfig = Field(default_factory=WebConfig)

    def provider(self, name: str) -> ProviderConfig:
        for p in self.providers:
            if p.name == name:
                return p
        raise KeyError(f"provider not configured: {name}")


def _env_key_for(provider: str) -> str:
    sanitized = provider.upper().replace("-", "_")
    return f"{sanitized}_API_KEY"


def _env_base_url_for(provider: str) -> str:
    sanitized = provider.upper().replace("-", "_")
    return f"{sanitized}_BASE_URL"


def load_config() -> Config:
    """Load the GLOBAL config (config.yaml) then overlay global .env values.

    Clean break (grandma launcher): config and secrets are machine-wide,
    resolved via :mod:`armance.paths`, not per project folder. Returns an
    empty default Config if neither file exists.
    """
    from armance import paths

    yaml_path = paths.global_config_path()
    env_path = paths.global_env_path()

    raw: dict[str, Any] = {}
    if yaml_path.exists():
        loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{yaml_path} must be a mapping")
        raw = loaded

    cfg = Config(**raw)

    # Guarantee the default provider is present so agent calls never crash with
    # `provider not configured` when a config lists it only as default_provider
    # (e.g. claude-code). It still receives its env overlay below.
    if cfg.default_provider and all(p.name != cfg.default_provider for p in cfg.providers):
        cfg.providers.append(ProviderConfig(name=cfg.default_provider))

    env: dict[str, str | None] = dict(dotenv_values(env_path)) if env_path.exists() else {}
    env.update({k: v for k, v in os.environ.items() if v is not None})

    for provider in cfg.providers:
        api_key_var = _env_key_for(provider.name)
        base_url_var = _env_base_url_for(provider.name)
        if env.get(api_key_var):
            provider.api_key = env[api_key_var]
        if env.get(base_url_var):
            provider.base_url = env[base_url_var]
    return cfg


def save_config(cfg: Config) -> Path:
    """Persist non-secret fields to the GLOBAL config.yaml.

    API keys are stripped — they belong in .env.
    """
    from armance import paths

    config_dir = paths.global_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = paths.global_config_path()

    payload = cfg.model_dump()
    for provider in payload["providers"]:
        provider.pop("api_key", None)
    yaml_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return yaml_path


def write_env(providers: list[ProviderConfig]) -> Path:
    """Write provider API keys + base URLs into the GLOBAL .env."""
    from armance import paths

    paths.global_config_dir().mkdir(parents=True, exist_ok=True)
    env_path = paths.global_env_path()
    lines: list[str] = []
    for provider in providers:
        if provider.api_key:
            lines.append(f"{_env_key_for(provider.name)}={provider.api_key}")
        if provider.base_url:
            lines.append(f"{_env_base_url_for(provider.name)}={provider.base_url}")
    env_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return env_path


# Per-folder DATA layout (clean break: no config/secrets, no base agents here).
# Project-specific recruited specialists still live in the local agents/ dir.
ARMANCE_DIR_TREE = (
    "docs",
    "reports",
    "context",
    "agents",
    "workflows",
    "judge",
    "sessions",
    ".archive",
)


def ensure_armance_tree(repo_root: Path, config: Config | None = None) -> Path:
    """Create the per-folder DATA tree under ``<repo_root>/.armance``.

    Clean break (grandma launcher): config / secrets / base agents are global
    (see :func:`ensure_global_setup`); this only provisions a project folder's
    data directories.
    """
    from armance import paths

    armance = paths.local_data_dir(repo_root)
    for sub in ARMANCE_DIR_TREE:
        (armance / sub).mkdir(parents=True, exist_ok=True)
    _install_readme(armance)
    return armance


def ensure_global_setup(config: Config | None = None) -> Path:
    """Provision the GLOBAL config dir: base agents (+ builtin assets).

    config.yaml / .env are written by :func:`save_config` / :func:`write_env`.
    This installs the base meta-agents into the global agents dir so every
    project folder shares one staff roster.
    """
    from armance import paths

    global_dir = paths.global_config_dir()
    (global_dir / "agents" / "builtin").mkdir(parents=True, exist_ok=True)
    _install_builtin_agents(global_dir, config)
    return global_dir


def _install_readme(armance_root: Path) -> None:
    """Copy bundled README.md into .armance/README.md (install-time user guide)."""
    from importlib import resources as _res
    try:
        pkg_readme = _res.files("armance").joinpath("_data/README.md")
        content = pkg_readme.read_text(encoding="utf-8")
    except Exception:
        # Fallback: look for README.md two levels up from this file
        try:
            here = Path(__file__).resolve().parent
            # src/armance → src → repo_root
            content = (here.parent.parent / "README.md").read_text(encoding="utf-8")
        except Exception:
            return

    target = armance_root / "README.md"
    if not target.exists():
        try:
            target.write_text(content, encoding="utf-8")
        except Exception:
            pass


def _install_builtin_agents(armance_root: Path, config: Config | None = None) -> None:
    """Copy bundled built-in agents into .armance/agents/ and substitute placeholder defaults."""
    from importlib import resources
    from armance.core.models.agent import Agent

    try:
        builtin = resources.files("armance.service.agents.builtin")
    except (ModuleNotFoundError, AttributeError):
        return

    agents_dir = armance_root / "agents"

    def _process_and_write(entry_content: str, filename: str) -> None:
        # Files with names starting with '_' are non-agent assets (e.g. the
        # knowledge-base _armance_concepts.md). Copy verbatim, no frontmatter
        # processing.
        target = agents_dir / filename
        if filename.startswith("_"):
            try:
                target.write_text(entry_content, encoding="utf-8")
            except Exception:
                pass
            return

        if target.exists():
            try:
                existing_content = target.read_text(encoding="utf-8")
                existing_agent = Agent.from_frontmatter(existing_content)
                builtin_agent = Agent.from_frontmatter(entry_content)

                existing_ver = int(getattr(existing_agent, "version", 0) or 0)
                builtin_ver = int(getattr(builtin_agent, "version", 0) or 0)

                if builtin_ver <= existing_ver and existing_agent.model != "openai/gpt-4o-mini":
                    return  # Already up to date and not a placeholder

                # Newer builtin or placeholder: update body, preserve user's model/provider
                if existing_agent.model and existing_agent.model != "openai/gpt-4o-mini":
                    builtin_agent.provider = existing_agent.provider or builtin_agent.provider
                    builtin_agent.model = existing_agent.model
                elif config:
                    dp = getattr(config, "default_provider", "") or ""
                    dm = getattr(config, "default_model", "") or ""
                    if not dp and config.providers:
                        dp = config.providers[0].name
                        if dp == "gemini":
                            dm = "gemini-2.5-flash"
                        elif dp == "claude-code":
                            dm = "claude-sonnet-4-6"
                        elif dp == "openrouter":
                            dm = "google/gemini-2.5-flash"
                        else:
                            dm = "openai/gpt-4o-mini"
                    builtin_agent.provider = dp or "openrouter"
                    builtin_agent.model = dm or "openai/gpt-4o-mini"
                entry_content = builtin_agent.to_markdown()
            except Exception:
                # Fallback: old heuristic (file lacks proper frontmatter)
                existing_content = target.read_text(encoding="utf-8")
                if "openai/gpt-4o-mini" not in existing_content:
                    return  # Custom agent, leave intact
                # Placeholder — fall through to overwrite with substituted content
                if config:
                    try:
                        builtin_agent = Agent.from_frontmatter(entry_content)
                        dp = getattr(config, "default_provider", "") or ""
                        dm = getattr(config, "default_model", "") or ""
                        if not dp and config.providers:
                            dp = config.providers[0].name
                            if dp == "gemini":
                                dm = "gemini-2.5-flash"
                            elif dp == "claude-code":
                                dm = "claude-sonnet-4-6"
                            elif dp == "openrouter":
                                dm = "google/gemini-2.5-flash"
                            else:
                                dm = "openai/gpt-4o-mini"
                        builtin_agent.provider = dp or "openrouter"
                        builtin_agent.model = dm or "openai/gpt-4o-mini"
                        entry_content = builtin_agent.to_markdown()
                    except Exception as e2:
                        logger.error("Failed to substitute placeholder in agent %s: %s", filename, e2)
        else:
            # Fresh install: substitute placeholder with user config
            if config:
                try:
                    agent = Agent.from_frontmatter(entry_content)
                    if agent.model == "openai/gpt-4o-mini":
                        dp = getattr(config, "default_provider", "") or ""
                        dm = getattr(config, "default_model", "") or ""
                        if not dp and config.providers:
                            dp = config.providers[0].name
                            if dp == "gemini":
                                dm = "gemini-2.5-flash"
                            elif dp == "claude-code":
                                dm = "claude-sonnet-4-6"
                            elif dp == "openrouter":
                                dm = "google/gemini-2.5-flash"
                            else:
                                dm = "openai/gpt-4o-mini"
                        agent.provider = dp or "openrouter"
                        agent.model = dm or "openai/gpt-4o-mini"
                        entry_content = agent.to_markdown()
                except Exception as e:
                    logger.error("Failed to substitute placeholder in agent %s: %s", filename, e)

        try:
            target.write_text(entry_content, encoding="utf-8")
        except Exception:
            pass

    # Copy from service.agents.builtin
    try:
        for entry in builtin.iterdir():
            if not entry.name.endswith(".md"):
                continue
            try:
                _process_and_write(entry.read_text(encoding="utf-8"), entry.name)
            except Exception:
                pass
    except Exception:
        pass


