# core/memory/vault_sync.py
# Obsidian → Tier-3 memory sync. Runs at session start only.
#
# Axiom 2 compliance: vault content is NEVER sent to an external API.
# store_fact() uses a local SentenceTransformer for dedup — zero network calls.
#
# Sync cycle: once per session start. Last-sync timestamp persisted in
# core/memory/.vault_sync_ts so repeated restarts don't re-ingest unchanged notes.
#
# PRIVACY (Sir's rule, 2026-06-20): the default sync stores a note's IDENTITY only —
# its title, plus an optional "purpose:" line taken from the note's YAML frontmatter.
# The note BODY is NEVER read into a fact. Content stays on disk, readable on demand
# via obsidian_read, and is persisted ONLY when Sir explicitly says "remember the
# content of note X" (a separate, deliberate path — not this sync).
# Form is always "project" — vault notes are Sir's work/project content.
# Dedup at 0.90 threshold (inherited from store_fact) prevents re-ingestion.

import os
import time
from pathlib import Path
from tools.file_paths import OBSIDIAN_VAULT
from core.memory.memory_store import store_fact

_SYNC_TS_FILE = Path(__file__).parent / ".vault_sync_ts"
_MAX_PURPOSE_CHARS = 200  # cap the optional purpose line for clean embedding


def _read_last_sync() -> float:
    """Return the last sync timestamp, or 0 if never synced."""
    try:
        return float(_SYNC_TS_FILE.read_text().strip())
    except Exception:
        return 0.0


def _write_last_sync(ts: float) -> None:
    try:
        _SYNC_TS_FILE.write_text(str(ts))
    except Exception as e:
        print(f"[vault_sync] Could not write sync timestamp: {e}")


def _extract_purpose(raw: str) -> str:
    """Return ONLY the YAML frontmatter 'purpose:' value. Never reads the note body.
    Frontmatter is the leading block delimited by '---' lines; parsing stops at the
    closing '---' so body content can never leak into a stored fact."""
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for ln in lines[1:]:
        if ln.strip() == "---":
            break  # end of frontmatter — never descend into the body
        if ln.lower().startswith("purpose:"):
            return ln.split(":", 1)[1].strip()[:_MAX_PURPOSE_CHARS]
    return ""


def _note_to_fact(path: Path) -> str:
    """Convert a vault note into an IDENTITY-only fact: title plus an optional
    'purpose:' line from frontmatter. The note BODY is never read or stored —
    content stays on disk, persisted only on Sir's explicit request."""
    title = path.stem
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        raw = ""
    purpose = _extract_purpose(raw)
    if purpose:
        return f"Obsidian note '{title}': {purpose}"
    return f"Obsidian note '{title}' exists in the vault."


def sync_vault_to_memory() -> int:
    """
    Scan the Obsidian vault for notes modified since last sync.
    Store each changed note as a Tier-3 project fact.
    Returns the number of new facts stored.
    """
    vault = Path(OBSIDIAN_VAULT)
    if not vault.is_dir():
        print(f"[vault_sync] Vault not found at {OBSIDIAN_VAULT} — skipping.")
        return 0

    last_sync = _read_last_sync()
    now = time.time()
    stored = 0

    for note_path in vault.glob("**/*.md"):
        try:
            mtime = note_path.stat().st_mtime
        except Exception:
            continue
        if mtime <= last_sync:
            continue

        fact = _note_to_fact(note_path)
        result = store_fact(
            fact=fact,
            form="project",
            emotional_weight="neutral",
            stability="permanent",
            source="vault",   # vault-sourced — excluded from personal recall and ambient context
        )
        if result != -1:
            stored += 1

    _write_last_sync(now)

    if stored:
        print(f"[vault_sync] Synced {stored} note(s) from vault to memory.")
    return stored
