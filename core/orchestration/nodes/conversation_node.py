# core/orchestration/nodes/conversation_node.py
# Groq call #3a — Aegon personality node.
# Handles casual conversation and follow-up questions.
# Respects active mode — adjusts behavior accordingly.

from core.orchestration.state import AegonState
from core.orchestration.llm_client import call_llm
from prompts.conversation_prompt import CONVERSATION_PROMPT
from prompts.identity import build_capability_summary
from prompts.mode_prompts import Mode, get_mode_instruction

# Built once from the live tool registry — the registry does not change at runtime.
_CAPABILITY_SUMMARY = None


def _capability_summary() -> str:
    global _CAPABILITY_SUMMARY
    if _CAPABILITY_SUMMARY is None:
        _CAPABILITY_SUMMARY = build_capability_summary()
    return _CAPABILITY_SUMMARY


def conversation_node(state: AegonState) -> AegonState:
    a2a_payload = state.get("a2a_payload") or {}
    payload = a2a_payload.get("payload", state.get("raw_input", ""))
    memory_context = state.get("memory_context")
    conversation_history = state.get("conversation_history")
    active_mode = state.get("active_mode") or Mode.STANDARD
    decision_log = state.get("decision_log") or []

    # In focus or deep_work mode — block casual conversation
    if active_mode in [Mode.FOCUS, Mode.DEEP_WORK]:
        response = f"{active_mode.replace('_', ' ').title()} mode is active, Sir."
        decision_log.append({
            "node": "conversation_node",
            "active_mode": active_mode,
            "action": "blocked — mode restricts casual conversation",
            "worker_response": response,
        })
        return {
            **state,
            "worker_response": response,
            "decision_log": decision_log,
        }

    # Build system prompt. Capabilities are always present, not only when asked —
    # otherwise Aegon disclaims things it can actually do.
    system_prompt = CONVERSATION_PROMPT + "\n" + _capability_summary()

    # Inject memory context if available
    if memory_context:
        system_prompt += f"\n\nMemory context:\n{memory_context}"

    # Inject conversation history if available
    if conversation_history:
        system_prompt += f"\n\nRecent conversation:\n{conversation_history}"

    # Inject mode instruction
    mode_instruction = get_mode_instruction(active_mode)
    if mode_instruction:
        system_prompt += f"\n\n{mode_instruction}"

    # Morning mode — lead with memory briefing
    if active_mode == Mode.MORNING:
        if memory_context:
            system_prompt += (
                "\n\nFor morning mode: start your response with a brief summary "
                "of Sir's most important active tasks and any time-sensitive items. "
                "Then answer the question naturally."
                # Phase 5: enhance with calendar, weather, news MCP tools
            )

    response = call_llm(
        system_prompt=system_prompt,
        user_message=payload,
        temperature=0.7,
    )

    decision_log.append({
        "node": "conversation_node",
        "active_mode": active_mode,
        "payload_received": payload,
        "memory_context_injected": memory_context is not None,
        "history_injected": conversation_history is not None,
        "worker_response": response,
    })

    return {
        **state,
        "worker_response": response,
        "decision_log": decision_log,
    }