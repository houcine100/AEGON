# Run from project root in a terminal with the SPOTIFY_* env vars set:
#   python tests\test_spotify_auth.py
from core.security.spotify_auth import authorize_spotify, get_spotify_client
from core.security import token_store


token_store.delete_token("spotify")
authorize_spotify()
print("has token:", token_store.has_token("spotify"))
print("client ready:", get_spotify_client() is not None)