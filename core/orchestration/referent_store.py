# core/orchestration/referent_store.py
# Bounded, provenance-tagged working-memory referent store (Phase B5 / flag F33).
#
# Replaces the transcript-vs-firewall binary: orchestrator_node resolves cross-turn
# pronouns ("weather there") against this small typed store instead of raw history.
# Only "tool_result"-provenance referents are ever written or read in this increment —
# values the orchestrator itself already put into a validated tool_input once. No
# "memory"-provenance path exists yet, so there is nothing for the provenance gate
# to have to block yet; latest() still enforces the allow-list so a memory path added
# later fails closed by default instead of by omission.
#
# Per-session, in-process, thread-safe. Not persisted — resets with the process,
# same as proactive_queue.

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

MAX_REFERENTS_PER_SESSION = 4   # Cowan's working-memory bound
_TTL_SECONDS = 30 * 60           # a referent older than this is stale, not resolved

_store: dict = {}   # session_id -> list[Referent], oldest first
_lock = threading.Lock()


@dataclass
class Referent:
    value: str
    type: str            # open string — e.g. "place", "artist", "repo", "note"
    provenance: str       # "tool_result" | "sir_utterance" | "memory"
    created_at: float = field(default_factory=time.time)


def add(session_id: str, value: str, type_: str, provenance: str) -> None:
    """Store a referent, evicting the oldest once the session is at capacity."""
    if not session_id or not value or not type_ or not provenance:
        return
    with _lock:
        bucket = _store.setdefault(session_id, [])
        bucket.append(Referent(value=value, type=type_, provenance=provenance))
        if len(bucket) > MAX_REFERENTS_PER_SESSION:
            bucket.pop(0)


def latest(
    session_id: str,
    type_: Optional[str] = None,
    allowed_provenance: tuple = ("tool_result",),
) -> Optional[Referent]:
    """Most recent live referent, optionally filtered by type.
    Provenance-gated: only values whose provenance is in allowed_provenance are
    ever returned, regardless of what is stored for the session."""
    with _lock:
        bucket = _store.get(session_id, [])
        now = time.time()
        candidates = [
            r for r in bucket
            if r.provenance in allowed_provenance
            and (now - r.created_at) < _TTL_SECONDS
            and (type_ is None or r.type == type_)
        ]
        return candidates[-1] if candidates else None


def clear_session(session_id: str) -> None:
    with _lock:
        _store.pop(session_id, None)
