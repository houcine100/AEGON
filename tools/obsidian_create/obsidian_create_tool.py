# tools/obsidian_create/obsidian_create_tool.py
# Creates a new .md note in the vault root. Never overwrites.
# write_gated — always needs approval.

import os

from tools.base_connector import BaseConnector
from tools.file_paths import OBSIDIAN_VAULT, is_allowed


def _safe_filename(title: str) -> str:
    """Strip characters not allowed in filenames."""
    forbidden = r'\/:*?"<>|'
    return "".join(c for c in title if c not in forbidden).strip()


class ObsidianCreateConnector(BaseConnector):
    name = "obsidian_create"
    version = "1.0.0"
    description = "Creates a new Obsidian note. Never overwrites an existing note."
    permission_level = "write_gated"

    def validate(self, payload: dict) -> bool:
        return (isinstance(payload.get("title"), str) and len(payload["title"].strip()) > 0
                and isinstance(payload.get("content"), str))

    def approval_prompt(self, payload: dict) -> str:
        title = _safe_filename(payload.get("title", "").strip())
        return f"This will create a new note '{title}.md' in the vault. Shall I proceed, Sir?"

    def execute(self, payload: dict) -> dict:
        if not self.validate(payload):
            return {"status": "error", "output": "Both a title and content are required."}
        title = _safe_filename(payload["title"].strip())
        if not title:
            return {"status": "error", "output": "The note title contains no valid characters."}
        path = os.path.join(OBSIDIAN_VAULT, f"{title}.md")
        if not is_allowed(path):
            return {"status": "denied", "output": f"Path not allowed: {path}"}
        if os.path.exists(path):
            return {"status": "error", "output": f"Note '{title}' already exists. Use append to add content."}
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(payload["content"])
        except Exception as e:
            return {"status": "error", "output": f"Could not create note: {e}"}
        return {"status": "success", "output": f"Note '{title}' created in the vault."}
