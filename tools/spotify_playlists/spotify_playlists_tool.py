from tools.base_connector import BaseConnector
from core.security.spotify_auth import get_spotify_client, describe_spotify_error


class SpotifyPlaylistsConnector(BaseConnector):
    name = "spotify_playlists"
    version = "1.0.0"
    description = "Lists Sir's own Spotify playlists (read-only)."
    permission_level = "read_only"

    def validate(self, payload: dict) -> bool:
        return isinstance(payload, dict)

    def execute(self, payload: dict) -> dict:
        client = get_spotify_client()
        if client is None:
            return {"status": "error", "output": "Spotify is not connected, Sir."}
        try:
            res = client.current_user_playlists(limit=50)
            items = [p for p in res.get("items", []) if p]
        except Exception as e:
            return {"status": "error", "output": describe_spotify_error(e, "Reading playlists")}
        if not items:
            return {"status": "no_results", "output": []}
        shaped = []
        for p in items:
            shaped.append({
                "title": p.get("name", ""),
                "href": (p.get("external_urls") or {}).get("spotify", ""),
                "body": "",
            })
        return {"status": "success", "output": shaped}