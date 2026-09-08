# tools/spotify_control/spotify_control_tool.py
# Spotify transport control (pause/resume/skip/previous). ALWAYS GATED — asks before acting.
# Native on spotipy, uses the encrypted token via spotify_auth.

from tools.base_connector import BaseConnector
from core.security.spotify_auth import get_spotify_client, describe_spotify_error

_ACTIONS = {
    "pause": "pause", "stop": "pause",
    "resume": "resume", "play": "resume", "unpause": "resume",
    "next": "next", "skip": "next",
    "previous": "previous", "back": "previous", "prev": "previous",
}
_VERB = {
    "pause": "pause Spotify",
    "resume": "resume Spotify playback",
    "next": "skip to the next track",
    "previous": "go to the previous track",
}


class SpotifyControlConnector(BaseConnector):
    name = "spotify_control"
    version = "1.0.0"
    description = "Controls Spotify playback: pause, resume, skip, previous. Always asks first."
    permission_level = "always_gated"

    def _norm(self, payload: dict):
        return _ACTIONS.get(str(payload.get("action", "")).strip().lower())

    def validate(self, payload: dict) -> bool:
        return isinstance(payload, dict) and self._norm(payload) is not None

    def approval_prompt(self, payload: dict) -> str:
        return f"Shall I {_VERB.get(self._norm(payload), 'control Spotify')}, Sir?"

    def execute(self, payload: dict) -> dict:
        action = self._norm(payload)
        if action is None:
            return {"status": "error", "output": "I did not understand that playback command, Sir."}
        client = get_spotify_client()
        if client is None:
            return {"status": "error", "output": "Spotify is not connected, Sir."}
        try:
            if action == "pause":
                client.pause_playback(); done = "Paused."
            elif action == "resume":
                client.start_playback()
                done = "Resumed."
                try:
                    cur = client.current_playback()
                    if cur and cur.get("item"):
                        it = cur["item"]
                        who = ", ".join(a.get("name", "") for a in it.get("artists", []))
                        done = f"Resumed — now playing {it.get('name','')} by {who}."
                except Exception:
                    pass
            elif action == "next":
                client.next_track(); done = "Skipped to the next track."
            elif action == "previous":
                client.previous_track(); done = "Went to the previous track."
            else:
                return {"status": "error", "output": "Unsupported action, Sir."}
        except Exception as e:
            m = str(e).upper()
            if "NO_ACTIVE_DEVICE" in m or "NO ACTIVE DEVICE" in m or "404" in m:
                return {"status": "error", "output": "No active Spotify device, Sir. Open Spotify on a device and try again."}
            return {"status": "error", "output": describe_spotify_error(e, "Spotify control")}
        return {"status": "success", "output": done}