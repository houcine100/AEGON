# core/orchestration/nodes/orchestrator_node.py
# Groq call #2 — decides which worker handles the request, builds the A2A payload.
# Phase 5 — Step 3b: can decide a task needs a tool, pick it from the registry,
# and build the tool input. The REGISTRY decides tool approval, never the LLM.

import json
from core.orchestration.state import AegonState
from core.orchestration.llm_client import call_llm
from core.protocols.a2a_schema import A2AMessage
from core.orchestration import referent_store
from prompts.orchestrator_prompt import build_orchestrator_prompt
from tools import tool_registry


VALID_RECEIVERS = [
    "conversation_node",
    "task_node",
    "tool_node",            # Phase 5 — Step 3b
    "memory_agent",
    "summarizer_agent",
    "planner_agent",
]

# Phase B5 / flag F33 — bare backreference words the orchestrator LLM is instructed
# to pass through literally (see orchestrator_prompt.py rule 11) rather than guess.
_PLACEHOLDER_WORDS = {"there", "that", "them", "it", "those", "this", "him", "her"}

# Heuristic field-name -> referent-type map, used only to prefer a same-type referent
# when one exists. Open string typing (Sir's call) — unmapped fields fall back to
# "most recent referent of any type", not to a hard failure.
_FIELD_TYPE_HINTS = {
    "location": "place", "place": "place", "city": "place",
    "area": "place", "timezone": "place", "destination": "place",
    "artist": "artist", "band": "artist", "singer": "artist",
    "repo": "repo", "repository": "repo",
    "note": "note", "title": "note",
    "person": "person", "contact": "person", "recipient": "person",
}


def _resolve_placeholders(tool_input: dict, session_id: str) -> dict:
    """Replace bare backreference words in tool_input with the latest matching
    referent (tool_result provenance only). Leaves the word as-is — same as
    today's behavior — when nothing in the store matches, so this never
    regresses a turn that would have worked before."""
    if not isinstance(tool_input, dict):
        return tool_input
    resolved = dict(tool_input)
    for key, value in tool_input.items():
        if not isinstance(value, str) or value.strip().lower() not in _PLACEHOLDER_WORDS:
            continue
        type_hint = _FIELD_TYPE_HINTS.get(key.lower())
        referent = referent_store.latest(session_id, type_=type_hint)
        if referent is None and type_hint is not None:
            referent = referent_store.latest(session_id, type_=None)
        if referent is not None:
            resolved[key] = referent.value
    return resolved


def _store_referents(raw_referents, session_id: str) -> None:
    """Persist entities the orchestrator LLM flagged this turn (rule 11), tagged
    tool_result provenance — these values were already built into a validated
    tool_input, so reusing them later leaks nothing new. Capped and sanitized;
    a malformed or oversized list is silently dropped, not partially trusted."""
    if not isinstance(raw_referents, list):
        return
    for item in raw_referents[:4]:
        if not isinstance(item, dict):
            continue
        type_ = item.get("type")
        value = item.get("value")
        if isinstance(type_, str) and isinstance(value, str) and type_.strip() and value.strip():
            referent_store.add(session_id, value.strip(), type_.strip(), provenance="tool_result")


