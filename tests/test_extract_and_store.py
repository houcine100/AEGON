import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.memory.fact_extractor import extract_and_store

sessions_dir = Path(__file__).resolve().parent.parent / "core" / "memory" / "sessions"
session_files = sorted(sessions_dir.glob("session_*.jsonl"))

if not session_files:
    print("No session files found.")
    exit()

latest = session_files[-1]
print(f"Extracting and storing facts from: {latest.name}")
count = extract_and_store(latest)
print(f"Stored {count} facts.")