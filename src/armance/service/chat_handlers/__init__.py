"""Per-meta-agent chat handlers.

Each module here owns the conversation loop for one meta-agent:
  - armance.py       — context / framing
  - malik.py        — recruiter
  - kim.py        — orchestrator
  - specialist.py   — generic non-meta agent chat (the default chat path)
  - common.py       — shared helpers (status, load-run intercept)

Mona lives in `armance.service.mona_ops` for now (legacy path).
"""
from __future__ import annotations
