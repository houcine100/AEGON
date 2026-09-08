# tools/weather/weather_tool.py
# Weather connector. READ ONLY — no approval needed.
# Fetches current weather + today's forecast from wttr.in, then phrases it as
# one short spoken line (response_style: verbatim — the tool speaks for itself).
# _get_weather_data returns the structured fields, reusable by morning mode later.

from urllib.parse import quote
import requests

from tools.base_connector import BaseConnector

WTTR_URL = "https://wttr.in/{location}?format=j1"
# wttr.in's own place lookup is unreliable: "Tokyo" resolved to Shikinejima (~150km
# offshore, but administratively Tokyo Metropolis) and "Tunis" to Kebili (~340km away).
# That returned genuinely wrong weather, not just an odd label. So named places are
# geocoded here first and wttr.in is queried by coordinates.
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
REQUEST_TIMEOUT = 10  # seconds


def _geocode(location: str) -> tuple:
    """Resolve a place name to (query_string, canonical_name). Falls back to the raw
    name if lookup fails, so a geocoder outage degrades rather than breaks."""
    try:
        response = requests.get(
            GEOCODE_URL,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return location, ""
        results = (response.json() or {}).get("results") or []
        if not results:
            return location, ""
        hit = results[0]
        lat, lon = hit.get("latitude"), hit.get("longitude")
        if lat is None or lon is None:
            return location, ""
        # Country-level results repeat the same string in both fields (e.g. "Tunisia"/"Tunisia") —
        # drop the duplicate so the spoken line doesn't say "Tunisia, Tunisia".
        parts = [hit.get("name"), hit.get("country")]
        name = ", ".join(dict.fromkeys(p for p in parts if p))
        return f"{lat},{lon}", name
    except requests.RequestException:
        return location, ""


def _safe_get(items, index: int = 0) -> dict:
    """Return items[index] if the list is non-empty, else {}."""
    if isinstance(items, list) and len(items) > index:
        return items[index]
    return {}


def _nested_value(field) -> str:
    """wttr.in wraps many fields as [{'value': '...'}]. Pull the first value."""
    first = _safe_get(field)
    return first.get("value", "") if isinstance(first, dict) else ""


def _to_int(value, default=None):
    """wttr.in returns numbers as strings. Convert defensively."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_weather_data(location: str) -> tuple:
    """Fetch + parse wttr.in. Returns (data, None) on success, (None, error) on failure.
    data is the structured weather — reusable by morning mode.

    A named location is geocoded first and queried by coordinates. An empty location
    keeps wttr.in's IP-based detection, which is what Sir wants for "the weather".
    """
    canonical_name = ""
    if location:
        location, canonical_name = _geocode(location)
    url = WTTR_URL.format(location=quote(location))
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "aegon-weather/1.0"},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        return None, f"Weather request failed: {e}"

    if response.status_code != 200:
        return None, f"Weather service returned {response.status_code}."

    try:
        raw = response.json()
    except ValueError:
        return None, "Weather service returned no readable data."

    current = _safe_get(raw.get("current_condition"))
    if not current:
        return None, "No current weather available."

    area = _safe_get(raw.get("nearest_area"))
    place_name = _nested_value(area.get("areaName"))
    country = _nested_value(area.get("country"))
    today = _safe_get(raw.get("weather"))

    data = {
        # Prefer the geocoded city Sir actually named. wttr.in's nearest_area is the
        # closest weather STATION ("Saint-Merri" for Paris), which is not what he asked for.
        "location": canonical_name
        or ", ".join(p for p in (place_name, country) if p)
        or "your area",
        "temp_c": _to_int(current.get("temp_C")),
        "feels_like_c": _to_int(current.get("FeelsLikeC")),
        "description": _nested_value(current.get("weatherDesc")),
        "humidity_pct": _to_int(current.get("humidity")),
        "wind_kmph": _to_int(current.get("windspeedKmph")),
        "wind_dir": current.get("winddir16Point", ""),
        "high_c": _to_int(today.get("maxtempC")),
        "low_c": _to_int(today.get("mintempC")),
        "date": today.get("date", ""),
    }
    return data, None


def _format_spoken(data: dict) -> str:
    """Compose one short, voice-friendly line from the structured weather."""
    location = data["location"]
    temp = data["temp_c"]
    # wttr.in pads descriptions ("Clear "), which becomes "clear , feeling like" when spoken.
    desc = data["description"].strip().lower() if data["description"] else ""

    if temp is not None and desc:
        sentence = f"Right now in {location} it's {temp} degrees and {desc}"
    elif temp is not None:
        sentence = f"Right now in {location} it's {temp} degrees"
    elif desc:
        sentence = f"Right now in {location} it's {desc}"
    else:
        sentence = f"I have the weather for {location}"

    if data["feels_like_c"] is not None:
        sentence += f", feeling like {data['feels_like_c']}"
    sentence += "."

    if data["high_c"] is not None and data["low_c"] is not None:
        sentence += f" Today's high is {data['high_c']}, low {data['low_c']}."

    return sentence


class WeatherConnector(BaseConnector):
    name = "weather"
    version = "1.0.0"
    description = "Gets current weather and today's forecast from wttr.in."
    permission_level = "read_only"

    def validate(self, payload: dict) -> bool:
        """Location is optional. If present, it must be a string."""
        if not isinstance(payload, dict):
            return False
        location = payload.get("location")
        return location is None or isinstance(location, str)

    def execute(self, payload: dict) -> dict:
        """
        Fetch the weather and phrase it. Location is optional (empty = detect by IP).
        response_style is verbatim, so output is the spoken line itself.
        On success: {"status": "success", "output": "<one or two sentences>"}
        On failure: {"status": "error", "output": "<message>"}
        """
        if not self.validate(payload):
            return {"status": "error", "output": "Invalid location."}

        location = (payload.get("location") or "").strip()
        data, error = _get_weather_data(location)
        if error:
            return {"status": "error", "output": error}

        return {"status": "success", "output": _format_spoken(data)}
