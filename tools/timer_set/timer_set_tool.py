# tools/timer_set/timer_set_tool.py
# Ephemeral timer: speaks a title aloud after a short delay. In-memory only —
# nothing is written to Calendar, and it is lost on restart. That is acceptable:
# timers are short fuses set while Aegon is running. For durable, dated reminders
# that must sync across devices, use reminder_set (Google Calendar) instead.
#
# read_only: speaking is not a real-world action (Axiom 1), so no approval gate.

import threading
from datetime import datetime

import dateparser

from tools.base_connector import BaseConnector
from core.voice.speak import speak

MAX_TIMER_SECONDS = 24 * 60 * 60  # refuse long fuses — those belong in the calendar


def _seconds_until(when: str) -> float | None:
    """Parse a relative fuse into seconds from now. None if unreadable or in the past."""
    parsed = dateparser.parse(
        when,
        settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": True},
    )
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    delta = (parsed - datetime.now().astimezone()).total_seconds()
    return delta if delta > 0 else None


def _format_delay(seconds: float) -> str:
    """'5 minutes' / '1 hour 5 minutes' / '30 seconds'."""
    total = int(round(seconds))
    if total < 60:
        return f"{total} second{'s' if total != 1 else ''}"
    minutes = total // 60
    hours, mins = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if mins:
        parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
    return " ".join(parts) if parts else "a moment"


class TimerSetConnector(BaseConnector):
    name = "timer_set"
    version = "1.0.0"
    description = "Sets a short in-memory timer that speaks aloud when it fires."
    permission_level = "read_only"

    def validate(self, payload: dict) -> bool:
        return (
            isinstance(payload, dict)
            and bool(payload.get("message"))
            and bool(payload.get("when"))
        )

    def execute(self, payload: dict) -> dict:
        """Start a daemon timer that speaks the message at the fuse. Returns a spoken line."""
        if not self.validate(payload):
            return {"status": "error", "output": "I need both what to remind and when, Sir."}

        message = payload["message"]
        seconds = _seconds_until(payload["when"])
        if seconds is None:
            return {"status": "error", "output": f"I couldn't read the time '{payload['when']}', Sir."}
        if seconds > MAX_TIMER_SECONDS:
            return {
                "status": "error",
                "output": "That's a long way off, Sir — set it as a calendar reminder instead.",
            }

        timer = threading.Timer(seconds, speak, args=(f"Reminder, Sir: {message}",))
        timer.daemon = True
        timer.start()

        return {"status": "success", "output": f"Timer set: {message}, in {_format_delay(seconds)}, Sir."}
