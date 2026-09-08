# core/modes/morning_mode_runner.py
# Morning briefing runner — executes when morning mode is activated externally.
# NOT a tool. Lives in core/modes/ and calls connectors directly.
#
# Current bundle: time + weather + calendar (today) + news.
# Future slots (add here when hardware exists):
#   - CurtainsConnector.execute({}) — always_gated
#   - CoffeeMachineConnector.execute({}) — always_gated

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from tools.weather.weather_tool import WeatherConnector
from tools.calendar_read.calendar_read_tool import CalendarReadConnector
from tools.news.news_tool import NewsConnector


def _time_line() -> str:
    """Current local time as a short spoken fragment. No network call."""
    now = datetime.now().astimezone()
    clock = now.strftime("%I:%M %p").lstrip("0")
    return f"It's {clock}."


def run_briefing() -> str:
    """
    Execute the full morning briefing.
    Weather, calendar, and news run in parallel.
    Returns a single spoken string ready for TTS.
    """
    time_line = _time_line()

    with ThreadPoolExecutor(max_workers=3) as pool:
        f_weather  = pool.submit(WeatherConnector().execute, {})
        f_calendar = pool.submit(CalendarReadConnector().execute, {"range": "today"})
        f_news     = pool.submit(NewsConnector().execute, {})

        weather_out  = f_weather.result().get("output", "Weather unavailable.")
        calendar_out = f_calendar.result().get("output", "Calendar unavailable.")
        news_out     = f_news.result().get("output",    "No headlines available.")

    # Strip trailing periods so the joined sentence reads cleanly.
    weather_line  = weather_out.rstrip(".")
    calendar_line = calendar_out.rstrip(".")

    return (
        f"Good morning, Sir. {time_line} "
        f"{weather_line}. "
        f"{calendar_line}. "
        f"{news_out}"
    )
