# apps/orchestrator/aegon_orchestrator.py
# Phase 4 entry point.
# Receives callback from session_logger.
# Starts the LangGraph state machine.
# Maintains conversation history and active mode across turns.
# Triggers real-time fact extraction after every turn.

import os
import sys
import uuid
import threading

# Windows' default console codec (cp1252) cannot encode many characters an LLM
# may produce (e.g. U+2011 non-breaking hyphen) — without this, printing such a
# response crashes the whole process, not just that turn.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
from core.orchestration.graph import build_graph
from core.orchestration.checkpointer import get_checkpointer
from core.orchestration.state import AegonState
from core.observability.decision_logger import log_decision
from core.memory.context_injector import build_memory_context, build_session_context
from core.memory.inference_engine import maybe_run_inference
from core.memory.fact_extractor import extract_and_store_from_turns
from core.reminders.reminder_watcher import start_watcher
from core.modes.morning_briefing import start_briefing_async
from core.modes.mode_detector import infer_mode_from_context
from core.memory.vault_sync import sync_vault_to_memory
from core.sentinel import sentinel
from core.sentinel.proactive_queue import drain as drain_sentinel_queue, format_findings_for_speech
from core.voice.speak import speak
from prompts.mode_prompts import Mode


# --- Build graph with persistent checkpointer ---
_checkpointer = get_checkpointer()
_graph = build_graph(checkpointer=_checkpointer)

# --- Session ID ---
SESSION_ID = str(uuid.uuid4())

# --- Active mode ---
# Persisted across turns in this session.
# Defaults to standard. Updated by mode_switch_node.
_active_mode: str = Mode.DEFAULT

# --- Conversation history ---
# Maintained across turns in this session.
# Stores last 6 turns (3 exchanges) as plain text.
MAX_HISTORY_TURNS = 6
_conversation_history: list = []

# --- Recent turns for fact extraction ---
_recent_turns_buffer: list = []
_buffer_lock = threading.Lock()
_extraction_threads: list = []
_threads_lock = threading.Lock()

# Intents that are commands, ratings, or read-backs — never a fact about Sir.
# Turns with these intents are excluded from fact extraction (Root cause of the
# "asking to forget creates a memory" bug). Only informational turns are mined.
_NON_EXTRACTABLE_INTENTS = {
    "memory_query",
    "memory_delete",
    "note_remember",
    "mode_switch",
    "finding_feedback",
    "rule_override_attempt",
    "clarification_needed",
}

# --- Pending approval (Phase 5 — Step 1) ---
# Carries the parked action across turns, the same way mode and history are carried.
# None when nothing is awaiting Sir's yes/no.
_pending_approval: dict = None

def _format_history(history: list) -> str:
    """Formats conversation history as plain text for injection into nodes."""
    if not history:
        return ""
    return "\n".join(history)


def _update_history(user_input: str, aegon_response: str) -> None:
    """Adds a new exchange to conversation history. Trims to MAX_HISTORY_TURNS."""
    global _conversation_history
    _conversation_history.append(f"Sir: {user_input}")
    _conversation_history.append(f"Aegon: {aegon_response}")
    if len(_conversation_history) > MAX_HISTORY_TURNS:
        _conversation_history = _conversation_history[-MAX_HISTORY_TURNS:]


def _add_to_extraction_buffer(user_input: str, aegon_response: str) -> None:
    """Adds a turn to the extraction buffer for real-time fact extraction."""
    with _buffer_lock:
        _recent_turns_buffer.append({
            "type": "turn",
            "speaker": "user",
            "text": user_input,
        })
        _recent_turns_buffer.append({
            "type": "turn",
            "speaker": "aegon",
            "text": aegon_response,
        })


def _run_fact_extraction() -> None:
    """Runs fact extraction in background — does not block conversation."""
    with _buffer_lock:
        turns_to_process = list(_recent_turns_buffer)
        _recent_turns_buffer.clear()   # F16: extract each turn once; don't reprocess the whole session

    if not turns_to_process:
        return
    def extract():
        try:
            count = extract_and_store_from_turns(turns_to_process)
            if count > 0:
                print(f"[orchestrator] Extracted {count} new facts.")
        except Exception as e:
            print(f"[orchestrator] Fact extraction failed: {e}")

    thread = threading.Thread(target=extract, daemon=True)
    with _threads_lock:
        _extraction_threads.append(thread)
    thread.start()


def drain_extraction_threads(timeout: float = 120.0) -> None:
    """Join all pending extraction threads. For use in tests only."""
    with _threads_lock:
        threads = list(_extraction_threads)
        _extraction_threads.clear()
    for t in threads:
        t.join(timeout=timeout)


