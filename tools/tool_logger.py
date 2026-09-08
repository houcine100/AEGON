# tools/tool_logger.py
# Logs every connector (tool) call to a JSONL file.
# Sits beside decisions.jsonl in core/observability/logs/.
# Same style as decision_logger.py — build a record, append one line.

import json
import os
from datetime import datetime

# --- Log file location ---
# Beside decisions.jsonl, in the same logs folder.
LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "core", "observability", "logs",
)
LOG_FILE = os.path.join(LOG_DIR, "tool_calls.jsonl")


def _ensure_log_dir() -> None:
    """Creates the logs directory if it does not exist."""
    os.makedirs(LOG_DIR, exist_ok=True)


def log_tool_call(
        tool_name: str,
        payload: dict,
        result: dict,
        approval_status: str,
        session_id: str = None,
        thread_id: str = None,
) -> None:
    """
    Writes one tool call to the JSONL log.
    Called by tool_node (Step 3) after every connector runs.

    Fields logged:
        - timestamp
        - tool_name
        - payload (what the tool was given)
        - result (what the tool returned)
        - approval_status ("approved", "not_required", "rejected")
        - session_id
        - thread_id
    """
    _ensure_log_dir()

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "tool_name": tool_name,
        "payload": payload,
        "result": result,
        "approval_status": approval_status,
        "session_id": session_id,
        "thread_id": thread_id,
    }

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[tool_logger] Failed to write log: {e}")


def read_last_n(n: int = 10) -> list:
    """Reads the last n tool calls. For debugging and review."""
    _ensure_log_dir()
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        records = [json.loads(line) for line in lines if line.strip()]
        return records[-n:]
    except Exception as e:
        print(f"[tool_logger] Failed to read log: {e}")
        return []