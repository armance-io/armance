"""Tests for web access-token / password resolution (Epic S · SEC1-SEC2)."""
from __future__ import annotations

import re

import pytest

from armance.config import Config, WebConfig
from armance.service import security


@pytest.fixture(autouse=True)
def _reset_cached_token():
    """Each test starts with a fresh process-token cache."""
    security.reset_web_secret_cache()
    yield
    security.reset_web_secret_cache()


def test_env_password_takes_precedence(monkeypatch):
    monkeypatch.setenv("ARMANCE_WEB_PASSWORD", "from-env")
    cfg = Config(web=WebConfig(password="from-config"))
    assert security.resolve_web_secret(cfg) == "from-env"


def test_config_password_used_when_no_env(monkeypatch):
    monkeypatch.delenv("ARMANCE_WEB_PASSWORD", raising=False)
    cfg = Config(web=WebConfig(password="from-config"))
    assert security.resolve_web_secret(cfg) == "from-config"


def test_random_token_when_unconfigured(monkeypatch):
    monkeypatch.delenv("ARMANCE_WEB_PASSWORD", raising=False)
    cfg = Config()
    secret = security.resolve_web_secret(cfg)
    # 32 hex characters, as specified by SEC1.
    assert re.fullmatch(r"[0-9a-f]{32}", secret)


def test_random_token_is_stable_within_process(monkeypatch):
    monkeypatch.delenv("ARMANCE_WEB_PASSWORD", raising=False)
    cfg = Config()
    first = security.resolve_web_secret(cfg)
    second = security.resolve_web_secret(cfg)
    assert first == second


def test_was_auto_generated_reflects_source(monkeypatch):
    monkeypatch.delenv("ARMANCE_WEB_PASSWORD", raising=False)
    cfg = Config()
    security.resolve_web_secret(cfg)
    assert security.was_auto_generated(cfg) is True

    cfg2 = Config(web=WebConfig(password="explicit"))
    assert security.was_auto_generated(cfg2) is False


def test_constant_time_check_accepts_valid(monkeypatch):
    monkeypatch.delenv("ARMANCE_WEB_PASSWORD", raising=False)
    cfg = Config(web=WebConfig(password="s3cret"))
    assert security.check_web_secret(cfg, "s3cret") is True
    assert security.check_web_secret(cfg, "wrong") is False
    assert security.check_web_secret(cfg, "") is False
    assert security.check_web_secret(cfg, None) is False
