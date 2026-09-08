# core/orchestration/nodes/approval_handler.py
# Phase 5 — Step 1.
# Runs ONLY when state["pending_approval"] is set — route_after_classifier
# short-circuits to this node before intent is considered.
#
# Job: interpret Sir's reply against the parked action.
#   approved -> clear requires_approval; KEEP pending_approval for tool_node (Step 3)
#   rejected -> clear pending_approval + requires_approval; tell Sir
#   unclear  -> fail closed: keep the action parked, ask again
#
# Deterministic keyword match first. LLM fallback only for ambiguous replies.
# Never approves on an ambiguous reply (Axiom 1).

from core.orchestration.state import AegonState
from core.orchestration.llm_client import call_llm
from core.memory.memory_store import update_fact_status
from prompts.approval_handler_prompt import (
    APPROVAL_HANDLER_SYSTEM_PROMPT,
    build_approval_user_message,
    APPROVE_KEYWORDS,
    REJECT_KEYWORDS,
)


def _normalise(text: str) -> str:
    return (text or "").strip().lower().rstrip(".!?,")


def _keyword_verdict(reply: str):
    """Return 'approved' / 'rejected' / None. None means escalate to the LLM.
    REJECT is checked first everywhere — fail closed on conflict."""
    norm = _normalise(reply)
    if not norm:
        return None
    if norm in REJECT_KEYWORDS:
        return "rejected"
    if norm in APPROVE_KEYWORDS:
        return "approved"
    if any(kw in norm for kw in REJECT_KEYWORDS):
        return "rejected"
    if any(kw in norm for kw in APPROVE_KEYWORDS):
        return "approved"
    return None


def _llm_verdict(reply: str, pending: dict) -> str:
    """Escalate ambiguous replies to the LLM. Returns approved/rejected/unclear."""
    pending_summary = pending.get("prompt_shown") or str(pending.get("payload", {}))
    user_message = build_approval_user_message(pending_summary, reply)
    raw = call_llm(APPROVAL_HANDLER_SYSTEM_PROMPT, user_message, temperature=0.2).upper()
    if "APPROVE" in raw:
        return "approved"
    if "REJECT" in raw:
        return "rejected"
    return "unclear"   # fail closed on anything else


def approval_handler(state: AegonState) -> AegonState:
    decision_log = state.get("decision_log") or []
    pending = state.get("pending_approval")
    reply = state.get("raw_input", "")

    # Defensive: should never run without a parked action. Surface the bug, act on nothing.
    if not pending:
        decision_log.append({
            "node": "approval_handler",
            "verdict": "no_pending_action",
            "reason": "Ran with no pending_approval — routing bug.",
        })
        return {
            **state,
            "approval_verdict": "unclear",
            "worker_response": "I have nothing awaiting your confirmation, Sir.",
            "governance_result": "pass",
            "governance_reason": "Approval handler — no axiom check needed.",
            "decision_log": decision_log,
        }

    verdict = _keyword_verdict(reply)
    if verdict is None:
        verdict = _llm_verdict(reply, pending)

    tool_name = pending.get("tool", "unknown")

    if verdict == "approved":
        action_type = pending.get("action_type")

        if action_type == "memory_delete":
            # Resolve EVERY parked fact. Fall back to the single-fact fields for
            # backward compatibility with actions parked before multi-delete.
            fact_ids = pending.get("fact_ids") or [pending.get("fact_id")]
            fact_texts = pending.get("fact_texts") or [pending.get("fact_text", "unknown")]
            for fid in fact_ids:
                update_fact_status(
                    record_id=fid,
                    status="resolved",
                    resolution_notes="Removed by Sir's explicit request.",
                )
            if len(fact_ids) == 1:
                response = f"Done, Sir. I have removed from memory: '{fact_texts[0]}'"
            else:
                response = f"Done, Sir. I have removed {len(fact_ids)} memories from my records."
            decision_log.append({
                "node": "approval_handler", "verdict": "approved_executed",
                "action_type": "memory_delete", "fact_id": fact_ids[0],
                "fact_ids": fact_ids, "reply": reply,
            })
            return {
                **state,
                "approval_verdict": "completed",
                "pending_approval": None,
                "requires_approval": False,
                "worker_response": response,
                "governance_result": "pass",
                "governance_reason": "Memory delete confirmed and executed by Sir.",
                "decision_log": decision_log,
            }

        decision_log.append({
            "node": "approval_handler", "verdict": "approved",
            "tool": tool_name, "reply": reply,
        })
        # KEEP pending_approval — tool_node (Step 3) consumes it to execute.
        return {
            **state,
            "approval_verdict": "approved",
            "requires_approval": False,
            "decision_log": decision_log,
        }

    if verdict == "rejected":
        decision_log.append({
            "node": "approval_handler", "verdict": "rejected",
            "tool": tool_name, "reply": reply,
        })
        return {
            **state,
            "approval_verdict": "rejected",
            "pending_approval": None,
            "requires_approval": False,
            # Never name the internal tool/agent here — {tool_name} is an implementation
            # identifier ("memory_agent", "spotify_play"), not something Sir should hear.
            "worker_response": (
                "Understood, Sir. I have left it in memory."
                if pending.get("action_type") == "memory_delete"
                else "Understood, Sir. I have not done that."
            ),
            "governance_result": "pass",
            "governance_reason": "Action rejected by Sir — nothing executed.",
            "decision_log": decision_log,
        }

    # UNCLEAR — fail closed: keep parked, ask again.
    decision_log.append({
        "node": "approval_handler", "verdict": "unclear",
        "tool": tool_name, "reply": reply,
    })
    prompt_shown = pending.get("prompt_shown", "Shall I proceed?")
    return {
        **state,
        "approval_verdict": "unclear",
        "worker_response": (
            f"I did not catch a clear yes or no, Sir. {prompt_shown} "
            "Say 'yes' to proceed or 'no' to cancel."
        ),
        "governance_result": "pass",
        "governance_reason": "Awaiting clear confirmation — nothing executed.",
        "decision_log": decision_log,
    }