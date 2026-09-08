# core/orchestration/nodes/tool_node.py
# Phase 5 — Steps 3c + 4b.
# Three branches:
#   1. Approved-run: approval_verdict == "approved" AND a parked action exists
#      -> run the parked action, consume pending_approval.
#   2. Park: chosen tool needs approval and is not yet approved
#      -> store in pending_approval, ask "Shall I proceed?", do NOT run.
#   3. Direct run: read-only tool -> run now.
# FIREWALL: tool_input comes from the orchestrator (Sir's words only) — no memory added.

from core.orchestration.state import AegonState
from core.orchestration.llm_client import call_llm
from core.research_notes import save_research_note
from tools import tool_registry
from tools.tool_logger import log_tool_call
from prompts.tool_node_prompt import TOOL_NODE_PROMPT


def _format_results(results) -> str:
    if not results:
        return "(No results.)"
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. {r.get('title','')}\n"
            f"   Source: {r.get('href','')}\n"
            f"   {r.get('body','')}"
        )
    return "\n\n".join(lines)


def _build_response(tool_name: str, tool_input: dict, result: dict) -> str:
    """Turn a tool result into Aegon's answer, based on the tool's response_style."""
    manifest = tool_registry.get_tool(tool_name) or {}
    style = manifest.get("response_style", "summarize")

    status = result.get("status")
    if status == "denied":
        return f"I cannot touch that location, Sir. {result.get('output','')}"
    if status == "no_results":
        return "I searched, Sir, but found nothing useful."
    if status != "success":
        return f"That did not work, Sir. {result.get('output','')}"

    if style == "raw":          # e.g. file_read — present content directly
        return f"Here is what I found, Sir:\n\n{result.get('output','')}"
    if style == "confirm":      # e.g. file_write — short confirmation
        return f"Done, Sir. {result.get('output','')}"
    if style == "verbatim":     # tool fully phrases its own output (e.g. gmail_read)
        return result.get("output", "")

    # default: summarize (e.g. web_search) — apply the honesty principles
    raw_results = result.get("output", [])
    results_text = _format_results(raw_results)
    query = tool_input.get("query", "")
    user_message = f"Sir's question: {query}\n\nSearch results:\n{results_text}"
    answer = call_llm(system_prompt=TOOL_NODE_PROMPT, user_message=user_message, temperature=0.3)

    # Link-bearing results are useless spoken — URLs are stripped before TTS anyway.
    # Save them where Sir can actually open them, and tell him where they went.
    note = save_research_note(query, raw_results, tool_name)
    if note:
        answer = f"{answer}\n\nI have put the links in a note for you, Sir: {note}"
    return answer


def _run_tool(tool_name, tool_input, approval_status, session_id, thread_id, decision_log):
    """Load, validate, execute. Returns (result, response)."""
    tool = tool_registry.get_tool_instance(tool_name)
    if tool is None:
        decision_log.append({"node": "tool_node", "tool": tool_name, "error": "tool not found/loadable"})
        return None, "That tool is not available, Sir."
    if not tool.validate(tool_input):
        safe_payload, _ = tool.redact_for_log(tool_input, {})
        log_tool_call(tool_name, safe_payload, {"status": "invalid_input"}, approval_status, session_id, thread_id)
        decision_log.append({"node": "tool_node", "tool": tool_name, "error": "invalid input"})
        return None, "The tool input was invalid, Sir."
    result = tool.execute(tool_input)
    # Let the connector redact anything sensitive before it hits the log.
    safe_payload, safe_result = tool.redact_for_log(tool_input, result)
    log_tool_call(tool_name, safe_payload, safe_result, approval_status, session_id, thread_id)
    return result, _build_response(tool_name, tool_input, result)


def tool_node(state: AegonState) -> AegonState:
    session_id = state.get("session_id", "")
    thread_id = state.get("thread_id", "")
    decision_log = state.get("decision_log") or []

    approval_verdict = state.get("approval_verdict")
    pending = state.get("pending_approval")

    # --- Branch 1: approved-run (needs BOTH the flag AND a real parked action) ---
    if approval_verdict == "approved" and pending:
        tool_name = pending.get("tool", "")
        tool_input = pending.get("tool_input") or {}
        result, response = _run_tool(tool_name, tool_input, "approved", session_id, thread_id, decision_log)
        decision_log.append({"node": "tool_node", "branch": "approved_run", "tool": tool_name})
        # Consume the parked action. Leave approval_verdict for governance THIS turn;
        # the orchestrator resets it to None next turn.
        return {
            **state,
            "worker_response": response,
            "tool_result": result,
            "pending_approval": None,
            "decision_log": decision_log,
            }

    # --- Read the orchestrator's chosen tool ---
    a2a_payload = state.get("a2a_payload") or {}
    tool_name = a2a_payload.get("tool_name", "")
    tool_input = a2a_payload.get("tool_input") or {}
    tool_calls = a2a_payload.get("tool_calls")

    # --- Branch 1b: multi-tool batch (read-only tools only) ---
    # Runs each non-gated tool in order and combines the answers. A gated tool is
    # NEVER auto-run inside a batch (Axiom 1) — it is reported as needing separate
    # approval. The single-tool path below is untouched when there is no batch.
    if isinstance(tool_calls, list) and len(tool_calls) > 1:
        responses = []
        results = []
        ran = []
        for call in tool_calls:
            cname = call.get("tool_name", "")
            cinput = call.get("tool_input") or {}
            if not cname or not tool_registry.get_tool(cname):
                continue
            if tool_registry.requires_approval(cname):
                responses.append(
                    f"{cname} needs your approval, Sir — ask me for that one on its own."
                )
                continue
            result, response = _run_tool(
                cname, cinput, "not_required", session_id, thread_id, decision_log
            )
            results.append(result)
            responses.append(response)
            ran.append(cname)
        decision_log.append({"node": "tool_node", "branch": "multi_run", "tools": ran})
        return {
            **state,
            "worker_response": "\n\n".join(responses),
            "tool_result": results,
            "decision_log": decision_log,
        }

    if not tool_name:
        decision_log.append({"node": "tool_node", "error": "no tool specified"})
        return {**state, "worker_response": "I was not sure which tool to use, Sir.", "decision_log": decision_log}

    # --- Branch 2: gated tool, not yet approved -> park and ask ---
    if tool_registry.requires_approval(tool_name):
        instance = tool_registry.get_tool_instance(tool_name)
        if instance is not None:
            prompt_shown = instance.approval_prompt(tool_input)
        else:
            prompt_shown = f"This will run {tool_name}. Shall I proceed, Sir?"
        decision_log.append({"node": "tool_node", "branch": "park", "tool": tool_name})
        return {
            **state,
            "pending_approval": {"tool": tool_name, "tool_input": tool_input, "prompt_shown": prompt_shown},
            "requires_approval": True,
            "worker_response": prompt_shown,
            "decision_log": decision_log,
        }

    # --- Branch 3: read-only tool -> run directly ---
    result, response = _run_tool(tool_name, tool_input, "not_required", session_id, thread_id, decision_log)
    decision_log.append({"node": "tool_node", "branch": "direct_run", "tool": tool_name})
    return {**state, "worker_response": response, "tool_result": result, "decision_log": decision_log}