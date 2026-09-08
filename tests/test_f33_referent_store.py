# tests/test_f33_referent_store.py
# Flag F33 / Phase B5 gate — typed referent store + orchestrator_node wiring.
# Fully mocked — no LLM, no live connectors, no real clock.
#
#   1. referent_store: add/latest, type filter, provenance gate, capacity eviction, TTL.
#   2. orchestrator_node: a turn that names a place stores it (tool_result provenance).
#   3. orchestrator_node: a later turn's bare "there" resolves against that referent.
#   4. Provenance gate: a memory-provenance referent is never returned by latest()
#      even when a caller does not explicitly filter it out — fails closed by default.
#   5. No regression: a bare word with nothing in the store is passed through unchanged,
#      same as today's behavior.

import json
import time
from unittest.mock import patch

from core.orchestration import referent_store
from core.orchestration.nodes.orchestrator_node import orchestrator_node


def _state(raw_input, session_id="test-session"):
    return {
        "raw_input": raw_input,
        "intent": "task",
        "confidence": 0.95,
        "session_id": session_id,
        "thread_id": "test",
        "decision_log": [],
        "a2a_payload": None,
        "approval_verdict": None,
        "pending_approval": None,
    }


def setup_function(_):
    # Each test gets a clean store — sessions are keyed by session_id, and tests
    # reuse a small set of ids, so clear between tests to avoid cross-test bleed.
    referent_store.clear_session("test-session")
    referent_store.clear_session("test-session-2")


# ── referent_store: unit behavior ───────────────────────────────────────────────

def test_add_and_latest_basic():
    referent_store.add("test-session", "Tunisia", "place", provenance="tool_result")
    r = referent_store.latest("test-session")
    assert r is not None
    assert r.value == "Tunisia"
    assert r.type == "place"


def test_latest_filters_by_type():
    referent_store.add("test-session", "Tunisia", "place", provenance="tool_result")
    referent_store.add("test-session", "Radiohead", "artist", provenance="tool_result")
    assert referent_store.latest("test-session", type_="artist").value == "Radiohead"
    assert referent_store.latest("test-session", type_="place").value == "Tunisia"
    assert referent_store.latest("test-session", type_="repo") is None


def test_latest_returns_most_recent_of_type():
    referent_store.add("test-session", "Tunisia", "place", provenance="tool_result")
    referent_store.add("test-session", "Montreal", "place", provenance="tool_result")
    assert referent_store.latest("test-session", type_="place").value == "Montreal"


def test_provenance_gate_blocks_memory_by_default():
    # Directly seed a memory-provenance referent (no code path does this yet —
    # this simulates one existing to prove the gate, not starvation, is what blocks it).
    referent_store.add("test-session", "Sir's home address", "place", provenance="memory")
    assert referent_store.latest("test-session", type_="place") is None
    # Explicitly widening the allow-list is the only way to see it — proves the
    # gate is opt-in-to-trust, not opt-out-to-block.
    r = referent_store.latest("test-session", type_="place", allowed_provenance=("tool_result", "memory"))
    assert r is not None
    assert r.value == "Sir's home address"


def test_capacity_eviction_keeps_bound():
    for i in range(referent_store.MAX_REFERENTS_PER_SESSION + 3):
        referent_store.add("test-session", f"place-{i}", "place", provenance="tool_result")
    # newest survives, store never grows past the bound
    assert referent_store.latest("test-session").value == f"place-{referent_store.MAX_REFERENTS_PER_SESSION + 2}"


def test_stale_referent_not_returned():
    referent_store.add("test-session", "Tunisia", "place", provenance="tool_result")
    with patch("core.orchestration.referent_store.time") as mock_time:
        mock_time.time.return_value = time.time() + referent_store._TTL_SECONDS + 1
        assert referent_store.latest("test-session") is None


def test_clear_session_empties_store():
    referent_store.add("test-session", "Tunisia", "place", provenance="tool_result")
    referent_store.clear_session("test-session")
    assert referent_store.latest("test-session") is None


# ── orchestrator_node: store referents from a tool-routed turn ──────────────────

def test_orchestrator_stores_referent_from_tool_turn():
    llm_json = json.dumps({
        "receiver": "tool_node",
        "payload": "Get the current time in Tunisia.",
        "requires_approval": False,
        "tool_name": "clock",
        "tool_input": {"timezone": "Africa/Tunis"},
        "referents": [{"type": "place", "value": "Tunisia"}],
    })
    with patch("core.orchestration.nodes.orchestrator_node.call_llm", return_value=llm_json), \
         patch("core.orchestration.nodes.orchestrator_node.tool_registry.get_tool", return_value={"x": 1}), \
         patch("core.orchestration.nodes.orchestrator_node.tool_registry.requires_approval", return_value=False):
        orchestrator_node(_state("what time is it in tunisia"))

    r = referent_store.latest("test-session", type_="place")
    assert r is not None
    assert r.value == "Tunisia"  # Sir's own word, not the converted "Africa/Tunis"


def test_orchestrator_resolves_bare_backreference():
    referent_store.add("test-session", "Tunisia", "place", provenance="tool_result")
    llm_json = json.dumps({
        "receiver": "tool_node",
        "payload": "Get the weather there.",
        "requires_approval": False,
        "tool_name": "weather",
        "tool_input": {"location": "there"},
    })
    with patch("core.orchestration.nodes.orchestrator_node.call_llm", return_value=llm_json), \
         patch("core.orchestration.nodes.orchestrator_node.tool_registry.get_tool", return_value={"x": 1}), \
         patch("core.orchestration.nodes.orchestrator_node.tool_registry.requires_approval", return_value=False):
        result = orchestrator_node(_state("what's the weather there"))

    assert result["a2a_payload"]["tool_input"]["location"] == "Tunisia"


def test_orchestrator_leaves_placeholder_when_store_empty():
    # No prior referent stored for this session — must not fabricate a value.
    llm_json = json.dumps({
        "receiver": "tool_node",
        "payload": "Get the weather there.",
        "requires_approval": False,
        "tool_name": "weather",
        "tool_input": {"location": "there"},
    })
    with patch("core.orchestration.nodes.orchestrator_node.call_llm", return_value=llm_json), \
         patch("core.orchestration.nodes.orchestrator_node.tool_registry.get_tool", return_value={"x": 1}), \
         patch("core.orchestration.nodes.orchestrator_node.tool_registry.requires_approval", return_value=False):
        result = orchestrator_node(_state("what's the weather there", session_id="test-session-2"))

    assert result["a2a_payload"]["tool_input"]["location"] == "there"


def test_orchestrator_does_not_store_when_tool_unknown():
    # Referents must not persist for a turn that never actually reached a valid tool.
    llm_json = json.dumps({
        "receiver": "tool_node",
        "payload": "x",
        "tool_name": "made_up_tool",
        "tool_input": {"location": "Tunisia"},
        "referents": [{"type": "place", "value": "Tunisia"}],
    })
    with patch("core.orchestration.nodes.orchestrator_node.call_llm", return_value=llm_json), \
         patch("core.orchestration.nodes.orchestrator_node.tool_registry.get_tool", return_value=None):
        orchestrator_node(_state("what time is it in tunisia"))

    assert referent_store.latest("test-session", type_="place") is None
