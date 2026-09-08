# tools/reminder_set/reminder_set_tool.py
# Sets a reminder by creating a Google Calendar event with a popup notification.
# write_gated — Aegon asks before creating. Google syncs the notification to all
# of Sir's devices (laptop, phone, TV) automatically.
# Reuses the Gmail Google token (calendar.events scope) via gmail_auth.

from datetime import datetime, timedelta

import dateparser
from googleapiclient.errors import HttpError

from tools.base_connector import BaseConnector
from core.security.gmail_auth import get_calendar_service
from core.reminders.reminder_watcher import REMINDER_MARKER_KEY, REMINDER_MARKER_VALUE

REMINDER_DURATION_MINUTES = 15  # calendar events need an end; the popup fires at start


def _parse_when(when: str) -> datetime | None:
    """Parse free-form time into a local tz-aware datetime. Future-biased."""
    parsed = dateparser.parse(
        when,
        settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": True},
    )
    if parsed is None:
        return None
    # If dateparser returned a naive datetime, attach the local timezone.
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def _format_clock(moment: datetime) -> str:
    """'6 PM' on the hour, else '6:30 PM'."""
    hour = moment.strftime("%I").lstrip("0") or "12"
    ampm = moment.strftime("%p")
    return f"{hour} {ampm}" if moment.minute == 0 else f"{hour}:{moment.strftime('%M')} {ampm}"


def _format_when(moment: datetime) -> str:
    """Human-friendly day + clock, e.g. 'today at 6 PM' / 'Saturday at 9 AM'."""
    today = datetime.now().astimezone().date()
    clock = _format_clock(moment)
    if moment.date() == today:
        return f"today at {clock}"
    if moment.date() == today + timedelta(days=1):
        return f"tomorrow at {clock}"
    return f"{moment.strftime('%A %d %B')} at {clock}"


class ReminderSetConnector(BaseConnector):
    name = "reminder_set"
    version = "1.0.0"
    description = "Sets a reminder via a Google Calendar event with a notification."
    permission_level = "write_gated"

    def validate(self, payload: dict) -> bool:
        return (
            isinstance(payload, dict)
            and bool(payload.get("message"))
            and bool(payload.get("when"))
        )

    def approval_prompt(self, payload: dict) -> str:
        """Rich preview shown before Sir approves."""
        message = payload.get("message", "")
        moment = _parse_when(payload.get("when", ""))
        if moment is None:
            return f"Set a reminder to {message}? I couldn't read the time, Sir."
        return f"Set a reminder: {message}, {_format_when(moment)}. Proceed, Sir?"

    def execute(self, payload: dict) -> dict:
        """Create the calendar event with a popup reminder. Returns a spoken line."""
        if not self.validate(payload):
            return {"status": "error", "output": "I need both what to remind and when, Sir."}

        message = payload["message"]
        moment = _parse_when(payload["when"])
        if moment is None:
            return {"status": "error", "output": f"I couldn't understand the time '{payload['when']}', Sir."}

        service = get_calendar_service()
        if service is None:
            return {"status": "error", "output": "The calendar isn't authorized yet, Sir."}

        start = moment
        end = moment + timedelta(minutes=REMINDER_DURATION_MINUTES)
        event = {
            "summary": message,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": 0}],
            },
            # Private marker: tells the watcher this is Aegon's to voice (Axiom 6).
            "extendedProperties": {"private": {REMINDER_MARKER_KEY: REMINDER_MARKER_VALUE}},
        }

        try:
            service.events().insert(calendarId="primary", body=event).execute()
        except HttpError as e:
            return {"status": "error", "output": f"Couldn't set the reminder: {e}"}

        return {"status": "success", "output": f"Reminder set: {message}, {_format_when(moment)}, Sir."}