def _run_turn(transcribed_text: str, thread_id: str = None) -> dict:
    """
    Runs the full LangGraph state machine for one turn.
    Returns {response, intent, requires_approval, thread_id}.
    Single source of truth for both the CLI (string) and web (rich) entry points.
    """
    global _active_mode, _pending_approval

    if not thread_id:
        thread_id = str(uuid.uuid4())

    # Inject memory context and session context from Tier 3
    try:
        memory_context = build_memory_context(transcribed_text)
        session_ctx = build_session_context(transcribed_text)
        if session_ctx:
            memory_context = (memory_context + "\n\n" + session_ctx) if memory_context else session_ctx
    except Exception as e:
        print(f"[orchestrator] Memory context injection failed: {e}")
        memory_context = None

    conversation_history = _format_history(_conversation_history)

    initial_state: AegonState = {
        "session_id": SESSION_ID,
        "thread_id": thread_id,
        "raw_input": transcribed_text,
        "active_mode": _active_mode,
        "conversation_history": conversation_history,
        "intent": None,
        "confidence": None,
        "requested_mode": None,
        "a2a_payload": None,
        "worker_response": None,
        "governance_result": None,
        "governance_reason": None,
        "requires_approval": None,
        "final_response": None,
        "decision_log": [],
        "memory_context": memory_context,
        "pending_approval": _pending_approval,
        "tool_result": None,
        "approval_verdict": None,
    }

    config = {"configurable": {"thread_id": thread_id}}

    try:
        if _checkpointer:
            result = _graph.invoke(initial_state, config=config)
        else:
            result = _graph.invoke(initial_state)
    except Exception as e:
        print(f"[orchestrator] Graph invocation failed: {e}")
        return {
            "response": "Something went wrong, Sir. I was unable to process that.",
            "intent": None,
            "requires_approval": False,
            "thread_id": thread_id,
        }

    final_response = result.get("final_response", "")

    new_mode = result.get("active_mode")
    if new_mode and new_mode != _active_mode:
        _active_mode = new_mode
        print(f"[orchestrator] Mode switched to: {_active_mode}")

    _pending_approval = result.get("pending_approval")

    _update_history(transcribed_text, final_response)

    # F16: only mint facts from turns where Sir is actually sharing personal info.
    # Skip command/control intents (he's issuing an instruction or reading his own data
    # back — not stating a fact) and tool turns (the response is external content —
    # search results, playback, etc. — not a fact about Sir).
    _a2a = result.get("a2a_payload") or {}
    _used_tool = bool(result.get("tool_result")) or _a2a.get("receiver") == "tool_node"
    if result.get("intent") not in _NON_EXTRACTABLE_INTENTS and not _used_tool:
        _add_to_extraction_buffer(transcribed_text, final_response)
        _run_fact_extraction()

    # B1: update project models in background after every non-tool turn
    if not _used_tool:
        try:
            import threading
            from core.memory.project_model_updater import maybe_update_project_models
            threading.Thread(
                target=maybe_update_project_models,
                args=(transcribed_text, final_response),
                daemon=True,
                name="project-model-updater",
            ).start()
        except Exception as e:
            print(f"[orchestrator] Project model updater failed to start: {e}")

    try:
        log_decision(result)
    except Exception as e:
        print(f"[orchestrator] Decision logging failed: {e}")

    return {
        "response": final_response,
        "intent": result.get("intent"),
        "requires_approval": bool(result.get("requires_approval"))
        or _pending_approval is not None,
        "thread_id": thread_id,
    }


def on_user_turn_complete(transcribed_text: str, thread_id: str = None) -> str:
    """Legacy string entry point (CLI/voice). Returns the response text only."""
    return _run_turn(transcribed_text, thread_id)["response"]


def on_user_turn_complete_rich(transcribed_text: str, thread_id: str = None) -> dict:
    """Web entry point. Returns {response, intent, requires_approval, thread_id}."""
    return _run_turn(transcribed_text, thread_id)


def start(thread_id: str = None) -> None:
    """
    Starts Aegon in interactive text mode for testing.
    Type your input. Press Enter. Aegon responds.
    Type 'exit' to quit.
    """
    global _active_mode
    _active_mode = infer_mode_from_context()

    start_watcher()
    sentinel.start()
    sync_vault_to_memory()
    maybe_run_inference()

    if _active_mode == "morning":
        start_briefing_async()
    else:
        findings = drain_sentinel_queue(max_items=3)
        if findings:
            speak(format_findings_for_speech(findings))

    print("Aegon Phase 4 — Multi-Agent Orchestrator")
    print(f"Active mode: {_active_mode}")
    print("Type your input. Press Enter. Type 'exit' to quit.")
    print("-" * 50)

    session_thread_id = thread_id or str(uuid.uuid4())

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nShutting down, Sir.")
            break

        if not user_input:
            continue

        if user_input.lower() == "exit":
            print("Shutting down, Sir.")
            break

        response = on_user_turn_complete(user_input, thread_id=session_thread_id)
        print(f"Aegon: {response}\n")


if __name__ == "__main__":
    start()