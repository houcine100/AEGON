# tools/obsidian_search/obsidian_search_tool.py
# Searches all .md files in the Obsidian vault for a keyword.
# read_only — no approval needed.

import os

from tools.base_connector import BaseConnector
from tools.file_paths import OBSIDIAN_VAULT

MAX_RESULTS = 5
MAX_FILE_BYTES = 500_000   # skip files larger than 500 KB
EXCERPT_CHARS = 200        # chars around the match to return as excerpt


def _excerpt(content: str, query: str) -> str:
    idx = content.lower().find(query.lower())
    if idx == -1:
        return content[:EXCERPT_CHARS].strip()
    start = max(0, idx - 80)
    end = min(len(content), idx + EXCERPT_CHARS - 80)
    return ("..." if start > 0 else "") + content[start:end].strip() + ("..." if end < len(content) else "")


def _search_vault(query: str) -> list[dict]:
    matches = []
    for root, _dirs, files in os.walk(OBSIDIAN_VAULT):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            if os.path.getsize(fpath) > MAX_FILE_BYTES:
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue
            title = os.path.splitext(fname)[0]
            if query.lower() in title.lower() or query.lower() in content.lower():
                matches.append({"title": title, "excerpt": _excerpt(content, query)})
            if len(matches) >= MAX_RESULTS:
                break
    return matches


class ObsidianSearchConnector(BaseConnector):
    name = "obsidian_search"
    version = "1.0.0"
    description = "Searches Sir's Obsidian notes for a keyword or phrase."
    permission_level = "read_only"

    def validate(self, payload: dict) -> bool:
        return isinstance(payload.get("query"), str) and len(payload["query"].strip()) > 0

    def execute(self, payload: dict) -> dict:
        if not self.validate(payload):
            return {"status": "error", "output": "A search query is required."}
        query = payload["query"].strip()
        results = _search_vault(query)
        if not results:
            return {"status": "success", "output": f"No notes found matching '{query}'."}
        lines = [f"Found {len(results)} note(s) matching '{query}':"]
        for r in results:
            lines.append(f"\n— {r['title']}\n  {r['excerpt']}")
        return {"status": "success", "output": "\n".join(lines)}
