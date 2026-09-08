# Shows the RAW tracks field Spotify returns for a few of your playlists.
from core.security.spotify_auth import get_spotify_client

c = get_spotify_client()
res = c.current_user_playlists(limit=5)
for p in res.get("items", []):
    if p:
        print(repr(p.get("name")), "| tracks field:", p.get("tracks"))