# core/feedback/feedback_store.py
# Logs every surfaced finding and records Sir's verdict.
# Provides hit-rate calculation and suppression gate for the sentinel.
# Storage: local JSON — no external calls, no DB dependency.

import json
import uuid
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

_LOG_FILE = Path(__file__).parent / "feedback_log.json"
_lock = threading.Lock()

_SUPPRESS_THRESHOLD = 0.3   # below 30% useful → suppress
_SUPPRESS_MIN_SAMPLES = 5   # need at least 5 rated findings before suppressing


def _load() -> list:
    if not _LOG_FILE.exists():
        return []
    try:
        return json.loads(_LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(records: list) -> None:
    _LOG_FILE.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")


def log_finding(finding_type: str, content: str, urgency: str) -> str:
    """Log a surfaced finding. Returns its ID for later feedback recording."""
    record_id = str(uuid.uuid4())
    with _lock:
        records = _load()
        records.append({
            "id": record_id,
            "type": finding_type,
            "content": content,
            "urgency": urgency,
            "surfaced_at": datetime.now(timezone.utc).isoformat(),
            "verdict": None,
        })
        _save(records)
    return record_id


def record_response(finding_id: str, verdict: str) -> bool:
    """Record Sir's verdict: 'useful' or 'not_relevant'. Returns True if found."""
    with _lock:
        records = _load()
        for r in records:
            if r["id"] == finding_id:
                r["verdict"] = verdict
                r["responded_at"] = datetime.now(timezone.utc).isoformat()
                _save(records)
                return True
    return False


def get_hit_rate(finding_type: str, days: int = 30) -> tuple:
    """Returns (hit_rate, sample_count) for finding_type in the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with _lock:
        records = _load()
    rated = [
        r for r in records
        if r["type"] == finding_type
        and r.get("verdict") is not None
        and datetime.fromisoformat(r["surfaced_at"]) >= cutoff
    ]
    if not rated:
        return 1.0, 0
    useful = sum(1 for r in rated if r["verdict"] == "useful")
    return useful / len(rated), len(rated)


def should_suppress(finding_type: str) -> bool:
    """Return True if this finding type has a low enough hit-rate to suppress."""
    rate, count = get_hit_rate(finding_type)
    return count >= _SUPPRESS_MIN_SAMPLES and rate < _SUPPRESS_THRESHOLD


def get_weekly_report() -> str:
    """Return a spoken summary of hit rates for the past 7 days."""
    finding_types = [
        "deadline", "habit_deviation", "stale_decision",
        "dormant_project", "recurring_error", "calendar_approaching",
    ]
    lines = []
    for ft in finding_types:
        rate, count = get_hit_rate(ft, days=7)
        if count == 0:
            continue
        label = ft.replace("_", " ").title()
        pct = int(rate * 100)
        tag = " — suppressed" if should_suppress(ft) else ""
        lines.append(f"{label}: {pct}% useful from {count} rated{tag}.")
    if not lines:
        return "No rated findings in the past week, Sir."
    return "Sentinel weekly report. " + " ".join(lines)
