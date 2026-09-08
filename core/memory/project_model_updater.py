# core/memory/project_model_updater.py
# Background updater: fires after project-related conversation turns,
# extracts structured project state via LLM, upserts into project_models.

import json
import re
from core.orchestration.llm_client import call_llm
from core.memory.project_model_store import upsert_project_model

_PROJECT_KEYWORDS = {
    "project", "working on", "building", "stuck", "blocked", "blocker",
    "progress", "milestone", "deadline", "ship", "release", "feature",
    "sprint", "implementing", "developing", "developed",
}

_VALID_FIELDS = {"name", "domain", "current_state", "next_decision", "blockers", "confidence"}

_EXTRACT_PROMPT = """Extract structured project state from this conversation turn.

Sir said: {raw_input}
Aegon replied: {response}

Return a JSON object with these optional fields:
- "name": short project name (string)
- "domain": category — "software", "business", "personal", "fitness", etc. (string)
- "current_state": one sentence on where the project is now (string)
- "next_decision": the next decision or action needed (string)
- "blockers": current obstacles (string)
- "confidence": extraction confidence 0.0–1.0 (float)

Return ONLY valid JSON. If no project is mentioned, return {{}}."""


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


def maybe_update_project_models(raw_input: str, response: str) -> None:
    """
    Keyword-gate then LLM extraction. Runs in a daemon thread — never raises.
    """
    try:
        text = (raw_input + " " + response).lower()
        if not any(kw in text for kw in _PROJECT_KEYWORDS):
            return

        prompt = _EXTRACT_PROMPT.format(raw_input=raw_input, response=response)
        result = call_llm(system_prompt=prompt, user_message="", temperature=0.1)
        extracted = _parse_json(result)

        if not extracted or "name" not in extracted:
            return

        kwargs = {k: v for k, v in extracted.items() if k in _VALID_FIELDS}
        upsert_project_model(**kwargs)
    except Exception as e:
        print(f"[project_model_updater] Failed: {e}")
