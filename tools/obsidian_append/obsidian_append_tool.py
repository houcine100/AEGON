# tools/obsidian_append/obsidian_append_tool.py
# Appends text to an existing note. Never overwrites.
# write_gated — always needs approval.

import os

from tools.base_connector import BaseConnector
from tools.file_paths import OBSIDIAN_VAULT, is_allowed


def _find_note(title: str) -> str | None:
    clean = title.strip()
    if clean.lower().endswith(".md"):
        clean = clean[:-3]
    for root, _dirs, files in os.walk(OBSIDIAN_VAULT):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            if os.path.splitext(fname)[0].lower() == clean.lower():
                return os.path.join(root, fname)
    return None


class ObsidianAppendConnector(BaseConnector):
    name = "obsidian_append"
    version = "1.0.0"
    description = "Appends text to an existing Obsidian note. Never overwrites existing content."
    permission_level = "write_gated"

    def validate(self, payload: dict) -> bool:
        return (isinstance(payload.get("title"), str) and len(payload["title"].strip()) > 0
                and isinstance(payload.get("content"), str) and len(payload["content"].strip()) > 0)

    def approval_prompt(self, payload: dict) -> str:
        title = payload.get("title", "").strip()
        preview = payload.get("content", "")[:80].strip()
        return f"This will append to note '{title}': \"{preview}...\". Shall I proceed, Sir?"

    def execute(self, payload: dict) -> dict:
        if not self.validate(payload):
            return {"status": "error", "output": "Both a note title and content to append are required."}
        title = payload["title"].strip()
        path = _find_note(title)
        if not path:
            return {"status": "error", "output": f"Note '{title}' not found. Use create to make a new note."}
        if not is_allowed(path):
            return {"status": "denied", "output": f"Path not allowed: {path}"}
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n" + payload["content"])
        except Exception as e:
            return {"status": "error", "output": f"Could not append to note: {e}"}
        return {"status": "success", "output": f"Appended to note '{title}'."}
