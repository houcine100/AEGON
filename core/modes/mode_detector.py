# core/modes/mode_detector.py
# Infers operating mode at session start from time, calendar, and recent activity.
# Called once per session. Silent — never speaks.

from datetime import datetime, timedelta

from prompts.mode_prompts import Mode

_CODING_SIGNALS = {
    "code", "coding", "function", "bug", "error", "python", "git",
    "deploy", "test", "refactor", "commit", "pull request", "debug",
}
_RESEARCH_SIGNALS = {
    "research", "article", "reading", "paper", "study", "learning",
    "investigate", "notes", "wiki", "book", "document",
}


def _has_imminent_event(window_minutes: int = 30) -> bool:
    """Returns True if a calendar event starts within window_minutes from now."""
    try:
        from core.security.gmail_auth import get_calendar_service
        service = get_calendar_service()
        if service is None:
            return False
        now = datetime.now().astimezone()
        window_end = now + timedelta(minutes=window_minutes)
        response = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=1,
        ).execute()
        return bool(response.get("items"))
    except Exception:
        return False


def _infer_from_recent_activity(window_minutes: int = 60) -> str:
    """Returns deep_work or research if recent memory facts signal those modes, else ''."""
    try:
        from core.memory.memory_store import get_recent_facts
        facts = get_recent_facts(minutes=window_minutes)
        text = " ".join(f["fact"].lower() for f in facts)
        if any(sig in text for sig in _CODING_SIGNALS):
            return Mode.DEEP_WORK
        if any(sig in text for sig in _RESEARCH_SIGNALS):
            return Mode.RESEARCH
        return ""
    except Exception:
        return ""


def infer_mode_from_context() -> str:
    """
    Returns the inferred mode for session start.
    Priority: AEGON_MODE env override → time → calendar → app context → recent memory → standard.
    Auto-detected changes are silent — callers must not announce them.
    """
    import os
    override = os.environ.get("AEGON_MODE", "").lower().strip()
    if override in (Mode.MORNING, Mode.NIGHT, Mode.FOCUS, Mode.DEEP_WORK, Mode.RESEARCH, Mode.STANDARD):
        return override

    hour = datetime.now().hour

    if 6 <= hour < 9:
        return Mode.MORNING
    if hour >= 22 or hour < 4:
        return Mode.NIGHT
    if _has_imminent_event():
        return Mode.FOCUS

    activity_mode = _infer_from_recent_activity()
    if activity_mode:
        return activity_mode

    return Mode.STANDARD
