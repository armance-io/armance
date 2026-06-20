# Contributing to Armance

Thank you for considering a contribution.

Armance is dual-licensed: AGPL-3.0-or-later for open-source use, and a
commercial license is available from the copyright holder. To keep that
option open for the project, **every contribution must be signed off
under the Developer Certificate of Origin (DCO)** — see below.

---

## TL;DR

1. Open an issue first if the change is non-trivial.
2. Branch from `main`, keep commits focused.
3. Sign every commit with `git commit -s` (DCO).
4. Run `uv run pytest tests/` and `uv run ruff check src/ tests/` before pushing.
5. Open a pull request. CI must pass.

---

## Developer Certificate of Origin (DCO)

Armance uses the [Developer Certificate of Origin v1.1](https://developercertificate.org/).
It is a lightweight alternative to a full Contributor License Agreement
(CLA): you certify, with each commit, that you have the right to submit
the change under the project's licence.

By adding a `Signed-off-by` trailer to your commits, you certify the
following:

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
1 Letterman Drive
Suite D4700
San Francisco, CA, 94129

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

### How to sign off your commits

Use the `-s` flag on every commit:

```bash
git commit -s -m "fix: handle empty roster in Malik proposals"
```

This appends a trailer of the form:

```
Signed-off-by: Your Real Name <your.email@example.com>
```

The name and email must match the identity of a real person (not a
pseudonym) and the email under which you actually receive mail. The
git config used is:

```bash
git config user.name  "Your Real Name"
git config user.email "your.email@example.com"
```

If you forget to sign a commit, amend it:

```bash
git commit --amend --no-edit -s
```

For a batch of unsigned commits on a branch, rebase with sign-off:

```bash
git rebase --signoff main
```

Pull requests without DCO sign-off on every commit will be asked to
amend before merge.

---

## Licence implications

- All contributions are accepted **under AGPL-3.0-or-later**, the
  current project licence.
- Because the copyright holder of Armance is a single legal entity
  (Guillaume Richard), the holder may **dual-licence** the codebase —
  including your contributions — under a commercial licence. By signing
  off under the DCO, you certify that you have the right to submit your
  contribution under the project's licence, which is sufficient for the
  holder to dual-licence.
- If you cannot agree to those terms, please do not submit a
  contribution.

If your employer holds rights to your work, you must obtain their
permission first — the DCO sign-off implies they have agreed.

---

## Development setup

Prerequisites: Python ≥ 3.11, [`uv`](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:armance-io/armance.git
cd armance
uv sync
uv pip install -e .
```

Verify:

```bash
uv run pytest tests/ -q          # unit + integration (no network)
uv run ruff check src/ tests/    # lint
uv run python scripts/check_invariants.sh   # layering invariants
```

For live-LLM smoke tests (requires `OPENROUTER_API_KEY`):

```bash
uv run python scripts/qa_live.py
```

---

## Coding conventions

Read [`CLAUDE.md`](CLAUDE.md) — it documents the project's architectural
invariants. The short version:

- **Layering** `client → transport → service → core`. Lower layers never
  import from upper layers. Enforced by `import-linter`.
- Python ≥ 3.11. `from __future__ import annotations` at the top of
  every module. Type hints everywhere. `asyncio` for parallelism.
- Files ≤ 300 LOC where reasonable. Big monoliths get split.
- `logging` only — no `print` for diagnostics.
- **No hardcoded user-facing strings**. Everything goes through
  `armance.nls.t("key")` and lives in `src/armance/nls_catalogues/{en,fr,es,de,zh,ja}.yaml`.
- **No hardcoded model lists or pricing**. Models are discovered from
  each provider's live catalogue.
- Tests: `pytest` + `pytest-asyncio` + `respx` + `monkeypatch`. **No
  real network calls** in `tests/`.
- Conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`,
  `chore:`). Imperative mood.

---

## Pull request checklist

Before opening a PR:

- [ ] All commits have a DCO `Signed-off-by:` trailer (`git commit -s`).
- [ ] `uv run pytest tests/` passes.
- [ ] `uv run ruff check src/ tests/` passes.
- [ ] New user-facing strings go through `armance.nls.t()` and have
      entries in all translation files (en, fr, es, de, zh, ja).
- [ ] No new hardcoded model ids, pricing, or provider-specific magic.
- [ ] Tests cover the change (regression test if it's a fix; behaviour
      test if it's a feature).
- [ ] If you touched the architecture, `scripts/check_invariants.sh`
      still passes.
- [ ] CHANGELOG entry under the `Unreleased` section.

The PR description should explain **why**, not just **what** — link the
issue, summarise the trade-off you considered.

---

## Releasing (bundling the web UI)

The static web UI (`src/armance/web_dist/`) is a **build artifact** and is
gitignored. A plain `uv build` or `pip install git+…` therefore produces an
**API-only** wheel. Release wheels (the ones published to PyPI) must bundle
the UI so `pip install armance && armance web` serves it with Python only:

```bash
scripts/build_release.sh        # pnpm build → web_dist → uv build → verify
```

This needs Node + pnpm on the build machine (CI), never on the user's. The
script fails loudly if the bundle is missing from the resulting wheel.
Publish the `dist/*.whl` and `dist/*.tar.gz` it produces.

### Cutting a release — two clicks

CI (`.github/workflows/release.yml`) does the build + publish. Two ways in:

1. **From the Actions tab (recommended).** Set the version in `pyproject.toml`,
   commit, then **Actions → Release → Run workflow** and pick the channel:
   - **beta** — the version *must* carry a pre-release suffix (e.g.
     `0.2-beta.4`). Published as a PyPI pre-release + a GitHub *pre-release*.
     The `install.sh` / `install.ps1` scripts pass `--pre`, so beta users get
     it; plain `pip install armance` does not.
   - **ga** — the version *must* be final (e.g. `0.3.0`). Becomes the default
     for everyone.

   The workflow refuses a channel/version mismatch (beta with a final version,
   or ga with a pre-release), creates the `v<version>` tag for you, builds,
   publishes to PyPI via OIDC, and drafts a GitHub Release with install
   instructions. No tokens, no manual tagging.

2. **By hand.** `git tag vX.Y.Z && git push origin vX.Y.Z` — the channel is
   inferred from whether the version has a pre-release suffix.

The Linux/macOS/Windows installers live in the **armance.io** site repo and
always `pipx install armance --pre` from PyPI, so a published release is
available on all three OSes the moment it lands — nothing else to ship.

---

## Reporting bugs

Open a GitHub issue with:

- Armance version (`armance --version`).
- Python version (`python --version`).
- OS.
- Steps to reproduce.
- Expected vs actual behaviour.
- Relevant log fragments (`.armance/logs/`) if any, **redacted of any
  API key or private content**.

Security issues: please email `guillaume@richard-pro.fr` privately rather
than opening a public issue.

---

## Code of conduct

Be civil, technical, and specific. Disagree with the work, not the
person. Project maintainers may remove comments, commits, or PRs that
do not meet that bar.

---

## Questions

Open a discussion on GitHub, or email `guillaume@richard-pro.fr`.
