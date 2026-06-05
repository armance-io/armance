"""Session persistence: state.json + ledger.json under .armance/sessions/<id>/.

A session captures which agent is active, which workflow + step is
currently running, and where the ledger lives. armance run prompts the
user to resume the most recent session if state.json is present.

Legacy TUIState enum has been dropped. Session wraps SessionState with
validated state transitions and atomic persist.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from armance.core.models.conversation import Conversation

logger = logging.getLogger(__name__)


class SessionState(BaseModel):
    """Slim session state.

    Per Spec §11_session.md — History moved to .armance/conversations/.
    """
    id: str
    created_at: str
    # Last write time. Bumped on every Session.save() so the resume picker
    # can sort sessions by recency without stat()-ing every file.
    updated_at: str = ""
    # Id of the session this one was forked from, if any. Forms a chain of
    # checkpoints: each `armance run` that starts a NEW session while a
    # previous one exists records the previous id here.
    parent_id: str | None = None
    current_agent: str | None = "system-context"
    current_context_version: str | None = None
    mode: str = "AMA"
    current_workflow: str | None = None
    current_step_id: str | None = None
    ledger_path: str | None = None
    current_provider: str | None = None
    current_model: str | None = None
    project_brief: str = ""
    # Ephemeral per-session set of agent names currently running on their
    # boost (provider, model). Resolved by service/boost_ops.boosted_model_for.
    # Never leaks into L0 project context. pydantic v2 serialises set→JSON
    # array via model_dump_json and coerces array→set on model_validate_json,
    # so this round-trips through state.json without a custom serializer.
    boosted_agents: set[str] = Field(default_factory=set)

    @classmethod
    def new(cls, parent_id: str | None = None) -> "SessionState":
        import random
        words = [
            "parapluies", "chimères", "silences", "secrets", "songes", "miroirs",
            "cahiers", "soupirs", "étoiles", "nuages", "plumes", "livres",
            "pensées", "mots", "ombres", "lumières", "flammes", "pages",
            "mystères", "horloges", "chemins", "voyages", "rêves", "jardins",
            "clefs", "lettres", "portraits", "souvenirs", "murmures", "vagues",
            "brises", "parfums", "instants", "dialogues", "esprits", "reflets",
            "ciels", "horizons", "architectures", "bibliothèques", "ateliers"
        ]
        num = random.randint(10, 999)
        word = random.choice(words)
        sid = f"{num}-{word}"
        
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            id=sid,
            created_at=now,
            updated_at=now,
            parent_id=parent_id,
        )


class Session:
    """Runtime wrapper around SessionState with history persistence."""

    def __init__(self, state: SessionState, armance_root: Path) -> None:
        self._state = state
        self._root = armance_root
        from armance.storage.conversation_store import ConversationStore
        self._store = ConversationStore(armance_root)
        self._conversation: Conversation | None = None
        self._metadata: dict | None = None

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def conversation(self) -> Conversation:
        if self._conversation is None:
            self._conversation, self._metadata = self._store.load(self._state.id)
        return self._conversation

    @property
    def metadata(self) -> dict:
        if self._metadata is None:
            self._conversation, self._metadata = self._store.load(self._state.id)
        return self._metadata

    def save(self) -> Path:
        # Bump the recency stamp so the resume picker can rank sessions by
        # most-recent activity without stat()-ing every file.
        self._state.updated_at = datetime.now(timezone.utc).isoformat()
        if self._conversation is not None:
            self._store.save(self._state.id, self._conversation, self.metadata)
        return save_state(self._root, self._state)


def session_dir(armance_root: Path, session_id: str) -> Path:
    return armance_root / "sessions" / session_id


def state_path(armance_root: Path, session_id: str) -> Path:
    return session_dir(armance_root, session_id) / "state.json"


def save_state(armance_root: Path, state: SessionState) -> Path:
    sdir = session_dir(armance_root, state.id)
    sdir.mkdir(parents=True, exist_ok=True)
    if state.ledger_path is None:
        state.ledger_path = (sdir / "ledger.json").as_posix()
    path = sdir / "state.json"
    # Atomic write: temp file + rename
    tmp = path.with_suffix(".tmp")
    tmp.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def load_state(armance_root: Path, session_id: str) -> SessionState:
    path = state_path(armance_root, session_id)
    return SessionState.model_validate_json(path.read_text(encoding="utf-8"))


def latest_session_id(armance_root: Path) -> str | None:
    sessions_root = armance_root / "sessions"
    if not sessions_root.exists():
        return None
    candidates = [p for p in sessions_root.iterdir() if (p / "state.json").exists()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: (p / "state.json").stat().st_mtime)
    return candidates[-1].name


def session_summary(armance_root: Path, session_id: str) -> dict:
    """Quick stats for the resume picker: turn count, age, est tokens."""
    sessions_root = armance_root / "sessions"
    sdir = sessions_root / session_id
    if not sdir.exists():
        return {}
    state_p = sdir / "state.json"
    conv_p = sdir / "conversation.md"
    import datetime
    out: dict = {"id": session_id}
    if state_p.exists():
        out["last_update"] = datetime.datetime.fromtimestamp(
            state_p.stat().st_mtime, tz=datetime.timezone.utc
        ).isoformat()
    if conv_p.exists():
        text = conv_p.read_text(encoding="utf-8", errors="ignore")
        # Cheap heuristic: 1 token ≈ 4 chars
        out["est_tokens"] = len(text) // 4
        out["turns"] = text.count("\n## [")
    else:
        out["est_tokens"] = 0
        out["turns"] = 0
    return out


def list_sessions(armance_root: Path) -> list[dict]:
    """Return every persisted session with its summary fields, newest first.

    Output schema: id, created_at, updated_at, parent_id, turns, est_tokens.
    `updated_at` falls back to file mtime for legacy sessions whose state.json
    predates the field. Sorts descending by updated_at so the resume picker
    can show recency without an extra pass.
    """
    sessions_root = armance_root / "sessions"
    if not sessions_root.exists():
        return []
    out: list[dict] = []
    for sdir in sessions_root.iterdir():
        state_p = sdir / "state.json"
        if not state_p.exists():
            continue
        try:
            st = SessionState.model_validate_json(state_p.read_text(encoding="utf-8"))
        except Exception:
            logger.debug("list_sessions: skip unreadable %s", state_p, exc_info=True)
            continue
        if not st.updated_at:
            import datetime as _dt
            st.updated_at = _dt.datetime.fromtimestamp(
                state_p.stat().st_mtime, tz=_dt.timezone.utc,
            ).isoformat()
        summary = session_summary(armance_root, st.id)
        out.append({
            "id": st.id,
            "created_at": st.created_at,
            "updated_at": st.updated_at,
            "parent_id": st.parent_id,
            "turns": summary.get("turns", 0),
            "est_tokens": summary.get("est_tokens", 0),
        })
    out.sort(key=lambda s: s["updated_at"], reverse=True)
    return out


def start_or_resume(armance_root: Path, *, resume: bool) -> SessionState:
    if resume:
        sid = latest_session_id(armance_root)
        if sid is not None:
            state = load_state(armance_root, sid)
            logger.info(
                "resumed session %s", state.id
            )
            return state
        logger.info("no prior session found; starting fresh")
    # Fresh session: link to the most recent one (if any) so the chain
    # captures "this checkpoint was forked from <parent>".
    parent = latest_session_id(armance_root)
    state = SessionState.new(parent_id=parent)
    save_state(armance_root, state)
    return state
