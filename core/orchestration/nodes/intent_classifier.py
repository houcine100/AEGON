# core/orchestration/nodes/intent_classifier.py
# Groq call #1 — reads raw_input, returns intent label, confidence, and requested_mode.
# Writes intent, confidence, and requested_mode back to AegonState.
# No other job. No response generation. Classification only.

import json
from core.orchestration.state import AegonState
from core.orchestration.llm_client import call_llm
from prompts.intent_classifier_prompt import INTENT_CLASSIFIER_PROMPT
from schemas.intent_schema import Intent


def intent_classifier(state: AegonState) -> AegonState:
    raw_input = state.get("raw_input", "")
    decision_log = state.get("decision_log") or []

    # Call LLM — classification only
    raw_response = call_llm(
        system_prompt=INTENT_CLASSIFIER_PROMPT,
        user_message=raw_input,
        temperature=0.1,
    )

    # Parse the JSON response
    try:
        parsed = json.loads(raw_response)
        intent = parsed.get("intent", Intent.CONVERSATION)
        confidence = float(parsed.get("confidence", 0.0))
        requested_mode = parsed.get("requested_mode", None)

        # Safety check — reject any intent not in the valid list
        if intent not in Intent.ALL:
            intent = Intent.CLARIFICATION_NEEDED
            confidence = 0.0
            requested_mode = None

        # Low confidence fallback
        if confidence < 0.5:
            intent = Intent.CLARIFICATION_NEEDED
            requested_mode = None

    except (json.JSONDecodeError, ValueError):
        intent = Intent.CLARIFICATION_NEEDED
        confidence = 0.0
        requested_mode = None
        raw_response = ""

    # Log the decision
    decision_log.append({
        "node": "intent_classifier",
        "raw_input": raw_input,
        "intent_classified": intent,
        "confidence": confidence,
        "requested_mode": requested_mode,
        "raw_llm_response": raw_response,
    })

    return {
        **state,
        "intent": intent,
        "confidence": confidence,
        "requested_mode": requested_mode,
        "decision_log": decision_log,
    }