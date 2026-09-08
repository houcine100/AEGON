# core/observability/decision_logger.py
# Logs every routing decision to a JSONL file after every turn.
# Every node visited, every decision made, and the final response
# are all recorded. Nothing is lost.

import json
import os
from collections import Counter
from datetime import datetime, timedelta


# --- Log file location ---
# Stored locally inside core/observability/logs/
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "decisions.jsonl")


def _ensure_log_dir() -> None:
    """Creates the logs directory if it does not exist."""
    os.makedirs(LOG_DIR, exist_ok=True)


def log_decision(state: dict) -> None:
    """
    Writes the full decision trail for one turn to the JSONL log file.
    Called by aegon_orchestrator.py after every turn completes.

    Each line in the JSONL file is one complete turn — fully self-contained.
    Fields logged:
        - timestamp
        - session_id
        - thread_id
        - raw_input
        - intent
        - confidence
        - governance_result
        - governance_reason
        - requires_approval
        - final_response
        - decision_log (full node trail)
    """
    _ensure_log_dir()

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": state.get("session_id"),
        "thread_id": state.get("thread_id"),
        "raw_input": state.get("raw_input"),
        "intent": state.get("intent"),
        "confidence": state.get("confidence"),
        "governance_result": state.get("governance_result"),
        "governance_reason": state.get("governance_reason"),
        "requires_approval": state.get("requires_approval"),
        "final_response": state.get("final_response"),
        "decision_log": state.get("decision_log", []),
    }

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[decision_logger] Failed to write log: {e}")


def read_last_n(n: int = 10) -> list:
    """
    Reads the last n decisions from the log file.
    Useful for debugging and review.
    """
    _ensure_log_dir()

    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        records = [json.loads(line) for line in lines if line.strip()]
        return records[-n:]
    except Exception as e:
        print(f"[decision_logger] Failed to read log: {e}")
        return []


def get_session_stats(days: int = 7) -> dict:
    """Return session stats for the weekly review."""
    if not os.path.exists(LOG_FILE):
        return {"session_count": 0, "avg_turns": 0.0, "top_intents": [], "governance_violations": 0}
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            records = [json.loads(l) for l in f if l.strip()]
    except Exception:
        return {"session_count": 0, "avg_turns": 0.0, "top_intents": [], "governance_violations": 0}

    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = []
    for r in records:
        try:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", ""))
            if ts >= cutoff:
                recent.append(r)
        except Exception:
            pass

    sessions: dict = {}
    for r in recent:
        sid = r.get("session_id") or "unknown"
        sessions.setdefault(sid, []).append(r)

    session_count = len(sessions)
    avg_turns = round(sum(len(v) for v in sessions.values()) / max(session_count, 1), 1)
    intents = Counter(r.get("intent") for r in recent if r.get("intent"))
    violations = sum(1 for r in recent if r.get("governance_result") == "fail")

    return {
        "session_count": session_count,
        "avg_turns": avg_turns,
        "top_intents": intents.most_common(3),
        "governance_violations": violations,
    }


def read_violations() -> list:
    """
    Returns all turns where governance_result was fail.
    Useful for security review.
    """
    _ensure_log_dir()

    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        records = [json.loads(line) for line in lines if line.strip()]
        return [r for r in records if r.get("governance_result") == "fail"]
    except Exception as e:
        print(f"[decision_logger] Failed to read violations: {e}")
        return []