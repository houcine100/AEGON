# core/security/token_store.py
# Single shared store for OAuth tokens (Gmail, Spotify, etc.).
# Tokens are encrypted at rest with a key from the AEGON_TOKEN_KEY env var.
# Every app goes through this — no app stores tokens on its own.
#
# KEY BACKUP (F14) — two keys must be backed up separately from this folder:
#
#   AEGON_TOKEN_KEY        — Fernet key. Protects all OAuth tokens (Gmail, Spotify).
#                            Lose it → every connected service must be re-authorised.
#
#   AEGON_ENCRYPTION_KEY   — Fernet key. Protects session logs + fact-extraction data.
#                            Lose it → historical session logs become unreadable.
#
# Backup: run `python -m apps.backup_keys` — prints both keys for copying to a
# password manager. Re-run whenever a key is rotated. Never store keys in this repo.

import os
import json
from pathlib import Path
from cryptography.fernet import Fernet

# All tokens live here. This folder must stay out of any Git repo.
TOKENS_DIR = Path(__file__).resolve().parent / "tokens"


def _get_cipher() -> Fernet:
    key = os.environ.get("AEGON_TOKEN_KEY")
    if not key:
        raise RuntimeError(
            "AEGON_TOKEN_KEY is not set. Generate one with Fernet.generate_key() "
            "and set it as an environment variable."
        )
    return Fernet(key.encode())


def _token_path(service: str) -> Path:
    # Keep service names to simple identifiers — guard against path tricks.
    safe = "".join(c for c in service if c.isalnum() or c in ("_", "-"))
    return TOKENS_DIR / f"{safe}.token"


def save_token(service: str, data: dict) -> None:
    """Encrypt and store a service's token data."""
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    blob = _get_cipher().encrypt(json.dumps(data).encode())
    with open(_token_path(service), "wb") as f:
        f.write(blob)


def load_token(service: str) -> dict | None:
    """Return a service's token data, or None if not connected / unreadable."""
    path = _token_path(service)
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            blob = f.read()
        return json.loads(_get_cipher().decrypt(blob).decode())
    except Exception as e:
        print(f"[token_store] Failed to load token for {service}: {e}")
        return None


def delete_token(service: str) -> bool:
    """Remove a service's token (disconnect it). True if one was removed."""
    path = _token_path(service)
    if path.exists():
        path.unlink()
        return True
    return False


def has_token(service: str) -> bool:
    """True if a token exists for this service."""
    return _token_path(service).exists()