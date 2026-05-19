"""[EXECUTE:/workflow-run:<name>:<mode>] regex + mode propagation."""
from __future__ import annotations

from armance.service.chat_handlers.kim import _WF_RUN_RE


def test_regex_parses_name_only() -> None:
    m = _WF_RUN_RE.search("[EXECUTE:/workflow-run:dossier-hist]")
    assert m
    assert m.group(1) == "dossier-hist"
    assert m.group(2) is None


def test_regex_parses_name_and_mode_interactive() -> None:
    m = _WF_RUN_RE.search("[EXECUTE:/workflow-run:dossier-hist:interactive]")
    assert m
    assert m.group(1) == "dossier-hist"
    assert m.group(2) == "interactive"


def test_regex_parses_name_and_mode_autonomous() -> None:
    m = _WF_RUN_RE.search("[EXECUTE:/workflow-run:dossier-hist:autonomous]")
    assert m
    assert m.group(1) == "dossier-hist"
    assert m.group(2) == "autonomous"


def test_regex_rejects_unknown_mode_chars() -> None:
    """Mode is `[a-z]+` only — digits, hyphens, slashes excluded so we
    don't accidentally swallow more of the tag."""
    m = _WF_RUN_RE.search("[EXECUTE:/workflow-run:dossier-hist:mode-1]")
    # `mode-1` doesn't match `[a-z]+`; only `mode` would match, but the `-1`
    # then breaks the closing bracket → entire pattern fails.
    if m:
        # Either the regex bailed out, or matched only `mode` and the rest
        # of the tag is left in the string. Either way mode≠"mode-1".
        assert m.group(2) != "mode-1"
