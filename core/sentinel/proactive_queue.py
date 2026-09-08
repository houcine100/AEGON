# core/sentinel/proactive_queue.py
# Thread-safe queue for sentinel findings.
# Sentinel pushes; orchestrator drains at session start.

import threading
from core.sentinel.findings import Finding

_queue: list = []
_lock = threading.Lock()

_URGENCY_ORDER = {"high": 0, "medium": 1, "low": 2}


def push(finding: Finding) -> None:
    with _lock:
        _queue.append(finding)


def drain(max_items: int = 3) -> list:
    """Return up to max_items findings, high-urgency first. Remainder stay queued."""
    with _lock:
        all_findings = list(_queue)
        _queue.clear()
        sorted_findings = sorted(all_findings, key=lambda f: _URGENCY_ORDER.get(f.urgency, 3))
        to_surface = sorted_findings[:max_items]
        for f in sorted_findings[max_items:]:
            _queue.append(f)
    return to_surface


def size() -> int:
    with _lock:
        return len(_queue)


_TYPE_LABELS = {
    "deadline": "Deadline alert",
    "habit_deviation": "Habit check",
    "stale_decision": "Open decision",
    "dormant_project": "Dormant project",
    "recurring_error": "Recurring issue",
    "calendar_approaching": "Calendar alert",
}


def format_findings_for_speech(findings: list) -> str:
    """Convert a list of Findings into a spoken string. Marks each as surfaced."""
    if not findings:
        return ""
    parts = []
    for f in findings:
        f.surfaced = True
        label = _TYPE_LABELS.get(f.type, f.type.replace("_", " ").title())
        parts.append(f"{label}: {f.content}")
    noun = "observation" if len(findings) == 1 else "observations"
    intro = f"Sir, I have {len(findings)} {noun}."
    return intro + " " + " ".join(parts)
