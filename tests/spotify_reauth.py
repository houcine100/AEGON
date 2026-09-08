# Forces a clean re-auth and prints the scopes Spotify actually granted.
from core.security import token_store
from core.security.spotify_auth import authorize_spotify

print("deleted:", token_store.delete_token("spotify"))
authorize_spotify()
t = token_store.load_token("spotify")
print("granted scope:", t.get("scope") if t else "NONE")