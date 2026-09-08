# tools/file_write/file_write_tool.py
# Writes text to a file. WRITE GATED — needs approval. Limited to allowed folders.
# (The approval gate is enforced by tool_node in 4b — this tool just does the write.)

from tools.base_connector import BaseConnector
from tools.file_paths import is_allowed


class FileWriteConnector(BaseConnector):
    name = "file_write"
    version = "1.0.0"
    description = "Writes text to a file in an allowed folder."
    permission_level = "write_gated"

    def validate(self, payload: dict) -> bool:
        path = payload.get("path")
        content = payload.get("content")
        return (isinstance(path, str) and len(path.strip()) > 0
                and isinstance(content, str))

    def execute(self, payload: dict) -> dict:
        if not self.validate(payload):
            return {"status": "error", "output": "Need both a path and content."}
        path = payload["path"].strip()
        content = payload["content"]
        if not is_allowed(path):
            return {"status": "denied", "output": f"Path not allowed: {path}"}
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            return {"status": "error", "output": f"Write failed: {e}"}
        return {"status": "success", "output": f"Wrote {len(content)} characters to {path}"}