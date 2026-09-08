# tools/clock/clock_tool.py
# Aegon's clock — proxies the official mcp-server-time over stdio.
# Read-only, no approval. Proves the MCP bridge end-to-end.
# The time server REQUIRES a timezone, so if Sir names none we resolve it
# automatically from the machine's IP (same idea as the weather connector).
# The server replies in JSON; we phrase it as a short spoken line.

from datetime import datetime
import json
import requests

from tools.mcp_connector import MCPConnector

IPAPI_URL = "http://ip-api.com/json/?fields=timezone"
REQUEST_TIMEOUT = 5  # seconds


def _resolve_timezone() -> str:
    """Best-effort local IANA timezone. Try IP geolocation, then fall back."""
    try:
        response = requests.get(IPAPI_URL, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            tz = response.json().get("timezone")
            if tz:
                return tz
    except requests.RequestException:
        pass
    # Fallback: whatever the system reports, else UTC.
    local = datetime.now().astimezone().tzinfo
    return str(local) if local else "Etc/UTC"


def _format_time(raw: str, aspect: str) -> str:
    """Turn the server's JSON into a short spoken line.
    aspect: 'time' -> clock only, 'date' -> day only, else both."""
    try:
        data = json.loads(raw)
        moment = datetime.fromisoformat(data["datetime"])
    except (ValueError, KeyError, TypeError):
        return raw  # fallback: never hide the answer

    clock = moment.strftime("%I:%M %p").lstrip("0").replace("AM", "am").replace("PM", "pm")
    day = moment.strftime("%A %d %B %Y")

    if aspect == "time":
        return f"It's {clock}."
    if aspect == "date":
        return f"It's {day}."
    return f"It's {clock} on {day}."


class ClockConnector(MCPConnector):
    name = "clock"
    version = "1.0.0"
    description = "Tells the current time, via the official MCP time server."
    permission_level = "read_only"

    mcp_command = "python"
    mcp_args = ["-m", "mcp_server_time"]
    mcp_tool_name = "get_current_time"

    def execute(self, payload: dict) -> dict:
        """Resolve the timezone if absent, call the server, then phrase the reply.
        'aspect' is Aegon's own hint (time/date/both) — not a server argument."""
        payload = dict(payload or {})
        aspect = (payload.pop("aspect", "") or "").lower()
        if not payload.get("timezone"):
            payload["timezone"] = _resolve_timezone()

        result = super().execute(payload)
        if result.get("status") != "success":
            return result
        return {"status": "success", "output": _format_time(result.get("output", ""), aspect)}
