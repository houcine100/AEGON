# tools/calendar_read/calendar_read_tool.py
# Reads Sir's Google Calendar (read-only, no approval).
# Reuses the Gmail Google token (calendar.readonly scope) via gmail_auth.
# response_style is verbatim — the tool speaks its own short line.

from datetime import datetime, timedelta, time

from googleapiclient.errors import HttpError

from tools.base_connector import BaseConnector
from core.security.gmail_auth import get_calendar_service

VALID_RANGES = ("today", "tomorrow", "week")
MAX_RESULTS = 25


def _normalise_range(value) -> str:
    """Map free-form input to one of today / tomorrow / week."""
    text = (value or "").strip().lower()
    if "tomorrow" in text:
        return "tomorrow"
    if "week" in text:
        return "week"
    return "today"


def _bounds(range_key: str):
    """Return (timeMin_iso, timeMax_iso, label) for the chosen window, local time."""
    now = datetime.now().astimezone()
    tz = now.tzinfo
    today = now.date()
    if range_key == "tomorrow":
        start_date, end_date, label = today + timedelta(days=1), today + timedelta(days=2), "tomorrow"
    elif range_key == "week":
        start_date, end_date, label = today, today + timedelta(days=7), "this week"
    else:
        start_date, end_date, label = today, today + timedelta(days=1), "today"
    start = datetime.combine(start_date, time.min, tzinfo=tz)
    end = datetime.combine(end_date, time.min, tzinfo=tz)
    return start.isoformat(), end.isoformat(), label


def _format_clock(moment: datetime) -> str:
    """'9 AM' on the hour, else '9:30 AM'."""
    hour = moment.strftime("%I").lstrip("0") or "12"
    ampm = moment.strftime("%p")
    return f"{hour} {ampm}" if moment.minute == 0 else f"{hour}:{moment.strftime('%M')} {ampm}"


def _format_event(event: dict, range_key: str) -> str:
    summary = event.get("summary", "(no title)")
    start = event.get("start", {})
    if "dateTime" in start:
        moment = datetime.fromisoformat(start["dateTime"])
        when = _format_clock(moment)
        if range_key == "week":
            when = f"{moment.strftime('%A')} {when}"
        return f"{when} {summary}"
    # All-day event (start.date).
    if range_key == "week" and start.get("date"):
        day = datetime.fromisoformat(start["date"])
        return f"{day.strftime('%A')} (all day) {summary}"
    return f"{summary} (all day)"


class CalendarReadConnector(BaseConnector):
    name = "calendar_read"
    version = "1.0.0"
    description = "Reads Sir's Google Calendar events (read-only)."
    permission_level = "read_only"

    def validate(self, payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        value = payload.get("range")
        return value is None or isinstance(value, str)

    def execute(self, payload: dict) -> dict:
        """List events for today / tomorrow / this week. Returns a spoken line."""
        if not self.validate(payload):
            return {"status": "error", "output": "Invalid calendar request."}

        service = get_calendar_service()
        if service is None:
            return {"status": "error", "output": "The calendar isn't authorized yet, Sir."}

        range_key = _normalise_range(payload.get("range"))
        time_min, time_max, label = _bounds(range_key)

        try:
            response = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=MAX_RESULTS,
                )
                .execute()
            )
        except HttpError as e:
            return {"status": "error", "output": f"Calendar request failed: {e}"}

        events = response.get("items", [])
        if not events:
            return {"status": "success", "output": f"Nothing on your calendar {label}, Sir."}

        pieces = [_format_event(ev, range_key) for ev in events]
        noun = "event" if len(pieces) == 1 else "events"
        spoken = f"{len(pieces)} {noun} {label}, Sir: " + "; ".join(pieces) + "."
        return {"status": "success", "output": spoken}
