# core/memory/inference_engine.py
# Weekly LLM pass: finds patterns across stored facts, stores conclusions.
# Inferences carry form="inference", source="inference_engine" — never presented as stated facts.
# Called at session start via maybe_run_inference() — runs only if 7 days have elapsed.

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from core.memory.memory_store import get_all_active_facts, store_fact
from core.orchestration.llm_client import call_llm

_TS_FILE = Path(__file__).parent / ".inference_ts"
_INTERVAL_DAYS = 7
_MIN_SOURCE_FACTS = 5

INFERENCE_PROMPT = """You are a pattern-recognition engine for a personal AI assistant called Aegon.
You are given a list of known facts about Sir.
Your job: identify conclusions SUPPORTED by multiple independent facts that Sir has not explicitly stated.

Rules:
- Only generate inferences supported by at least 2 independent facts.
- Each inference must be a single clear sentence about Sir.
- Never repeat what is already explicitly stated — infer what is implied.
- Never speculate beyond what the evidence supports.
- Do not include inferences about Aegon itself.
- Assign confidence: high (3+ supporting facts), medium (2 supporting facts).
- Maximum 5 inferences per run.

Respond ONLY with a JSON array. No other text. No markdown. Example:
[
  {
    "inference": "Sir appears to do his best work late at night.",
    "confidence": "high",
    "supporting_count": 3
  }
]

If no clear patterns exist, respond with: []"""


def _last_run() -> datetime:
    if not _TS_FILE.exists():
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromtimestamp(float(_TS_FILE.read_text().strip()), tz=timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _save_ts() -> None:
    _TS_FILE.write_text(str(datetime.now(timezone.utc).timestamp()))


def is_due() -> bool:
    return (datetime.now(timezone.utc) - _last_run()).days >= _INTERVAL_DAYS


def run_inference() -> int:
    """Run the inference pass. Returns count of new inferences stored."""
    facts = get_all_active_facts()
    source_facts = [f for f in facts if f["form"] != "inference"]

    if len(source_facts) < _MIN_SOURCE_FACTS:
        _save_ts()
        return 0

    facts_text = "\n".join(f"- [{f['form']}] {f['fact']}" for f in source_facts)
    raw = call_llm(
        system_prompt=INFERENCE_PROMPT,
        user_message=f"Known facts about Sir:\n{facts_text}",
        temperature=0.3,
    )

    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            _save_ts()
            return 0
        items = json.loads(raw[start:end])
    except Exception:
        _save_ts()
        return 0

    count = 0
    for item in items:
        if not isinstance(item, dict) or not item.get("inference"):
            continue
        result = store_fact(
            fact=item["inference"],
            form="inference",
            emotional_weight="neutral",
            stability="permanent",
            source="inference_engine",
        )
        if result != -1:
            count += 1

    _save_ts()
    return count


def maybe_run_inference() -> int:
    """Run inference only if the weekly interval has elapsed. Safe to call at session start."""
    if not is_due():
        return 0
    try:
        return run_inference()
    except Exception as e:
        print(f"[inference_engine] Error: {e}")
        return 0
