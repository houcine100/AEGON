# tests/test_f16_extraction_gate.py
# F.5 gate: verify F16 fact-extraction guard under real conditions (deterministic).
# Tests the EXACT gate logic from aegon_orchestrator.py line ~173 in isolation —
# no DB, no Groq, no Postgres required.
#
# Gate spec: 5 tool turns + 5 memory_query turns = 0 extractions;
#            5 Sir-statement turns = exactly 5 extractions.
#
# Run: .venv\Scripts\python.exe -m pytest tests/test_f16_extraction_gate.py -v

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ── Replica of the F16 gate from aegon_orchestrator.py:173 ──────────────────
# Kept in sync manually; if the orchestrator changes, update here too.

def should_extract(intent: str, tool_result, a2a_payload: dict) -> bool:
    """Returns True when the orchestrator would call _add_to_extraction_buffer."""
    _used_tool = bool(tool_result) or (a2a_payload or {}).get("receiver") == "tool_node"
    return intent != "memory_query" and not _used_tool


# ── Helpers ──────────────────────────────────────────────────────────────────

def tool_turn(tool_name: str) -> dict:
    return {
        "intent": "task",
        "tool_result": {"output": "some data"},
        "a2a_payload": {"receiver": "tool_node", "tool_name": tool_name},
    }


def memory_query_turn() -> dict:
    return {"intent": "memory_query", "tool_result": None, "a2a_payload": {}}


def statement_turn(intent: str = "conversation") -> dict:
    return {"intent": intent, "tool_result": None, "a2a_payload": {}}


# ── F.5 gate tests ───────────────────────────────────────────────────────────

class TestF16Gate:

    def test_tool_turns_never_extract(self):
        turns = [
            tool_turn("web_search"),
            tool_turn("gmail_read"),
            tool_turn("spotify_play"),
            tool_turn("calendar_read"),
            tool_turn("github_search"),
        ]
        extractions = sum(1 for t in turns
                          if should_extract(t["intent"], t["tool_result"], t["a2a_payload"]))
        assert extractions == 0, f"Expected 0, got {extractions}"

    def test_memory_query_turns_never_extract(self):
        turns = [memory_query_turn() for _ in range(5)]
        extractions = sum(1 for t in turns
                          if should_extract(t["intent"], t["tool_result"], t["a2a_payload"]))
        assert extractions == 0, f"Expected 0, got {extractions}"

    def test_sir_statement_turns_always_extract(self):
        turns = [
            statement_turn("conversation"),
            statement_turn("conversation"),
            statement_turn("summarize_request"),
            statement_turn("plan_request"),
            statement_turn("conversation"),
        ]
        extractions = sum(1 for t in turns
                          if should_extract(t["intent"], t["tool_result"], t["a2a_payload"]))
        assert extractions == 5, f"Expected 5, got {extractions}"

    def test_mixed_session_20_turns(self):
        """20-turn mixed session: gate allows extraction only on Sir-statement turns."""
        session = (
            [tool_turn("web_search")] * 5
            + [memory_query_turn()] * 5
            + [statement_turn("conversation")] * 5
            + [tool_turn("gmail_read")] * 3
            + [statement_turn("plan_request")] * 2
        )
        expected = 7  # 5 conversation + 2 plan_request
        extractions = sum(1 for t in session
                          if should_extract(t["intent"], t["tool_result"], t["a2a_payload"]))
        assert extractions == expected, f"Expected {expected}, got {extractions}"

    def test_tool_node_receiver_blocks_extraction_even_without_tool_result(self):
        """a2a_payload receiver=tool_node is sufficient to block extraction."""
        turn = {"intent": "task", "tool_result": None,
                "a2a_payload": {"receiver": "tool_node", "tool_name": "clock"}}
        assert not should_extract(turn["intent"], turn["tool_result"], turn["a2a_payload"])

    def test_conversation_turn_with_no_tool_extracts(self):
        turn = statement_turn("conversation")
        assert should_extract(turn["intent"], turn["tool_result"], turn["a2a_payload"])
