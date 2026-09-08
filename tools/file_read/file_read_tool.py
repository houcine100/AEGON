# tools/file_read/file_read_tool.py
# Reads a text file. READ ONLY — no approval. Limited to allowed folders.

from tools.base_connector import BaseConnector
from tools.file_paths import is_allowed


class FileReadConnector(BaseConnector):
    name = "file_read"
    version = "1.0.0"
    description = "Reads a text file from an allowed folder."
    permission_level = "read_only"

    def validate(self, payload: dict) -> bool:
        path = payload.get("path")
        return isinstance(path, str) and len(path.strip()) > 0

    def execute(self, payload: dict) -> dict:
        if not self.validate(payload):
            return {"status": "error", "output": "No file path given."}
        path = payload["path"].strip()
        if not is_allowed(path):
            return {"status": "denied", "output": f"Path not allowed: {path}"}
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            return {"status": "error", "output": f"File not found: {path}"}
        except Exception as e:
            return {"status": "error", "output": f"Read failed: {e}"}
        return {"status": "success", "output": content}