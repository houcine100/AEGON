# core/orchestration/nodes/response_synthesizer.py
# Final node before Gemini TTS.
# Applies Aegon personality finish only when needed.
# Never rewrites responses that are already correct.
# Hands off to Gemini TTS.

from core.orchestration.state import AegonState
from core.orchestration.llm_client import call_llm
from core.memory.memory_store import search_facts
from core.voice.speak import speak
from prompts.synthesizer_prompt import SYNTHESIZER_PROMPT
from schemas.intent_schema import Intent

_CHALLENGE_INTENTS = {Intent.TASK, Intent.PLAN_REQUEST}

_CHALLENGE_SYSTEM_PROMPT = """You are Aegon's challenge check. Given a task description and a list of Sir's stored habits, decisions, and preferences, determine if the task conflicts with any of them.

Return ONLY one of:
- A single sentence ending with "Still confirm?" if there is a genuine, specific conflict
- An empty string if there is no conflict

Rules:
1. Only flag a real, direct conflict — not a vague concern
2. Name the specific fact the task conflicts with
3. Never invent a conflict not supported by a fact
4. Do not challenge if the task is neutral or aligned with the facts
5. One conflict maximum — pick the strongest if multiple exist
6. The sentence must be under 25 words

Memory facts:
{facts}"""


# --- Responses that must never be rewritten ---
# These are precise, intentional responses from governance or approval gates.
# The synthesizer must return them exactly as is.
PROTECTED_PHRASES = [
    "That requires your approval",
    "That requires real-world",
    "That requires a capability",
    "I cannot do that",
    "That is not something I will do",
    "I did not understand that",
    "My rules are not negotiable",
    "Sir prefers",
    "Sir wants",
    "Sir needs",
    "Sir has",
    "Sir is",
    "No information available",
    "No data available",
    "1.",
    "2.",
    "3.",
    "Sir, I remember",
    "Sir, I know",
    "Sir, based on",
    "Sir, you have",
    "Sir, you often",
    "Sir, you prefer",
    "Sir, you've been",
    "Sir, here are",
]


def _challenge_check(task_description: str) -> str:
    """Returns a one-sentence challenge ending 'Still confirm?' if the task conflicts
    with a stored habit, decision, or preference — empty string otherwise."""
    facts = search_facts(task_description, top_k=5)
    if not facts:
        return ""

    facts_text = "\n".join(f"- {f['fact']}" for f in facts)
    system = _CHALLENGE_SYSTEM_PROMPT.format(facts=facts_text)
    result = call_llm(system_prompt=system, user_message=task_description, temperature=0.1)
    result = result.strip()

    if "Still confirm?" not in result:
        return ""
    # Reject multi-sentence responses — challenge must be one sentence
    if result.count(".") >= 2 or "\n" in result:
        return ""
    return result


def _needs_synthesis(response: str) -> bool:
    """
    Returns True only if the response needs Groq personality polish.
    Returns False if the response is already correct and must not be touched.
    """
    # Never touch short responses — already complete
    if len(response) <= 500:
        return False

    # Never touch numbered lists
    for phrase in PROTECTED_PHRASES:
        if phrase.lower() in response.lower():
            return False

    return True


def response_synthesizer(state: AegonState) -> AegonState:
    worker_response = state.get("worker_response", "")
    governance_result = state.get("governance_result", "pass")
    intent = state.get("intent", "")
    raw_input = state.get("raw_input", "")
    decision_log = state.get("decision_log") or []

    # Governance failed — speak blocked response exactly as is
    if governance_result == "fail":
        final_response = worker_response

    # Response is protected — do not rewrite
    elif not _needs_synthesis(worker_response):
        final_response = worker_response

    # Response needs personality polish — call Groq
    else:
        final_response = call_llm(
            system_prompt=SYNTHESIZER_PROMPT,
            user_message=worker_response,
            temperature=0.3,
        )

    # Challenge check — fires only for task/plan intents when governance passed.
    # Skip it when a tool ran this turn (tool_result set): read-only retrievals
    # (obsidian_search, weather, web_search) have nothing to confirm, and gated
    # tool actions are already covered by the approval gate. Only brain-only
    # tasks and plans — the real A4 targets — reach the challenge.
    challenge = ""
    used_tool = state.get("tool_result") is not None
    if governance_result == "pass" and intent in _CHALLENGE_INTENTS and raw_input and not used_tool:
        challenge = _challenge_check(raw_input)
        if challenge:
            final_response = f"{challenge} {final_response}"

    # Speak the final response — Aegon's single mouth
    speak(final_response)

    # Log the decision
    decision_log.append({
        "node": "response_synthesizer",
        "governance_result": governance_result,
        "worker_response": worker_response,
        "final_response": final_response,
        "synthesis_applied": _needs_synthesis(worker_response) and governance_result != "fail",
        "challenge_fired": bool(challenge),
    })

    return {
        **state,
        "final_response": final_response,
        "decision_log": decision_log,
    }