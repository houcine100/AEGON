# core/reminders/reminder_watcher.py
# Background thread: polls Google Calendar every 60 s and speaks popup reminders aloud.
# Fires TTS when an event starts within FIRE_WINDOW_SECONDS of now.
# Started from aegon_orchestrator.start(). Stops when the process exits (daemon thread).

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from core.security.gmail_auth import get_calendar_service
from core.voice.speak import speak

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 60
FIRE_WINDOW_SECONDS = 90  # fire if event starts within this window ahead of now

# Security marker (Axiom 6). The watcher ONLY voices events Aegon created, identified
# by this PRIVATE extended property. Private props live solely on Sir's calendar copy —
# an external invite cannot forge them. Forging requires write access to the primary
# calendar, i.e. a full Google-account breach. reminder_set stamps every event with this.
REMINDER_MARKER_KEY = "aegon_reminder"
REMINDER_MARKER_VALUE = "1"

_fired: set[str] = set()  # "<event_id>:<YYYY-MM-DD>" — avoids double-firing per day
_lock = threading.Lock()


def _check_reminders() -> None:
    """Fetch upcoming events and fire TTS for any starting within the fire window."""
    service = get_calendar_service()
    if service is None:
        return

    now = datetime.now(timezone.utc)
    window_end = now + timedelta(seconds=FIRE_WINDOW_SECONDS)

    try:
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=window_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                # Server-side security filter: only events Aegon stamped (Axiom 6).
                privateExtendedProperty=f"{REMINDER_MARKER_KEY}={REMINDER_MARKER_VALUE}",
            )
            .execute()
        )
    except Exception as e:
        logger.warning(f"[reminder_watcher] Calendar poll failed: {e}")
        return

    for event in result.get("items", []):
        # Defense in depth: re-verify the private marker client-side. Fail closed.
        private_props = event.get("extendedProperties", {}).get("private", {})
        if private_props.get(REMINDER_MARKER_KEY) != REMINDER_MARKER_VALUE:
            continue

        event_id = event.get("id", "")
        start_str = event.get("start", {}).get("dateTime", "")
        if not start_str:
            continue  # all-day event — skip

        # Key: event_id + calendar date — one fire per day per event
        fire_key = f"{event_id}:{start_str[:10]}"
        with _lock:
            if fire_key in _fired:
                continue
            _fired.add(fire_key)

        summary = event.get("summary", "Reminder")
        logger.info(f"[reminder_watcher] Firing: {summary}")
        speak(f"Reminder, Sir: {summary}")


def _watcher_loop() -> None:
    """Poll calendar every POLL_INTERVAL_SECONDS, indefinitely."""
    while True:
        try:
            _check_reminders()
        except Exception as e:
            logger.error(f"[reminder_watcher] Unexpected error: {e}")
        time.sleep(POLL_INTERVAL_SECONDS)


def start_watcher() -> threading.Thread:
    """Start the reminder watcher as a daemon thread. Safe to call once at startup."""
    thread = threading.Thread(
        target=_watcher_loop,
        daemon=True,
        name="reminder-watcher",
    )
    thread.start()
    logger.info("[reminder_watcher] Reminder watcher started.")
    return thread