def orchestrator_node(state: AegonState) -> AegonState:
    raw_input = state.get("raw_input", "")
    intent = state.get("intent", "conversation")
    confidence = state.get("confidence", 0.0)
    session_id = state.get("session_id", "")
    decision_log = state.get("decision_log") or []

    # FIREWALL: the orchestrator sees only the intent and Sir's words.
    # Memory context is NOT passed in, so it can never leak into a tool query.
    user_message = f"Intent: {intent}\nUser input: {raw_input}"

    raw_response = call_llm(
        system_prompt=build_orchestrator_prompt(),
        user_message=user_message,
        temperature=0.1,
    )

    tool_name = ""
    tool_input = None
    tool_calls = None
    referents = None

    try:
        parsed = json.loads(raw_response)
        receiver = parsed.get("receiver", "conversation_node")
        payload = parsed.get("payload", raw_input)
        requires_approval = bool(parsed.get("requires_approval", False))
        tool_name = parsed.get("tool_name", "") or ""
        tool_input = parsed.get("tool_input", None)
        tool_calls = parsed.get("tool_calls", None)
        referents = parsed.get("referents", None)

        if receiver not in VALID_RECEIVERS:
            receiver = "conversation_node"
    except (json.JSONDecodeError, ValueError):
        receiver = "conversation_node"
        payload = raw_input
        requires_approval = False
        tool_name = ""
        tool_input = None
        tool_calls = None
        referents = None

    # --- Tool routing: the REGISTRY is the source of truth ---
    if receiver == "tool_node":
        # Bug 1b: validate a multi-tool batch. Keep only known tools; coerce each
        # input the same way single tools are coerced. If fewer than two survive,
        # drop the batch and fall through to the single-tool path below.
        if isinstance(tool_calls, list):
            clean_calls = []
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                cname = call.get("tool_name", "") or ""
                if not tool_registry.get_tool(cname):
                    continue
                cinput = call.get("tool_input", None)
                if not isinstance(cinput, dict):
                    cinput = {"query": payload}
                cinput = {k: v for k, v in cinput.items() if not isinstance(v, dict)}
                cinput = _resolve_placeholders(cinput, session_id)
                clean_calls.append({"tool_name": cname, "tool_input": cinput})
            tool_calls = clean_calls if len(clean_calls) >= 2 else None
            # When a valid batch exists, mirror its first element into the single
            # fields so the rest of this node and downstream readers stay consistent.
            if tool_calls:
                tool_name = tool_calls[0]["tool_name"]
                tool_input = tool_calls[0]["tool_input"]

        manifest = tool_registry.get_tool(tool_name)
        if not manifest:
            # Unknown or disabled tool — fail closed. Do not route to a tool.
            decision_log.append({
                "node": "orchestrator_node",
                "warning": f"Picked unknown/disabled tool '{tool_name}' — falling back.",
            })
            receiver = "conversation_node"
            tool_name = ""
            tool_input = None
            tool_calls = None
            requires_approval = False
        else:
            # Approval comes from the registry, never from the LLM.
            requires_approval = tool_registry.requires_approval(tool_name)
            if not isinstance(tool_input, dict):
                tool_input = {"query": payload}
            # Structural backstop (F22): the LLM sometimes echoes a field's SCHEMA
            # (e.g. {"type": "string", "required": false, ...}) as the value instead
            # of a real input. Every real tool input is a flat scalar, so drop any
            # dict-valued field before it reaches the tool.
            tool_input = {k: v for k, v in tool_input.items() if not isinstance(v, dict)}
            # Phase B5 / F33: resolve bare backreferences ("there", "that", ...)
            # against the referent store before the tool call goes out.
            tool_input = _resolve_placeholders(tool_input, session_id)
            # Referents named THIS turn are stored for FUTURE turns, after
            # resolution so a turn never resolves against its own new referent.
            _store_referents(referents, session_id)

    a2a_message = A2AMessage(
        sender="orchestrator_node",
        receiver=receiver,
        intent=intent,
        payload=payload,
        session_id=session_id,
        confidence=confidence,
        requires_approval=requires_approval,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_calls=tool_calls,
    )

    decision_log.append({
        "node": "orchestrator_node",
        "intent_received": intent,
        "receiver_decided": receiver,
        "payload": payload,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_calls": tool_calls,
        "referents": referents,
        "requires_approval": requires_approval,
        "raw_groq_response": raw_response,
    })

    return {
        **state,
        "a2a_payload": a2a_message.to_dict(),
        "requires_approval": requires_approval,
        "decision_log": decision_log,
    }