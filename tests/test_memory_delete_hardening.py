# tests/test_memory_delete_hardening.py
# Deterministic proof of the memory-delete hardening (no LLM / no Groq needed):
#   1. Multi-fact delete: "delete everything about X" parks ALL matches and the
#      approval handler resolves every one of them.
#   2. Threshold: matches below the similarity floor are ignored.
#   3. Extraction gate: command/control intents are excluded from fact extraction,
#      so asking to forget can never create a memory.

from unittest.mock import patch

from agents.memory_agent.memory_agent import memory_agent, DELETE_SIMILARITY_THRESHOLD
from core.orchestration.nodes.approval_handler import approval_handler
from schemas.intent_schema import Intent


def _state(raw_input, intent=Intent.MEMORY_DELETE, pending=None):
    return {
        "raw_input": raw_input,
        "intent": intent,
        "a2a_payload": {"payload": raw_input},
        "memory_context": "",
        "conversation_history": "",
        "session_id": "test",
        "decision_log": [],
        "pending_approval": pending,
    }


TWO_FACTS = [
    {"id": "fact-A", "fact": "Sir drives a black Tesla Model 3.", "similarity": 0.91},
    {"id": "fact-B", "fact": "Sir's Tesla needs new tires.", "similarity": 0.78},
]


def test_multi_delete_parks_all_matches():
    with patch("agents.memory_agent.memory_agent.search_facts", return_value=TWO_FACTS):
        result = memory_agent(_state("delete everything you know about my Tesla"))
    pending = result["pending_approval"]
    assert pending["action_type"] == "memory_delete"
    assert pending["fact_ids"] == ["fact-A", "fact-B"]
    assert "2 memories" in result["worker_response"]
    assert "black Tesla" in result["worker_response"]
    assert "new tires" in result["worker_response"]


def test_multi_delete_resolves_every_fact():
    with patch("agents.memory_agent.memory_agent.search_facts", return_value=TWO_FACTS):
        parked = memory_agent(_state("wipe what you know about my Tesla"))
    pending = parked["pending_approval"]

    calls = []
    with patch(
        "core.orchestration.nodes.approval_handler.update_fact_status",
        side_effect=lambda record_id, status, resolution_notes: calls.append((record_id, status)),
    ):
        result = approval_handler(_state("yes", intent=Intent.MEMORY_DELETE, pending=pending))

    assert [c[0] for c in calls] == ["fact-A", "fact-B"]
    assert all(c[1] == "resolved" for c in calls)
    assert result["approval_verdict"] == "completed"
    assert "2 memories" in result["worker_response"]


def test_below_threshold_is_ignored():
    weak = [{"id": "fact-Z", "fact": "loosely related note", "similarity": DELETE_SIMILARITY_THRESHOLD - 0.05}]
    with patch("agents.memory_agent.memory_agent.search_facts", return_value=weak):
        result = memory_agent(_state("delete my banking details"))
    assert result.get("pending_approval") is None
    assert "could not find" in result["worker_response"].lower()


def test_command_intents_excluded_from_extraction():
    from apps.orchestrator.aegon_orchestrator import _NON_EXTRACTABLE_INTENTS
    assert Intent.MEMORY_DELETE in _NON_EXTRACTABLE_INTENTS
    assert Intent.MEMORY_QUERY in _NON_EXTRACTABLE_INTENTS
    assert Intent.MODE_SWITCH in _NON_EXTRACTABLE_INTENTS
    # Informational intents must NOT be excluded.
    assert Intent.CONVERSATION not in _NON_EXTRACTABLE_INTENTS
