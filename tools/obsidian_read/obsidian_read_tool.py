# tools/obsidian_read/obsidian_read_tool.py
# Returns the full content of a named note.
# read_only — no approval needed.

import os

from tools.base_connector import BaseConnector
from tools.file_paths import OBSIDIAN_VAULT


def _find_note(title: str) -> str | None:
    """Return the path to the note matching title (case-insensitive, .md optional)."""
    clean = title.strip()
    if clean.lower().endswith(".md"):
        clean = clean[:-3]
    for root, _dirs, files in os.walk(OBSIDIAN_VAULT):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            note_title = os.path.splitext(fname)[0]
            if note_title.lower() == clean.lower():
                return os.path.join(root, fname)
    return None


class ObsidianReadConnector(BaseConnector):
    name = "obsidian_read"
    version = "1.0.0"
    description = "Reads the full content of a specific Obsidian note by title."
    permission_level = "read_only"

    def validate(self, payload: dict) -> bool:
        return isinstance(payload.get("title"), str) and len(payload["title"].strip()) > 0

    def execute(self, payload: dict) -> dict:
        if not self.validate(payload):
            return {"status": "error", "output": "A note title is required."}
        title = payload["title"].strip()
        path = _find_note(title)
        if not path:
            return {"status": "error", "output": f"Note '{title}' not found in the vault."}
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return {"status": "error", "output": f"Could not read note: {e}"}
        return {"status": "success", "output": content}
