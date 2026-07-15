# Armance — Feature Implementation Guide

> Audience: AI agents tasked with implementing new features or epics for the Armance project.
> This file outlines the strict architectural principles, guidelines, and processes you must follow.

---

## 0. Canonical Issue & Strategy Source

The public `armance` repository is kept clean of internal product strategy and roadmap discussions. 

> [!IMPORTANT]
> **Private Strategic Brain**: The canonical definitions of all epic features, user stories, macro-roadmaps, and chronological hand-off logs live in a private maintainer repository; ask the maintainer for access.
> 
> When implementing features:
> 1. Check the issue tracker and the latest hand-off log entries in that private repository.
> 2. Read the corresponding feature epic file there.
> 3. **Document everything** (progress, design decisions, outcomes, or residual bugs) in that private repository. Never write strategic notes or private client details into the public `armance` repository.

---

## 1. Strict Development Guidelines

### KISS (Keep It Simple, Stupid)
- Do not over-engineer. Prefer simple, clean, and direct solutions over complex abstractions, deep class hierarchies, or speculative "just-in-case" code.
- Avoid introducing helper frameworks or libraries unless explicitly approved.

### Pragmatism Over Rigid Metrics
- File size/LOC limits (e.g. 300 lines for Python backend files, 250 lines for React components) are **guidelines/targets, not absolute blockages**.
- **Cohesion is preferred**: If keeping a React `.tsx` component whole and complete makes the code more readable and self-contained, keep it in a single file even if it exceeds the line limit, rather than arbitrarily splitting it just to pass a metric check. 

### Modularity & Architecture Layers
- Respect the four-tier architectural hierarchy:
  ```
  client  →  transport  →  service  →  core
  ```
- Lower layers must never import from upper layers.
- Build clean interfaces/Protocols (like platform abstractions in `armance.platform`) to keep modules decoupled.

### No Hard-coded Values
- Avoid hard-coding API keys, magic constants, default models, embedding dimensions, or file paths.
- Load non-secret config from `Config` and read secrets via safe mechanisms.

### Readability & Documentation
- Write clean, self-documenting code with clear variable and function names.
- Document any non-obvious design decisions, constraints, or third-party workarounds directly in the code comments.

### Test-Driven Development (TDD)
- Write tests (ideally red first) before implementing logic changes.
- Verify that tests pass locally before committing:
  ```bash
  uv run pytest tests/ -q
  uv run ruff check src/
  bash scripts/check_invariants.sh
  ```
- Maintain or improve the overall coverage gate requirements (e.g. 85-90% coverage on new backend/platform layers).

---

## 2. Process & Commit Hygiene

- **Logical commits**: One commit should represent exactly one logical change.
- **Conventional Commits**: Format commit messages according to the rules in [BUG_FIXING_GUIDE.md](BUG_FIXING_GUIDE.md#commit-message).
- **Cryptographic Signatures**: All commits must be cryptographically signed (`git commit -sS`).
