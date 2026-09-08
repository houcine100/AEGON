# core/orchestration/state.py
# Defines AegonState — the single shared object that flows through every node.
# Every node reads from it and writes back to it. Nothing is passed by argument.

from typing import Optional
from typing_extensions import TypedDict


class AegonState(TypedDict):
    # --- Input ---
    session_id: str
    thread_id: str
    raw_input: str

    # --- Active mode ---
    # Persisted across turns by aegon_orchestrator.py
    # Defaults to "standard" if not set.
    active_mode: Optional[str]

    # --- Conversation history ---
    # Last 6 turns (3 exchanges) formatted as plain text.
    conversation_history: Optional[str]

    # --- Filled by intent_classifier node ---
    intent: Optional[str]
    confidence: Optional[float]

    # --- Filled by mode_switch_node ---
    requested_mode: Optional[str]          # the mode Sir requested to switch to

    # --- Filled by orchestrator node ---
    a2a_payload: Optional[dict]

    # --- Filled by conversation_node or task_node ---
    worker_response: Optional[str]

    # --- Filled by governance_node ---
    governance_result: Optional[str]
    governance_reason: Optional[str]
    requires_approval: Optional[bool]

    # --- Filled by response_synthesizer ---
    final_response: Optional[str]

    # --- Filled progressively by every node ---
    decision_log: Optional[list]

    # --- Injected at graph start ---
    memory_context: Optional[str]

    # --- Phase 5 — Step 1: approval flow + tool execution ---
    # pending_approval: the parked action carried ACROSS turns, awaiting Sir's
    #   yes/no/cancel. Distinct from requires_approval (a bool verdict) — this
    #   holds the action itself. None when nothing is awaiting confirmation.
    #   Shape: {"tool": str, "payload": dict, "prompt_shown": str}
    pending_approval: Optional[dict]

    # tool_result: result of the last executed connector. Filled by tool_node (Step 3).
    #   Shape: {"tool": str, "status": str, "output": <any>}
    tool_result: Optional[dict]

    # approval_verdict: set by approval_handler — "approved" / "rejected" / "unclear".
    #   Read by route_after_approval to choose the next edge. Transient per turn.
    approval_verdict: Optional[str]