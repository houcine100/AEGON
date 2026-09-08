# tools/morning_mode/morning_mode_tool.py
# Morning briefing: time + weather + today's calendar + top news.
# Calls the three other connectors in parallel via ThreadPoolExecutor.
# read_only, verbatim — no approval needed.

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from tools.base_connector import BaseConnector
from tools.weather.weather_tool import WeatherConnector
from tools.calendar_read.calendar_read_tool import CalendarReadConnector
from tools.news.news_tool import NewsConnector


def _time_line() -> str:
    """Current local time as a short spoken fragment."""
    now = datetime.now().astimezone()
    clock = now.strftime("%I:%M %p").lstrip("0")
    return f"It's {clock}."


class MorningModeConnector(BaseConnector):
    name = "morning_mode"
    version = "1.0.0"
    description = "Morning briefing: time, weather, calendar, top news."
    permission_level = "read_only"

    def validate(self, payload: dict) -> bool:
        return isinstance(payload, dict)

    def execute(self, payload: dict) -> dict:
        # Time is instant — no network call needed.
        time_line = _time_line()

        # Weather, calendar, news run in parallel.
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_weather  = pool.submit(WeatherConnector().execute, {})
            f_calendar = pool.submit(CalendarReadConnector().execute, {"range": "today"})
            f_news     = pool.submit(NewsConnector().execute, {})

            weather_out  = f_weather.result().get("output",  "Weather unavailable.")
            calendar_out = f_calendar.result().get("output", "Calendar unavailable.")
            news_out     = f_news.result().get("output",    "No headlines available.")

        # Strip trailing periods from weather/calendar so the join reads cleanly.
        weather_line  = weather_out.rstrip(".")
        calendar_line = calendar_out.rstrip(".")

        spoken = (
            f"Good morning, Sir. {time_line} "
            f"{weather_line}. "
            f"{calendar_line}. "
            f"{news_out}"
        )
        return {"status": "success", "output": spoken}
