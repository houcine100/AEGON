from tools.base_connector import BaseConnector
from core.security.spotify_auth import get_spotify_client, ensure_device, describe_spotify_error


class SpotifyPlayPlaylistConnector(BaseConnector):
    name = "spotify_play_playlist"
    version = "1.0.0"
    description = "Plays one of Sir's playlists by name. Always asks first."
    permission_level = "always_gated"

    def validate(self, payload: dict) -> bool:
        return isinstance(payload, dict) and bool(payload.get("name"))

    def approval_prompt(self, payload: dict) -> str:
        return f"Shall I play your '{payload.get('name', '')}' playlist on Spotify, Sir?"

    def _all_playlists(self, client):
        out, res = [], client.current_user_playlists(limit=50)
        while res:
            out.extend(p for p in res.get("items", []) if p)
            res = client.next(res) if res.get("next") else None
        return out

    def _find(self, client, name):
        target = name.strip().lower()
        pls = self._all_playlists(client)
        for p in pls:
            if p.get("name", "").strip().lower() == target:
                return p
        for p in pls:
            if target in p.get("name", "").strip().lower():
                return p
        return None

    def execute(self, payload: dict) -> dict:
        client = get_spotify_client()
        if client is None:
            return {"status": "error", "output": "Spotify is not connected, Sir."}
        try:
            pl = self._find(client, payload["name"])
            if not pl:
                return {"status": "error", "output": f"I could not find a playlist named '{payload['name']}', Sir."}
            device = ensure_device(client, launch_uri=pl["uri"])
            if device is None:
                return {"status": "error", "output": "Could not open Spotify, Sir. Is the desktop app installed?"}
            client.start_playback(device_id=device, context_uri=pl["uri"])
            return {"status": "success", "output": f"Now playing your '{pl.get('name', '')}' playlist."}
        except Exception as e:
            m = str(e).upper()
            if "NO_ACTIVE_DEVICE" in m or "NO ACTIVE DEVICE" in m or "404" in m:
                return {"status": "error", "output": "No active Spotify device, Sir. Open Spotify and try again."}
            return {"status": "error", "output": describe_spotify_error(e, "Spotify play")}