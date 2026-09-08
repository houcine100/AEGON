import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.memory.fact_extractor import extract_facts_from_session

sessions_dir = Path("core/memory/sessions")
session_files = sorted(sessions_dir.glob("session_*.jsonl"))

if not session_files:
    print("No session files found.")
    exit()

latest = session_files[-1]
print(f"Extracting facts from: {latest.name}\n")

facts = extract_facts_from_session(latest)

if not facts:
    print("No facts extracted.")
else:
    for f in facts:
        print(f"[{f['form']}] {f['fact']}")
        print(f"  weight={f['emotional_weight']} stability={f['stability']} source={f['source']}")
        print()