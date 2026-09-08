# tools/spotify_search/spotify_search_tool.py
# Native Spotify track search on spotipy. Read-only, no approval.
# Uses the encrypted token via spotify_auth (token_store), like Gmail.

from tools.base_connector import BaseConnector
from core.security.spotify_auth import get_spotify_client, describe_spotify_error


class SpotifySearchConnector(BaseConnector):
    name = "spotify_search"
    version = "1.0.0"
    description = "Searches Spotify for tracks (read-only)."
    permission_level = "read_only"

    def validate(self, payload: dict) -> bool:
        return isinstance(payload, dict) and bool(payload.get("query"))

    def execute(self, payload: dict) -> dict:
        client = get_spotify_client()
        if client is None:
            return {"status": "error", "output": "Spotify is not connected, Sir."}
        try:
            results = client.search(q=payload["query"], type="track", limit=8)
        except Exception as e:
            return {"status": "error", "output": describe_spotify_error(e, "Spotify search")}
        items = (results.get("tracks") or {}).get("items", [])
        if not items:
            return {"status": "no_results", "output": []}
        shaped = []
        for t in items:
            artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
            album = (t.get("album") or {}).get("name", "")
            shaped.append({
                "title": f"{t.get('name', '')} — {artists}",
                "href": (t.get("external_urls") or {}).get("spotify", ""),
                "body": f"Album: {album}" if album else "",
            })
        return {"status": "success", "output": shaped}