# core/research_notes.py
# Saves link-bearing search results to workspace/research/ so Aegon can say
# "I've put the links in a note" instead of reading URLs aloud.
#
# WHY THIS IS UNGATED (a deliberate, narrow Axiom 1 exception — Sir's decision, 2026-08-07):
#   Aegon has no display surface. Reading "open.spotify.com/track/7tFiyTwD0nx5a1eklYtX2J"
#   aloud is useless. The content saved here is PUBLIC search output — the equivalent of
#   pasting Google results into a scratch file — not memory, not personal data, and
#   nothing that leaves the machine.
#
# The exception is scoped, and these bounds are the reason it is acceptable:
#   - Writes ONLY to workspace/research/. Never the vault (curated personal knowledge,
#     still fully gated), never an arbitrary path.
#   - Filenames are auto-generated from the query, never Sir-specified — so a crafted
#     query cannot steer the write location.
#   - Every path is checked through file_paths.is_allowed() before writing.
#   - Only saves results that already came back from a read-only search tool.
#   - Never writes memory content.
#
# Do NOT widen this to the vault or to caller-supplied paths without Sir's approval.

import os
import re
from datetime import datetime

from tools.file_paths import WORKSPACE, is_allowed

RESEARCH_DIR = os.path.join(WORKSPACE, "research")

# Below this, just speak the results — a note is more friction than help.
MIN_RESULTS_TO_SAVE = 2


def _slugify(text: str, max_len: int = 40) -> str:
    """Filesystem-safe slug from Sir's query. Auto-generated, never caller-controlled."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return (slug[:max_len].rstrip("-") or "search")


def _linked_results(results) -> list:
    """Results that actually carry a link. Anything else is speakable as-is."""
    if not isinstance(results, list):
        return []
    return [r for r in results
            if isinstance(r, dict) and (r.get("href") or "").strip()]


def save_research_note(query: str, results, tool_name: str = "") -> str:
    """Write results to workspace/research/ and return the filename, or "" if not saved.

    Returns "" — never raises — so a failure here can only cost the note, never the answer.
    """
    linked = _linked_results(results)
    if len(linked) < MIN_RESULTS_TO_SAVE:
        return ""

    try:
        os.makedirs(RESEARCH_DIR, exist_ok=True)
        stamp = datetime.now()
        filename = f"{stamp:%Y-%m-%d}-{_slugify(query)}.md"
        path = os.path.join(RESEARCH_DIR, filename)

        # Structural guard: the path is built here, but check it anyway.
        if not is_allowed(path):
            return ""

        # Same query twice in a day appends rather than clobbering the earlier note.
        exists = os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            if not exists:
                f.write(f"# {query or 'Search results'}\n\n")
            f.write(f"_{stamp:%Y-%m-%d %H:%M}"
                    f"{f' · {tool_name}' if tool_name else ''}_\n\n")
            for r in linked:
                title = (r.get("title") or "Untitled").strip()
                href = (r.get("href") or "").strip()
                body = (r.get("body") or "").strip()
                f.write(f"- [{title}]({href})\n")
                if body:
                    f.write(f"  - {body}\n")
            f.write("\n")
        return filename
    except OSError:
        return ""
