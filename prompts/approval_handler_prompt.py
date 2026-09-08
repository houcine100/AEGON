# prompts/approval_handler_prompt.py
# Used by the approval_handler node.
# The system prompt is the LLM FALLBACK only — invoked when deterministic
# keyword matching cannot classify Sir's reply. Keyword sets are checked first.

APPROVAL_HANDLER_SYSTEM_PROMPT = """You are Aegon's approval interpreter.

Sir was asked to confirm a pending action. Classify Sir's reply into exactly one verdict:

- APPROVE  — Sir agrees / wants the action to proceed.
- REJECT   — Sir declines / does not want the action.
- UNCLEAR  — the reply does not clearly approve or reject (a question, a change of
             subject, hesitation, or anything unrelated).

Rules:
- Judge ONLY whether Sir approves or rejects THIS action.
- When in doubt between APPROVE and UNCLEAR, choose UNCLEAR.
- Never approve a real-world action on an ambiguous reply.

Respond with exactly one word: APPROVE, REJECT, or UNCLEAR."""


# The user message sent to the LLM is built from the pending action + Sir's reply.
def build_approval_user_message(pending_summary: str, reply: str) -> str:
    return (
        f"The pending action was:\n{pending_summary}\n\n"
        f'Sir\'s reply was:\n"{reply}"'
    )


# Deterministic keyword sets — checked BEFORE any LLM call.
# Generous on purpose: clear replies should never reach the LLM.
# REJECT is checked first everywhere — fail closed on conflict.
APPROVE_KEYWORDS = frozenset({
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "proceed",
    "go ahead", "do it", "confirmed", "confirm", "approve", "approved",
    "go", "affirmative", "please do",
})

REJECT_KEYWORDS = frozenset({
    "no", "nope", "stop", "cancel", "cancelled", "abort", "don't",
    "do not", "forget it", "never mind", "nevermind", "reject",
    "negative", "hold off", "not now",
})