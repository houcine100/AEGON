# core/sentinel/sentinel.py
# Sentinel daemon — two threads:
#   1. 30-minute timer: evaluates all five rules, queues findings.
#   2. 5-minute calendar poll: surfaces events within 15 minutes as immediate findings.
# on_fact_stored(): called by fact_extractor on each new fact — triggers rule evaluation.
# Never blocks the voice loop. Never writes to memory.

import threading
from datetime import datetime, timedelta
from core.sentinel.findings import Finding
from core.sentinel.rules import run_all_rules
from core.sentinel.proactive_queue import push

INTERVAL_SECONDS = 1800        # 30 minutes — periodic rule evaluation
CALENDAR_POLL_SECONDS = 300    # 5 minutes — calendar proximity check
CALENDAR_WINDOW_MINUTES = 15   # surface events starting within this window

_thread: threading.Thread = None
_calendar_thread: threading.Thread = None
_shutdown = threading.Event()
_surfaced_event_ids: set = set()        # dedup: each calendar event surfaced at most once
_last_surfaced_id: str = None           # ID of last finding logged to feedback_store
_deep_work_gap_date: str | None = None  # dedup: deep-work-gap fires at most once per day


# ── Immediate surfacing ────────────────────────────────────────────────────────

def _surface_immediate(finding: Finding) -> None:
    """Speak a finding right now — bypasses the proactive queue."""
    global _last_surfaced_id
    try:
        from core.sentinel.proactive_queue import format_findings_for_speech
        from core.voice.speak import speak
        from core.feedback.feedback_store import log_finding
        finding.surfaced = True
        _last_surfaced_id = log_finding(finding.type, finding.content, finding.urgency)
        text = format_findings_for_speech([finding])
        if text:
            speak(text)
    except Exception as e:
        print(f"[sentinel] Immediate surface error: {e}")


def get_last_surfaced_id() -> str:
    """Return the feedback_store ID of the most recently spoken finding."""
    return _last_surfaced_id


def _dispatch(findings: list) -> None:
    """Route findings: immediate → speak now; session_start → queue.
    Suppressed finding types (low hit-rate) are silently dropped."""
    try:
        from core.feedback.feedback_store import should_suppress
        findings = [f for f in findings if not should_suppress(f.type)]
    except Exception:
        pass  # feedback_store unavailable — surface everything
    for finding in findings:
        if finding.timing == "immediate":
            _surface_immediate(finding)
        else:
            push(finding)


# ── 30-minute timer loop ──────────────────────────────────────────────────────

def _sentinel_loop() -> None:
    while not _shutdown.wait(INTERVAL_SECONDS):
        try:
            findings = run_all_rules()
            _dispatch(findings)
            if findings:
                print(f"[sentinel] {len(findings)} finding(s) dispatched.")
        except Exception as e:
            print(f"[sentinel] Rule evaluation error: {e}")


# ── New-fact trigger ──────────────────────────────────────────────────────────

def on_fact_stored() -> None:
    """Called by fact_extractor after each new fact is stored.
    Runs all rules in a background thread — never blocks extraction."""
    def _evaluate():
        try:
            findings = run_all_rules()
            _dispatch(findings)
        except Exception as e:
            print(f"[sentinel] on_fact_stored error: {e}")
    threading.Thread(target=_evaluate, daemon=True, name="sentinel-fact-trigger").start()


# ── Calendar approaching trigger ──────────────────────────────────────────────

def _check_calendar_approaching() -> None:
    """Query calendar for events starting within CALENDAR_WINDOW_MINUTES.
    Surfaces each unseen event as an immediate Finding."""
    try:
        from core.security.gmail_auth import get_calendar_service
        service = get_calendar_service()
        if service is None:
            return
        now = datetime.now().astimezone()
        window_end = now + timedelta(minutes=CALENDAR_WINDOW_MINUTES)
        response = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=5,
        ).execute()
        for event in response.get("items", []):
            event_id = event.get("id", "")
            if event_id in _surfaced_event_ids:
                continue
            summary = event.get("summary", "a calendar event")
            start_str = event.get("start", {}).get("dateTime", "")
            if not start_str:
                continue
            start_dt = datetime.fromisoformat(start_str)
            minutes_away = max(0, int((start_dt - now).total_seconds() / 60))
            content = f"{summary} starts in {minutes_away} minutes."
            _surfaced_event_ids.add(event_id)
            _surface_immediate(Finding(
                type="calendar_approaching",
                content=content,
                urgency="high",
                timing="immediate",
            ))
    except Exception as e:
        print(f"[sentinel] Calendar poll error: {e}")


def _check_deep_work_gap() -> None:
    """Queue a session_start finding when a 2h+ free block exists today (09:00–17:00).
    Fires at most once per calendar day."""
    global _deep_work_gap_date
    today = datetime.now().strftime("%Y-%m-%d")
    if _deep_work_gap_date == today:
        return
    try:
        from core.security.gmail_auth import get_calendar_service
        service = get_calendar_service()
        if service is None:
            return
        now_local = datetime.now().astimezone()
        day_start = now_local.replace(hour=9, minute=0, second=0, microsecond=0)
        day_end = now_local.replace(hour=17, minute=0, second=0, microsecond=0)
        search_from = max(now_local, day_start)
        if search_from >= day_end:
            return
        response = service.events().list(
            calendarId="primary",
            timeMin=search_from.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        ).execute()
        events = response.get("items", [])
        cursor = search_from
        for event in events:
            start_str = event.get("start", {}).get("dateTime", "")
            end_str = event.get("end", {}).get("dateTime", "")
            if not start_str or not end_str:
                continue
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)
            gap_hours = (start_dt - cursor).total_seconds() / 3600
            if gap_hours >= 2.0:
                _deep_work_gap_date = today
                push(Finding(
                    type="deep_work_gap",
                    content=f"You have a {int(gap_hours)}-hour gap "
                            f"({cursor.hour}:{cursor.minute:02d}–"
                            f"{start_dt.hour}:{start_dt.minute:02d}) — potential deep work window.",
                    urgency="low",
                    timing="session_start",
                ))
                return
            cursor = max(cursor, end_dt)
        gap_hours = (day_end - cursor).total_seconds() / 3600
        if gap_hours >= 2.0:
            _deep_work_gap_date = today
            push(Finding(
                type="deep_work_gap",
                content=f"You have a {int(gap_hours)}-hour gap "
                        f"({cursor.hour}:{cursor.minute:02d}–"
                        f"{day_end.hour}:{day_end.minute:02d}) — potential deep work window.",
                urgency="low",
                timing="session_start",
            ))
    except Exception as e:
        print(f"[sentinel] Deep work gap check error: {e}")


def _calendar_poll_loop() -> None:
    while not _shutdown.wait(CALENDAR_POLL_SECONDS):
        _check_calendar_approaching()
        _check_deep_work_gap()


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def start() -> None:
    """Start both daemon threads. Safe to call multiple times."""
    global _thread, _calendar_thread
    if _thread is not None and _thread.is_alive():
        return
    _shutdown.clear()
    _thread = threading.Thread(target=_sentinel_loop, daemon=True, name="sentinel")
    _thread.start()
    _calendar_thread = threading.Thread(target=_calendar_poll_loop, daemon=True, name="sentinel-calendar")
    _calendar_thread.start()
    print("[sentinel] Started — 30-min rules + 5-min calendar poll.")


def stop() -> None:
    _shutdown.set()


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()
