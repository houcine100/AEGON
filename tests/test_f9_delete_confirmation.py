# tests/test_f9_delete_confirmation.py
# Gate test for F.9: delete confirmation flow.
# Mocks DB calls — no live Postgres needed.
#
# Run: python -m pytest tests/test_f9_delete_confirmation.py -v

import pytest
from unittest.mock import patch
from agents.memory_agent.memory_agent import memory_agent
from core.orchestration.nodes.approval_handler import approval_handler

FAKE_FACT = {"id": "fact-001", "fact": "Sir prefers working in silence.", "similarity": 0.92}


def _memory_state(raw_input: str, **overrides) -> dict:
    base = {
        "session_id": "test-session",
        "thread_id": "test-thread",
        "raw_input": raw_input,
        "active_mode": "standard",
        "conversation_history": "",
        "intent": "memory_query",
        "confidence": None,
        "requested_mode": None,
        "a2a_payload": {"payload": raw_input},
        "worker_response": None,
        "governance_result": None,
        "governance_reason": None,
        "requires_approval": None,
        "final_response": None,
        "decision_log": [],
        "memory_context": None,
        "pending_approval": None,
        "tool_result": None,
        "approval_verdict": None,
    }
    base.update(overrides)
    return base


def _approval_state(raw_input: str, pending: dict, **overrides) -> dict:
    base = _memory_state(raw_input, pending_approval=pending)
    base.update(overrides)
    return base


class TestDeleteParking:
    def test_delete_parks_and_asks_confirmation(self):
        state = _memory_state("forget that I prefer silence")
        with patch("agents.memory_agent.memory_agent.search_facts", return_value=[FAKE_FACT]):
            result = memory_agent(state)

        assert result["requires_approval"] is True
        pending = result["pending_approval"]
        assert pending is not None
        assert pending["action_type"] == "memory_delete"
        assert pending["fact_id"] == "fact-001"
        assert "Sir prefers working in silence" in pending["fact_text"]
        assert "Sir prefers working in silence" in result["worker_response"]

    def test_delete_not_found_returns_message_no_park(self):
        state = _memory_state("forget that I eat pizza")
        with patch("agents.memory_agent.memory_agent.search_facts", return_value=[]):
            result = memory_agent(state)

        assert not result.get("requires_approval")
        assert result.get("pending_approval") is None
        assert "could not find" in result["worker_response"].lower()

    def test_low_similarity_returns_message_no_park(self):
        low_sim = {**FAKE_FACT, "similarity": 0.30}
        state = _memory_state("forget something vague")
        with patch("agents.memory_agent.memory_agent.search_facts", return_value=[low_sim]):
            result = memory_agent(state)

        assert not result.get("requires_approval")
        assert result.get("pending_approval") is None


class TestApprovalYes:
    def _pending(self):
        return {
            "action_type": "memory_delete",
            "tool": "memory_agent",
            "fact_id": "fact-001",
            "fact_text": "Sir prefers working in silence.",
            "prompt_shown": "Shall I remove this from memory: 'Sir prefers working in silence.'?",
        }

    def test_yes_executes_soft_delete(self):
        state = _approval_state("yes", self._pending())
        with patch("core.orchestration.nodes.approval_handler.update_fact_status") as mock_update:
            result = approval_handler(state)

        mock_update.assert_called_once_with(
            record_id="fact-001",
            status="resolved",
            resolution_notes="Removed by Sir's explicit request.",
        )
        assert result["approval_verdict"] == "completed"
        assert result["pending_approval"] is None
        assert result["requires_approval"] is False
        assert "removed" in result["worker_response"].lower()

    def test_yes_response_names_the_fact(self):
        state = _approval_state("yes", self._pending())
        with patch("core.orchestration.nodes.approval_handler.update_fact_status"):
            result = approval_handler(state)
        assert "Sir prefers working in silence" in result["worker_response"]

    def test_audit_log_records_delete(self):
        state = _approval_state("yes", self._pending())
        with patch("core.orchestration.nodes.approval_handler.update_fact_status"):
            result = approval_handler(state)
        delete_entry = next(
            (e for e in result["decision_log"] if e.get("action_type") == "memory_delete"), None
        )
        assert delete_entry is not None
        assert delete_entry["fact_id"] == "fact-001"
        assert delete_entry["verdict"] == "approved_executed"


class TestApprovalNo:
    def _pending(self):
        return {
            "action_type": "memory_delete",
            "tool": "memory_agent",
            "fact_id": "fact-001",
            "fact_text": "Sir prefers working in silence.",
            "prompt_shown": "Shall I remove this from memory?",
        }

    def test_no_preserves_fact(self):
        state = _approval_state("no", self._pending())
        with patch("core.orchestration.nodes.approval_handler.update_fact_status") as mock_update:
            result = approval_handler(state)

        mock_update.assert_not_called()
        assert result["approval_verdict"] == "rejected"
        assert result["pending_approval"] is None

    def test_cancel_preserves_fact(self):
        state = _approval_state("cancel", self._pending())
        with patch("core.orchestration.nodes.approval_handler.update_fact_status") as mock_update:
            result = approval_handler(state)

        mock_update.assert_not_called()


class TestNoLeak:
    def test_two_deletes_ask_independently(self):
        fact_a = {"id": "fact-A", "fact": "Sir drinks coffee in the morning.", "similarity": 0.91}
        fact_b = {"id": "fact-B", "fact": "Sir prefers dark mode.", "similarity": 0.88}

        state_a = _memory_state("forget that I drink coffee")
        with patch("agents.memory_agent.memory_agent.search_facts", return_value=[fact_a]):
            result_a = memory_agent(state_a)

        state_b = _memory_state("forget that I like dark mode")
        with patch("agents.memory_agent.memory_agent.search_facts", return_value=[fact_b]):
            result_b = memory_agent(state_b)

        assert result_a["pending_approval"]["fact_id"] == "fact-A"
        assert result_b["pending_approval"]["fact_id"] == "fact-B"
        assert result_a["pending_approval"]["fact_id"] != result_b["pending_approval"]["fact_id"]
