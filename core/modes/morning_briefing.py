# core/modes/morning_briefing.py
# Morning briefing — fires automatically at session start when
# active_mode == "morning". Speaks directly via speak().
#
# Data is gathered deterministically (weather, calendar, news), then handed to
# Groq once to phrase a single warm, natural, human-sounding briefing.
#
# Order: greeting -> weather -> calendar -> news. Empty sections are simply
# omitted from the data handed to the LLM. Targets < 60 seconds spoken.

import threading

from tools.weather.weather_tool import WeatherConnector
from tools.calendar_read.calendar_read_tool import CalendarReadConnector
from tools.news.news_tool import NewsConnector
from core.orchestration.llm_client import call_llm
from core.voice.speak import speak

_BRIEFING_SYSTEM_PROMPT = """You are Aegon, a personal assistant in the spirit of JARVIS — composed, warm, intelligent, lightly British in tone.

You are giving Sir his morning briefing. You will be handed raw facts (weather, calendar, news). Turn them into ONE short spoken briefing that sounds like a real person talking, not a list being read out.

Rules:
- Open with a natural good-morning greeting. Vary it; do not be robotic.
- Flow the sections together conversationally in this order: weather, then calendar, then news.
- Do NOT start every sentence with "Sir." Use his name at most once, naturally.
- If a section's data is missing, skip it silently — no "I have no data" filler.
- Be concise. Spoken in under 45 seconds. No markdown, no lists, no headings — just speech.
- Sound human: contractions, easy rhythm, a touch of warmth. Never stiff."""


def _safe(connector_cls, payload: dict) -> str:
    """Run a connector, return its spoken output, or empty string on any failure."""
    try:
        result = connector_cls().execute(payload)
        text = (result.get("output") or "").strip()
        low = text.lower()
        if not text or "unavailable" in low or "invalid" in low:
            return ""
        return text
    except Exception:
        return ""


def _gather() -> dict:
    """Collect the raw briefing data deterministically. No LLM here."""
    return {
        "weather": _safe(WeatherConnector, {}),
        "calendar": _safe(CalendarReadConnector, {"range": "today"}),
        "news": _safe(NewsConnector, {}),
    }


def build_briefing() -> str:
    """Gather data, then have Groq phrase one warm spoken briefing."""
    data = _gather()

    parts = []
    if data["weather"]:
        parts.append(f"Weather: {data['weather']}")
    if data["calendar"]:
        parts.append(f"Today's calendar: {data['calendar']}")
    if data["news"]:
        parts.append(f"News: {data['news']}")

    if not parts:
        return "Good morning, Sir. Nothing notable to report this morning."

    facts = "\n".join(parts)
    try:
        spoken = call_llm(
            system_prompt=_BRIEFING_SYSTEM_PROMPT,
            user_message=f"Here is this morning's data:\n\n{facts}\n\nGive Sir his briefing.",
            temperature=0.7,
        ).strip()
        if spoken:
            return spoken
    except Exception as e:
        print(f"[morning_briefing] LLM phrasing failed, falling back: {e}")

    # Fallback: plain readout if the LLM call fails.
    return "Good morning, Sir. " + " ".join(
        v for v in (data["weather"], data["calendar"], data["news"]) if v
    )


def deliver_briefing() -> None:
    """Build, print, and speak the morning briefing. Runs in a background thread.
    Printing makes the briefing visible in text mode and when TTS is unavailable."""
    try:
        text = build_briefing()
        print(f"Aegon (briefing): {text}\n")
        speak(text)
    except Exception as e:
        print(f"[morning_briefing] Failed: {e}")


def start_briefing_async() -> None:
    """Fire the briefing in a daemon thread so the voice loop is never blocked."""
    t = threading.Thread(target=deliver_briefing, daemon=True, name="morning-briefing")
    t.start()
