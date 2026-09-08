# core/memory/fact_extractor.py
# Extracts facts from session logs and real-time turns.
# Uses llm_client.py — single shared client — no own Groq instance.

import json
import os
import base64
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet
from core.orchestration.llm_client import call_llm

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

VALID_FORMS = {"user_profile", "decision", "project", "habit", "error"}

EXTRACTION_PROMPT = """You are a memory extraction system for a personal AI assistant called Aegon.
Your job is to extract important, durable facts about Sir from a conversation log.

Rules:
- Only extract facts that are worth remembering long term.
- NEVER extract a command, request, or instruction Sir gives to Aegon. Phrases like
  "delete X", "forget Y", "wipe what you know about Z", "remember this", "play that",
  "search for ...", "remind me ..." are ACTIONS for Aegon to perform — they are NOT facts
  about Sir. An instruction to act is never a memory. Skip them entirely.
- Skip casual small talk, greetings, and one-off comments.
- Skip anything that is already obvious or generic.
- Each fact must be a single clear sentence about Sir — his identity, preferences,
  decisions, projects, or habits. Never a sentence describing what Sir told Aegon to do.
- Assign each fact one of these forms: user_profile, decision, project, habit, error
  - user_profile: who Sir is, preferences, personality, style
  - decision: choices Sir made and why
  - project: goals, plans, things Sir is building or working on
  - habit: routines, patterns, recurring behaviors
  - error: mistakes Aegon made that must not be repeated
- Assign emotional_weight: neutral, stressed, anxious, excited, or the detected emotion
- Assign stability: permanent or temporary
- Assign source: explicit (Sir stated it directly) or inferred (Aegon detected it)

Respond ONLY with a JSON array. No other text. No markdown. Example:
[
  {
    "fact": "Sir prefers working at night.",
    "form": "habit",
    "emotional_weight": "neutral",
    "stability": "permanent",
    "source": "inferred"
  }
]

If there are no facts worth extracting, respond with an empty array: []"""


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _get_fernet():
    key = os.environ.get("AEGON_ENCRYPTION_KEY", "")
    if not key:
        return None
    derived = hashlib.sha256(key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def load_session(session_file: Path) -> str:
    """Load a JSONL session file and format it as readable conversation."""
    fernet = _get_fernet()
    lines = []
    with open(session_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                if fernet:
                    decrypted = fernet.decrypt(line.encode()).decode()
                    record = json.loads(decrypted)
                else:
                    record = json.loads(line)
            except Exception:
                try:
                    record = json.loads(line)
                except Exception:
                    continue

            # Sir-turns only — same rule as extract_facts_from_turns.
            if record["type"] == "turn" and record.get("speaker") == "user":
                lines.append(f"Sir: {record['text']}")
            elif record["type"] == "task":
                lines.append(f"Sir requested: {record['task_text']}")
    return "\n".join(lines)


def parse_facts(raw: str) -> list:
    """Parse LLM JSON response into list of fact dicts."""
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        facts = json.loads(raw[start:end])
        valid = []
        for f in facts:
            if (
                    isinstance(f, dict)
                    and f.get("fact")
                    and f.get("form") in VALID_FORMS
            ):
                valid.append(f)
        return valid
    except Exception:
        return []


# ─────────────────────────────────────────
# EXTRACTOR
# ─────────────────────────────────────────

def extract_facts_from_session(session_file: Path) -> list:
    """Extract facts from a session JSONL file using llm_client."""
    conversation = load_session(session_file)
    if not conversation.strip():
        return []

    raw = call_llm(
        system_prompt=EXTRACTION_PROMPT,
        user_message=f"Extract facts from this conversation:\n\n{conversation}",
        temperature=0.2,
    )
    return parse_facts(raw)


def extract_and_store(session_file: Path) -> int:
    """Extract facts from session and store in Tier 3. Returns count stored."""
    from core.memory.memory_store import store_fact

    facts = extract_facts_from_session(session_file)
    count = 0
    for f in facts:
        store_fact(
            fact=f["fact"],
            form=f["form"],
            emotional_weight=f.get("emotional_weight", "neutral"),
            stability=f.get("stability", "permanent"),
            source=f.get("source", "inferred")
        )
        count += 1
    return count


def extract_facts_from_turns(recent_turns: list) -> list:
    """
    Extract facts from a list of recent turn dicts passed directly.
    Used for real-time extraction during 24/7 operation.
    """
    if not recent_turns:
        return []

    # Sir-turns only — Aegon's replies can contain recited memory or relayed
    # external content (email, search results); extracting them re-ingests it.
    lines = []
    for record in recent_turns:
        if record.get("type") == "turn" and record.get("speaker") == "user":
            lines.append(f"Sir: {record['text']}")
        elif record.get("type") == "task":
            lines.append(f"Sir requested: {record['task_text']}")

    conversation = "\n".join(lines)
    if not conversation.strip():
        return []

    raw = call_llm(
        system_prompt=EXTRACTION_PROMPT,
        user_message=f"Extract facts from this conversation:\n\n{conversation}",
        temperature=0.2,
    )
    return parse_facts(raw)


def extract_and_store_from_turns(recent_turns: list) -> int:
    """
    Extract facts from recent turns and store in Tier 3.
    Returns count of new facts stored.
    Used for real-time 24/7 memory updates.
    """
    from core.memory.memory_store import store_fact

    facts = extract_facts_from_turns(recent_turns)
    count = 0
    for f in facts:
        result = store_fact(
            fact=f["fact"],
            form=f["form"],
            emotional_weight=f.get("emotional_weight", "neutral"),
            stability=f.get("stability", "permanent"),
            source=f.get("source", "inferred")
        )
        if result != -1:
            count += 1
            try:
                from core.sentinel import sentinel
                sentinel.on_fact_stored()
            except Exception:
                pass  # sentinel not running — silent no-op
    return count