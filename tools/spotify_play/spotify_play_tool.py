# tools/spotify_play/spotify_play_tool.py
# Play a specific track by name on Spotify. ALWAYS GATED. Needs an active device.
from tools.base_connector import BaseConnector
from core.security.spotify_auth import get_spotify_client, ensure_device, describe_spotify_error


class SpotifyPlayConnector(BaseConnector):
    name = "spotify_play"
    version = "1.0.0"
    description = "Plays a specific named song on Spotify. Always asks first."
    permission_level = "always_gated"

    def validate(self, payload: dict) -> bool:
        return isinstance(payload, dict) and bool(payload.get("query"))

    def approval_prompt(self, payload: dict) -> str:
        return f"Shall I play '{payload.get('query', '')}' on Spotify, Sir?"

    def execute(self, payload: dict) -> dict:
        client = get_spotify_client()
        if client is None:
            return {"status": "error", "output": "Spotify is not connected, Sir."}
        try:
            res = client.search(q=payload["query"], type="track", limit=1)
            items = (res.get("tracks") or {}).get("items", [])
            if not items:
                return {"status": "no_results", "output": []}
            track = items[0]
            artists = ", ".join(a.get("name", "") for a in track.get("artists", []))
            device = ensure_device(client, launch_uri=track["uri"])
            if device is None:
                return {"status": "error", "output": "Could not open Spotify, Sir. Is the desktop app installed?"}
            client.start_playback(device_id=device, uris=[track["uri"]])
            return {"status": "success", "output": f"Now playing {track.get('name','')} by {artists}."}
        except Exception as e:
            m = str(e).upper()
            if "NO_ACTIVE_DEVICE" in m or "NO ACTIVE DEVICE" in m or "404" in m:
                return {"status": "error", "output": "No active Spotify device, Sir. Open Spotify and try again."}
            return {"status": "error", "output": describe_spotify_error(e, "Spotify play")}