# tests/test_bug1_multi_tool.py
# Bug 1b gate: multi-tool-per-turn. Fully mocked — no LLM, no live connectors.
#   1. orchestrator_node parses a valid tool_calls batch into the A2A payload.
#   2. tool_node runs every non-gated tool in the batch and combines the answers.
#   3. a gated tool inside a batch is NEVER auto-run — it is flagged for separate approval.
#   4. a batch with fewer than two valid tools collapses back to the single-tool path.

import json
from unittest.mock import patch

from core.orchestration.nodes.orchestrator_node import orchestrator_node
from core.orchestration.nodes.tool_node import tool_node


def _state(**overrides):
    base = {
        "raw_input": "whats the weather and my schedule",
        "intent": "task",
        "confidence": 0.95,
        "session_id": "test",
        "thread_id": "test",
        "decision_log": [],
        "a2a_payload": None,
        "approval_verdict": None,
        "pending_approval": None,
    }
    base.update(overrides)
    return base


# ── orchestrator_node: parse the batch ─────────────────────────────────────────

def test_orchestrator_parses_valid_batch():
    llm_json = json.dumps({
        "receiver": "tool_node",
        "payload": "weather and schedule",
        "requires_approval": False,
        "tool_name": "weather",
        "tool_input": {},
        "tool_calls": [
            {"tool_name": "weather", "tool_input": {}},
            {"tool_name": "calendar_read", "tool_input": {"range": "today"}},
        ],
    })
    with patch("core.orchestration.nodes.orchestrator_node.call_llm", return_value=llm_json), \
         patch("core.orchestration.nodes.orchestrator_node.tool_registry.get_tool", return_value={"x": 1}), \
         patch("core.orchestration.nodes.orchestrator_node.tool_registry.requires_approval", return_value=False):
        result = orchestrator_node(_state())

    calls = result["a2a_payload"]["tool_calls"]
    assert [c["tool_name"] for c in calls] == ["weather", "calendar_read"]
    # first element mirrored into the single fields
    assert result["a2a_payload"]["tool_name"] == "weather"


def test_orchestrator_drops_unknown_tools_in_batch():
    llm_json = json.dumps({
        "receiver": "tool_node",
        "payload": "x",
        "tool_name": "weather",
        "tool_input": {},
        "tool_calls": [
            {"tool_name": "weather", "tool_input": {}},
            {"tool_name": "made_up_tool", "tool_input": {}},
        ],
    })

    def fake_get_tool(name):
        return {"x": 1} if name == "weather" else None

    with patch("core.orchestration.nodes.orchestrator_node.call_llm", return_value=llm_json), \
         patch("core.orchestration.nodes.orchestrator_node.tool_registry.get_tool", side_effect=fake_get_tool), \
         patch("core.orchestration.nodes.orchestrator_node.tool_registry.requires_approval", return_value=False):
        result = orchestrator_node(_state())

    # only one valid tool survived -> batch collapses to None, single-tool path used
    assert result["a2a_payload"]["tool_calls"] is None
    assert result["a2a_payload"]["tool_name"] == "weather"


# ── tool_node: run the batch ───────────────────────────────────────────────────

def test_tool_node_runs_both_non_gated():
    payload = {
        "tool_name": "weather",
        "tool_input": {},
        "tool_calls": [
            {"tool_name": "weather", "tool_input": {}},
            {"tool_name": "calendar_read", "tool_input": {"range": "today"}},
        ],
    }
    canned = {
        "weather": ({"status": "success"}, "It is 20 degrees, Sir."),
        "calendar_read": ({"status": "success"}, "One meeting at noon, Sir."),
    }

    def fake_run_tool(name, tinput, status, sid, tid, log):
        return canned[name]

    with patch("core.orchestration.nodes.tool_node.tool_registry.get_tool", return_value={"x": 1}), \
         patch("core.orchestration.nodes.tool_node.tool_registry.requires_approval", return_value=False), \
         patch("core.orchestration.nodes.tool_node._run_tool", side_effect=fake_run_tool):
        result = tool_node(_state(a2a_payload=payload))

    assert "20 degrees" in result["worker_response"]
    assert "meeting at noon" in result["worker_response"]
    assert len(result["tool_result"]) == 2


def test_tool_node_skips_gated_tool_in_batch():
    payload = {
        "tool_name": "weather",
        "tool_input": {},
        "tool_calls": [
            {"tool_name": "weather", "tool_input": {}},
            {"tool_name": "gmail_send", "tool_input": {}},
        ],
    }

    def fake_requires_approval(name):
        return name == "gmail_send"

    def fake_run_tool(name, tinput, status, sid, tid, log):
        return ({"status": "success"}, "It is 20 degrees, Sir.")

    with patch("core.orchestration.nodes.tool_node.tool_registry.get_tool", return_value={"x": 1}), \
         patch("core.orchestration.nodes.tool_node.tool_registry.requires_approval", side_effect=fake_requires_approval), \
         patch("core.orchestration.nodes.tool_node._run_tool", side_effect=fake_run_tool):
        result = tool_node(_state(a2a_payload=payload))

    assert "20 degrees" in result["worker_response"]
    assert "gmail_send needs your approval" in result["worker_response"]
    # only the non-gated tool actually ran
    assert len(result["tool_result"]) == 1
