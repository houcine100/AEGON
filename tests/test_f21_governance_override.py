# tests/test_f21_governance_override.py
# Deterministic proof of the F21 fix: governance Axiom 2 override for own-data intents.
# Covers: memory_query (original fix) + summarize_request + plan_request (F21 extension).
# Run from project root:
#   python -m tests.test_f21_governance_override
#
# The governance LLM is non-deterministic, so we do NOT call it. We stub
# call_llm to force a fixed verdict, then assert the override logic in
# governance_node reacts correctly. No network, no Groq, no DB.

import json
import sys

import core.orchestration.nodes.governance_node as gov
from core.security.governance_rules import BLOCKED_RESPONSE

KEPT_RESPONSE = "Sir, you usually work late, and you enjoy Daft Punk."

_failures = 0


def _stub_verdict(result: str, violated_axiom, reason: str) -> None:
    """Force governance_node's call_llm to return one fixed verdict."""
    verdict = json.dumps({
        "result": result,
        "violated_axiom": violated_axiom,
        "reason": reason,
    })
    gov.call_llm = lambda system_prompt, user_message, temperature: verdict


def _run(intent: str, worker_response: str, **extra) -> dict:
    state = {
        "intent": intent,
        "raw_input": "what do you know about me",
        "worker_response": worker_response,
        **extra,
    }
    return gov.governance_node(state)


def _check(name: str, condition: bool, detail: str) -> None:
    global _failures
    if condition:
        print(f"[PASS] {name}")
    else:
        _failures += 1
        print(f"[FAIL] {name} -> {detail}")


print("=" * 70)
print("F21 — governance memory_query override (deterministic)")
print("=" * 70)

# Case 1 — the fix fires: fail/axiom_2 on a memory_query is overridden to pass.
_stub_verdict("fail", "axiom_2", "This shares Sir's personal data.")
r = _run("memory_query", KEPT_RESPONSE)
_check(
    "Case 1: fail/axiom_2 + memory_query -> pass, response kept",
    r["governance_result"] == "pass"
    and r["worker_response"] == KEPT_RESPONSE
    and "Override" in r["governance_reason"],
    f"got result={r['governance_result']!r}, response={r['worker_response']!r}",
)

# Case 2 — scope: the SAME violation on a non-own-data intent still blocks.
# (F.3: intent changed conversation -> task; conversation is now own-data/Layer 1.)
_stub_verdict("fail", "axiom_2", "This shares personal data.")
r = _run("task", KEPT_RESPONSE)
_check(
    "Case 2: fail/axiom_2 + task -> still blocked",
    r["governance_result"] == "fail" and r["worker_response"] == BLOCKED_RESPONSE,
    f"got result={r['governance_result']!r}, response={r['worker_response']!r}",
)

# Case 3 — axiom scope: a memory_query fail on a DIFFERENT axiom still blocks.
# (F.3: tool payload added so the turn reaches Layer 3 — no-tool own-data turns
# are structurally passed and never consult the LLM.)
_stub_verdict("fail", "axiom_1", "This implies a real-world action without approval.")
r = _run("memory_query", KEPT_RESPONSE,
         a2a_payload={"receiver": "tool_node", "tool_name": "gmail_send"},
         requires_approval=True)
_check(
    "Case 3: fail/axiom_1 + memory_query -> still blocked",
    r["governance_result"] == "fail" and r["worker_response"] == BLOCKED_RESPONSE,
    f"got result={r['governance_result']!r}, response={r['worker_response']!r}",
)

# Case 4 — no false override: a clean pass on a memory_query stays a pass.
_stub_verdict("pass", None, "No violation.")
r = _run("memory_query", KEPT_RESPONSE)
_check(
    "Case 4: pass + memory_query -> pass, response kept",
    r["governance_result"] == "pass" and r["worker_response"] == KEPT_RESPONSE,
    f"got result={r['governance_result']!r}, response={r['worker_response']!r}",
)

# Case 5 — F21 extension: fail/axiom_2 on summarize_request is overridden.
_stub_verdict("fail", "axiom_2", "This shares personal data.")
r = _run("summarize_request", KEPT_RESPONSE)
_check(
    "Case 5: fail/axiom_2 + summarize_request -> pass, response kept",
    r["governance_result"] == "pass"
    and r["worker_response"] == KEPT_RESPONSE
    and "Override" in r["governance_reason"],
    f"got result={r['governance_result']!r}, response={r['worker_response']!r}",
)

# Case 6 — F21 extension: fail/axiom_2 on plan_request is overridden.
_stub_verdict("fail", "axiom_2", "This shares personal data.")
r = _run("plan_request", KEPT_RESPONSE)
_check(
    "Case 6: fail/axiom_2 + plan_request -> pass, response kept",
    r["governance_result"] == "pass"
    and r["worker_response"] == KEPT_RESPONSE
    and "Override" in r["governance_reason"],
    f"got result={r['governance_result']!r}, response={r['worker_response']!r}",
)

print("-" * 70)
if _failures == 0:
    print("ALL CASES PASSED")
    sys.exit(0)
else:
    print(f"{_failures} CASE(S) FAILED")
    sys.exit(1)
