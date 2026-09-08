# core/orchestration/nodes/task_node.py
# Groq call #3b — handles detected task requests.
# Checks capability availability before checking requires_approval.
# Respects active mode — adjusts behavior accordingly.

import re
from core.orchestration.state import AegonState
from core.orchestration.llm_client import call_llm
from prompts.task_prompt import TASK_PROMPT
from prompts.mode_prompts import Mode, get_mode_instruction


AVAILABLE_CAPABILITIES = [
    "reminder",
    "reminders",
    "remind",
    "remember",
    "note",
    "summarize",
    "summary",
    "plan",
    "planning",
    "analyse",
    "analyze",
    "breakdown",
    "explain",
    "help me",
]


def _has_capability(payload: str) -> bool:
    payload_lower = payload.lower()
    for cap in AVAILABLE_CAPABILITIES:
        pattern = r'\b' + re.escape(cap) + r'\b'
        if re.search(pattern, payload_lower):
            return True
    return False


def task_node(state: AegonState) -> AegonState:
    a2a_payload = state.get("a2a_payload") or {}
    payload = a2a_payload.get("payload", state.get("raw_input", ""))
    requires_approval = state.get("requires_approval", False)
    memory_context = state.get("memory_context")
    active_mode = state.get("active_mode") or Mode.STANDARD
    decision_log = state.get("decision_log") or []



    # Capability check first
    if requires_approval and not _has_capability(payload):
        response = "That requires a capability I do not have yet, Sir. It is planned."
        decision_log.append({
            "node": "task_node",
            "active_mode": active_mode,
            "payload_received": payload,
            "requires_approval": True,
            "action": "blocked — capability not available",
            "worker_response": response,
        })
        return {
            **state,
            "worker_response": response,
            "decision_log": decision_log,
        }

    if requires_approval and _has_capability(payload):
        response = "That requires your approval, Sir. Shall I proceed?"
        decision_log.append({
            "node": "task_node",
            "active_mode": active_mode,
            "payload_received": payload,
            "requires_approval": True,
            "action": "blocked — waiting for approval",
            "worker_response": response,
        })
        return {
            **state,
            "worker_response": response,
            "decision_log": decision_log,
        }

    # Build system prompt
    system_prompt = TASK_PROMPT

    # Inject memory context if available
    if memory_context:
        system_prompt += f"\n\nMemory context:\n{memory_context}"

    # Inject mode instruction for style only — never block task execution
    # Tasks always execute regardless of mode.
    # Mode only affects response length and tone.
    if active_mode == Mode.FOCUS or active_mode == Mode.DEEP_WORK:
        system_prompt += (
            "\n\nIMPORTANT: Complete this task. "
            "Respond in ONE short sentence only. "
            "No explanation. No personality. Just confirm the task."
        )
    elif active_mode == Mode.NIGHT:
        system_prompt += (
            "\n\nIMPORTANT: Complete this task. "
            "Keep response calm and brief. One sentence maximum."
        )
    elif active_mode == Mode.RESEARCH:
        system_prompt += (
            "\n\nIMPORTANT: Complete this task with full detail and context."
        )
    elif active_mode == Mode.MORNING:
        system_prompt += (
            "\n\nIMPORTANT: Complete this task efficiently. "
            "Sir is starting his day."
        )

    response = call_llm(
        system_prompt=system_prompt,
        user_message=payload,
        temperature=0.3,
    )

    decision_log.append({
        "node": "task_node",
        "active_mode": active_mode,
        "payload_received": payload,
        "requires_approval": False,
        "memory_context_injected": memory_context is not None,
        "worker_response": response,
    })

    return {
        **state,
        "worker_response": response,
        "decision_log": decision_log,
    }