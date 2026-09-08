# core/orchestration/nodes/governance_node.py
# Three-layer governance (Phase F.3).
#   Layer 1 — structural rules, no LLM: state facts that make a violation impossible.
#   Layer 2 — pattern matching, no LLM: unambiguous violation phrases.
#   Layer 3 — LLM judgment (Groq): only for genuinely ambiguous turns.
# Blocks the response if any axiom is violated.
# Writes governance_result and governance_reason back to AegonState.

import json
from core.orchestration.state import AegonState
from core.orchestration.llm_client import call_llm
from prompts.governance_prompt import GOVERNANCE_PROMPT
from core.security.governance_rules import AXIOM_SEVERITY, SEVERITY_BLOCK, BLOCKED_RESPONSE

# Intents where Sir is reading or reasoning over his OWN data. Single-user system:
# when no tool ran, the answer goes only to Sir and no real-world action occurred —
# no axiom can be violated, so the LLM is never consulted (F21 made structural).
_OWN_DATA_INTENTS = {"memory_query", "summarize_request", "plan_request", "conversation"}

# Layer 2 — Axiom 3: first-person, affirmative capitulation only. Refusals
# ("I will not ignore my rules") must NOT match — every phrase asserts compliance
# with an override, not rejection of one.
_AXIOM_3_PATTERNS = (
    "i will ignore my rules",
    "i am ignoring my rules",
    "i have ignored my rules",
    "i will override my rules",
    "i have overridden my rules",
    "i will bypass my constraints",
    "i have bypassed my constraints",
    "my rules no longer apply",
    "i will disable my safety",
    "i have disabled my safety",
)


def _finish(state: AegonState, decision_log: list, *, layer: str, result: str,
            violated_axiom, reason: str, worker_response: str,
            final_response: str, raw_llm_response: str = "") -> AegonState:
    decision_log.append({
        "node": "governance_node",
        "layer": layer,
        "result": result,
        "violated_axiom": violated_axiom,
        "reason": reason,
        "original_response": worker_response,
        "final_response_after_governance": final_response,
        "raw_groq_response": raw_llm_response,
    })
    return {
        **state,
        "worker_response": final_response,
        "governance_result": result,
        "governance_reason": reason,
        "decision_log": decision_log,
    }


def governance_node(state: AegonState) -> AegonState:
    worker_response = state.get("worker_response", "")
    raw_input = state.get("raw_input", "")
    decision_log = state.get("decision_log") or []
    intent = state.get("intent", "conversation")

    a2a_payload = state.get("a2a_payload") or {}
    receiver = a2a_payload.get("receiver", "")
    tool_name = a2a_payload.get("tool_name", "")
    requires_approval = state.get("requires_approval", False)
    approval_verdict = state.get("approval_verdict")
    used_tool = receiver == "tool_node" and bool(tool_name)

    # ── Layer 1 — structural rules (no LLM) ─────────────────────────────────
    if state.get("pending_approval"):
        return _finish(
            state, decision_log, layer="structural", result="pass",
            violated_axiom=None,
            reason="Layer 1 structural pass: Aegon is asking Sir for approval — "
                   "no action taken, Axiom 1 cannot be violated.",
            worker_response=worker_response, final_response=worker_response,
        )

    if intent in _OWN_DATA_INTENTS and not used_tool:
        return _finish(
            state, decision_log, layer="structural", result="pass",
            violated_axiom=None,
            reason=f"Override (Layer 1 structural): {intent} is Sir's own data, "
                   "no tool used — axioms structurally satisfied, LLM not consulted.",
            worker_response=worker_response, final_response=worker_response,
        )

    # ── Layer 2 — pattern matching (no LLM) ─────────────────────────────────
    response_lower = worker_response.lower()

    for pattern in _AXIOM_3_PATTERNS:
        if pattern in response_lower:
            return _finish(
                state, decision_log, layer="pattern", result="fail",
                violated_axiom="axiom_3",
                reason=f"Layer 2 pattern block: response capitulates to a rule "
                       f"override ('{pattern}').",
                worker_response=worker_response, final_response=BLOCKED_RESPONSE,
            )

    if approval_verdict == "approved":
        return _finish(
            state, decision_log, layer="pattern", result="pass",
            violated_axiom=None,
            reason="Layer 2 pass: action explicitly approved by Sir and no "
                   "violation pattern found — LLM not consulted.",
            worker_response=worker_response, final_response=worker_response,
        )

    # ── Layer 3 — LLM judgment (ambiguous turns only) ───────────────────────
    if used_tool and not requires_approval:
        action_context = (
            f"The response used the read-only tool '{tool_name}', which required NO approval. "
            f"Read-only tool use is pre-cleared and is NOT an Axiom 1 violation."
        )
    else:
        action_context = "No external tool was used."

    user_message = (
        f"Intent: {intent}\n"
        f"User input: {raw_input}\n"
        f"Action context: {action_context}\n"
        f"Proposed response: {worker_response}"
    )

    raw_response = call_llm(
        system_prompt=GOVERNANCE_PROMPT,
        user_message=user_message,
        temperature=0.1,
    )

    try:
        parsed = json.loads(raw_response)
        result = parsed.get("result", "pass")
        violated_axiom = parsed.get("violated_axiom", None)
        reason = parsed.get("reason", "")

        if result not in ["pass", "fail"]:
            result = "pass"
            violated_axiom = None
            reason = "Governance parse fallback — defaulting to pass."

    except (json.JSONDecodeError, ValueError):
        result = "pass"
        violated_axiom = None
        reason = "Governance parse error — defaulting to pass."
        raw_response = ""

    final_response = worker_response
    if result == "fail" and violated_axiom:
        # Backstop for LLM misfires: an own-data turn (answer goes only to Sir)
        # can never leak to a third party, so Axiom 2 cannot apply.
        if violated_axiom == "axiom_2" and intent in _OWN_DATA_INTENTS:
            result = "pass"
            violated_axiom = None
            reason = f"Override: {intent} is Sir's own data — Axiom 2 does not apply."
        else:
            severity = AXIOM_SEVERITY.get(violated_axiom, SEVERITY_BLOCK)
            if severity == SEVERITY_BLOCK:
                final_response = BLOCKED_RESPONSE

    return _finish(
        state, decision_log, layer="llm", result=result,
        violated_axiom=violated_axiom, reason=reason,
        worker_response=worker_response, final_response=final_response,
        raw_llm_response=raw_response,
    )
