# core/security/spotify_auth.py
# Spotify OAuth: one-time authorization + a self-refreshing client.
# Token is stored ENCRYPTED via token_store (service "spotify"), NOT spotipy's .cache file.
# App credentials come from env vars. Read-only scopes for now.

import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheHandler
from core.security import token_store


SERVICE_NAME = "spotify"

# Read-only to start. Control scope (user-modify-playback-state) is added later,
# when we build play/pause — so the stored token cannot touch playback until then.
SCOPES = (
    "user-read-playback-state "
    "user-read-currently-playing "
    "user-read-private "
    "user-library-read "
    "user-modify-playback-state "
    "playlist-read-private "
    "playlist-read-collaborative"
)


class _TokenStoreCacheHandler(CacheHandler):
    """Routes spotipy's token cache through Aegon's encrypted token_store."""

    def get_cached_token(self):
        return token_store.load_token(SERVICE_NAME)

    def save_token_to_cache(self, token_info):
        token_store.save_token(SERVICE_NAME, token_info)


def _auth_manager() -> SpotifyOAuth:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI")
    if not (client_id and client_secret and redirect_uri):
        raise RuntimeError(
            "SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and SPOTIFY_REDIRECT_URI "
            "must all be set as environment variables."
        )
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPES,
        cache_handler=_TokenStoreCacheHandler(),
        open_browser=True,
    )


def authorize_spotify() -> None:
    """One-time: open the browser, log in, approve. Token saved encrypted via token_store."""
    sp = spotipy.Spotify(auth_manager=_auth_manager())
    me = sp.current_user()  # forces the OAuth flow if needed; saves the token via the handler
    print(f"Spotify authorized for {me.get('display_name') or me.get('id')} — token saved (encrypted).")


def get_spotify_client() -> spotipy.Spotify | None:
    """Return a ready, self-refreshing Spotify client, or None if not authorized yet."""
    if not token_store.has_token(SERVICE_NAME):
        return None
    return spotipy.Spotify(auth_manager=_auth_manager())

def describe_spotify_error(e: Exception, action: str) -> str:
    """One spoken-quality sentence for a failed Spotify call.

    spotipy already retries 429s itself (3 attempts, honouring Retry-After — see
    its default_retry_codes). It only raises 429 once those are exhausted, so a
    429 reaching here means sustained rate limiting, not a single throttled call.
    Without this, the raw exception ("http status: 429, code:-1 - /v1/search:
    Max Retries") would be read aloud verbatim.
    """
    status = getattr(e, "http_status", None)
    if status == 429:
        return "Spotify is rate-limiting me, Sir. Try again in a moment."
    if status in (401, 403):
        return "Spotify refused the request, Sir — the authorisation may need renewing."
    if status == 404:
        return "Spotify could not find that, Sir."
    return f"{action} failed, Sir."


def pick_device(client):
    """Pick a device to play on: the active one, else any open one, else None.
    Lets playback start even when nothing is currently playing — as long as Spotify
    is OPEN somewhere. If Spotify is fully closed, returns None (can't launch it remotely)."""
    try:
        devices = (client.devices() or {}).get("devices", [])
    except Exception:
        return None
    if not devices:
        return None
    for d in devices:
        if d.get("is_active"):
            return d.get("id")
    return devices[0].get("id")

def launch_in_app(uri: str) -> bool:
    """Open a spotify: URI with the local desktop app (Windows). NARROW: only spotify: URIs —
    not a general app launcher. Can open Spotify when it's fully closed, which the API cannot."""
    if not isinstance(uri, str) or not uri.startswith("spotify:"):
        return False
    try:
        import os
        os.startfile(uri)
        return True
    except Exception:
        return False


def ensure_device(client, launch_uri: str = "spotify:", timeout: int = 8):
    """Return a playable device id. If none is open, launch Spotify (via launch_uri) and wait
    for it to register. Returns None only if Spotify can't be opened (e.g. not installed)."""
    import time
    dev = pick_device(client)
    if dev:
        return dev
    if not launch_in_app(launch_uri):
        return None
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1)
        dev = pick_device(client)
        if dev:
            return dev
    return None