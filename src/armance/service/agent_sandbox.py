"""Defense-in-depth scrubbers applied to every LLM reply.

These run after the model returns and before any [EXECUTE:/...] interception,
so the actions actually fired match the agent's allow-list — even when a
weak free model hallucinates tags outside its sandbox.

Three layers:
  - strip_hallucinated_tool_calls(): drop <tool_call>...</tool_call> markup
    (no such mechanism in Armance; only [EXECUTE:/...] tags work).
  - truncate_repeated_garbage(): cut output when a 30+ char block repeats
    4+ times in a row (catches the 100x workflow-run loops on weak models).
  - strip_unauthorised_execute_tags(): per-role tag allow-list. Anything
    outside the list is removed + a warning logged.

Role → allowed tags:
  - armance:      /save, /library-*, plus legacy aliases
  - malik:       /recruit, /dismiss-all, /library-status
  - kim:       /workflow-design, /workflow-run, /library-status
  - mona:       /library-status
  - specialist:  no tags
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


_ROLE_TAG_ALLOWLIST: dict[str, set[str]] = {
    "armance": {
        "save", "library-index", "library-load", "library-unload",
        "library-unindex", "library-status",
        # legacy aliases tolerated for backwards compat
        "ingest-docs", "load", "forget", "rag-status",
    },
    "malik": {"recruit", "dismiss-all", "library-status"},
    "kim": {"workflow-design", "workflow-run", "workflow-stop", "library-status"},
    "mona": {"library-status", "save-deliverable", "load-run"},
    "specialist": {"load-run"},
}

_TAG_RE = re.compile(r"\[EXECUTE:/([\w-]+)(?::[^\]]*)?\]")


_TOOL_CALL_NAME_RE = re.compile(
    r"<tool_call>\s*([\w-]+)(?:\s*[:\s][^<\n]*)?\s*(?:</tool_call>)?",
    flags=re.IGNORECASE,
)


def normalise_hallucinated_tool_calls(text: str, *, allow: set[str]) -> str:
    """Convert `<tool_call>NAME[: arg]` to `[EXECUTE:/NAME]` when NAME is in
    the role's allow-list. Preserves user intent when a weak model emits the
    wrong format. Other tool_call blocks are left for strip_hallucinated_tool_calls
    to drop downstream.
    """
    if "<tool_call>" not in text:
        return text

    def _replace(m: re.Match[str]) -> str:
        name = m.group(1).lower()
        if name in allow:
            return f"[EXECUTE:/{name}]"
        return m.group(0)

    out = _TOOL_CALL_NAME_RE.sub(_replace, text)
    if out != text:
        logger.warning("normalised <tool_call> hallucination → [EXECUTE:/...]")
    return out


def strip_hallucinated_tool_calls(text: str) -> str:
    """Drop <tool_call>...</tool_call> blocks (or orphan tags). Armance never
    uses tool_call markup. Weak free models sometimes leak it from training
    data + spam it. Silent drop with a warning."""
    if "<tool_call>" not in text and "</tool_call>" not in text:
        return text
    cleaned = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<tool_call>[^\n]*", "", cleaned)
    cleaned = cleaned.replace("</tool_call>", "")
    if cleaned != text:
        logger.warning("stripped hallucinated <tool_call> markup from LLM reply")
    return cleaned.strip()


def truncate_repeated_garbage(text: str, max_repeats: int = 3) -> str:
    """If any 30+ char substring repeats > max_repeats times in a row, cut
    output at the first occurrence. Catches infinite loops from weak models."""
    m = re.search(r"(.{30,}?)(?:\1){" + str(max_repeats) + r",}", text, flags=re.DOTALL)
    if not m:
        return text
    cut = m.start() + len(m.group(1))
    logger.warning("truncated LLM reply: repeated-block loop detected")
    return text[:cut].rstrip() + "\n\n*(output truncated: repeated-block loop detected)*"


_ACK_TOKENS = (
    "parfait",
    "exact",
    "exact.",
    "exactement",
    "got it",
    "clair",
    "cadrage clair",
    "bien noté",
    "entendu",
    "bien.",
    "compris",
    "voilà",
    "voila",
    "tout à fait",
    "tout a fait",
    "c'est ça",
    "c'est cela",
    "bonne question",
    "tension émergente",
    "tension clé",
    "stratégie compense",
)


# Literal speaker markers a model emits when it starts scripting both sides of
# the dialogue: "[assistant: Kim]", "[assistant]", "[user]", "[utilisateur]",
# or a transcript header like "## [2026-…] user (system-…)". None of these are
# ever legitimate inside a single agent reply — cut at the first one.
_SPEAKER_MARKER_RE = re.compile(
    r"(?im)^\s*(?:"
    r"\[\s*(?:assistant|user|utilisateur|système|systeme|system)\b[^\]]*\]\s*$"  # [assistant: Kim]
    r"|#{1,6}\s*\[[^\]]*\]\s*(?:user|assistant|utilisateur)\b"                   # ## [ts] user (...)
    r")",
)


def cut_at_speaker_markers(text: str) -> str:
    """Cut a reply at the first literal speaker marker.

    Small models on long transcripts continue the recorded turn pattern and
    script the user's lines (and their own next turn) inside one reply, tagging
    them with markers like ``[assistant: Kim]`` or a ``## [...] user`` header.
    Everything from the first such marker on is hallucinated dialogue — drop it.
    """
    m = _SPEAKER_MARKER_RE.search(text)
    if m is None:
        return text
    cut = text[: m.start()].rstrip()
    logger.warning("truncated LLM reply: speaker marker detected (model scripting a dialogue)")
    if not cut:
        return text  # marker at the very top — nothing safe to keep; leave as-is
    return cut


def truncate_simulated_turns(text: str, max_acks: int = 1) -> str:
    """Cut reply when the model starts simulating user turns.

    Symptom: a single reply contains 2+ short paragraphs each opening with an
    acknowledgement token (``Parfait.`` / ``Exact.`` / ``Clair.`` / ``Voilà.``).
    Small models on long transcripts continue the Q/A pattern and write the
    user's lines themselves. We allow one legitimate opener (``Bien.``,
    ``Parfait.``) and cut at the second — the runaway second turn is dropped.
    """
    paragraphs = text.split("\n\n")
    ack_indices: list[int] = []
    for i, p in enumerate(paragraphs):
        head = p.strip().lower()
        if not head:
            continue
        first_line = head.splitlines()[0] if head else ""
        if any(first_line.startswith(tok) for tok in _ACK_TOKENS):
            ack_indices.append(i)
    if len(ack_indices) <= max_acks:
        return text
    cut_at = ack_indices[max_acks]
    cut_text = "\n\n".join(paragraphs[:cut_at]).rstrip()
    logger.warning(
        "truncated LLM reply: %d acknowledgements detected (model simulating user turns)",
        len(ack_indices),
    )
    return cut_text + "\n\n*(output truncated: model began simulating a multi-turn dialogue)*"


def strip_unauthorised_execute_tags(reply: str, *, agent_role: str) -> str:
    """Drop any [EXECUTE:/...] not in the role's allow-list. Logs every strip."""
    allow = _ROLE_TAG_ALLOWLIST.get(agent_role, set())
    dropped: list[str] = []

    def _replace(m: re.Match[str]) -> str:
        tag = m.group(1)
        if tag in allow:
            return m.group(0)
        dropped.append(tag)
        return ""

    cleaned = _TAG_RE.sub(_replace, reply)
    if dropped:
        logger.warning(
            "stripped %d unauthorised [EXECUTE:/...] tag(s) from %s reply: %s",
            len(dropped), agent_role, dropped,
        )
    return cleaned


def scrub_reply(reply: str, *, agent_role: str) -> str:
    """Apply scrubbers in order. The canonical entry point — every place
    that touches a raw LLM reply should call this.

    Order matters:
      1. Normalise `<tool_call>NAME` → `[EXECUTE:/NAME]` if NAME is allowed
         (preserves intent on weak models hallucinating wrong format).
      2. Drop remaining `<tool_call>` garbage.
      3. Truncate repeated-block loops.
      4. Strip any unauthorised [EXECUTE:/...] tags.
    """
    allow = _ROLE_TAG_ALLOWLIST.get(agent_role, set())
    reply = normalise_hallucinated_tool_calls(reply, allow=allow)
    reply = strip_hallucinated_tool_calls(reply)
    reply = truncate_repeated_garbage(reply)
    reply = cut_at_speaker_markers(reply)
    reply = truncate_simulated_turns(reply)
    reply = strip_unauthorised_execute_tags(reply, agent_role=agent_role)
    return reply
