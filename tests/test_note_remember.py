# tests/test_note_remember.py
# Part 2 gate: explicit "remember the content of note X" — the only sanctioned
# path for an Obsidian note's BODY to enter memory. Fully mocked: no LLM, no vault.

from unittest.mock import patch
import agents.memory_agent.memory_agent as ma
from schemas.intent_schema import Intent


def _state(payload: str) -> dict:
    return {
        "a2a_payload": {"payload": payload},
        "raw_input": payload,
        "intent": Intent.NOTE_REMEMBER,
        "memory_context": "",
        "conversation_history": "",
        "session_id": "test",
        "decision_log": [],
    }


class _FakeConnector:
    def __init__(self, result):
        self._result = result

    def execute(self, payload):
        return self._result


def test_note_content_stored_on_explicit_request():
    state = _state("remember the content of note Groceries")
    with patch.object(ma, "_extract_note_title", return_value="Groceries"), \
         patch.object(ma, "ObsidianReadConnector", return_value=_FakeConnector(
             {"status": "success", "output": "Milk, eggs, bread."})), \
         patch.object(ma, "store_fact", return_value=1) as mock_store:
        result = ma.memory_agent(state)

    fact = mock_store.call_args.kwargs["fact"]
    assert "Groceries" in fact
    assert "Milk, eggs, bread." in fact
    assert mock_store.call_args.kwargs["source"] == "vault"
    assert "remembered the content of 'Groceries'" in result["worker_response"]


def test_missing_note_does_not_store():
    state = _state("remember the content of note Ghost")
    with patch.object(ma, "_extract_note_title", return_value="Ghost"), \
         patch.object(ma, "ObsidianReadConnector", return_value=_FakeConnector(
             {"status": "error", "output": "Note 'Ghost' not found in the vault."})), \
         patch.object(ma, "store_fact") as mock_store:
        result = ma.memory_agent(state)

    mock_store.assert_not_called()
    assert "could not find" in result["worker_response"].lower()


def test_empty_note_does_not_store():
    state = _state("remember the content of note Blank")
    with patch.object(ma, "_extract_note_title", return_value="Blank"), \
         patch.object(ma, "ObsidianReadConnector", return_value=_FakeConnector(
             {"status": "success", "output": "   "})), \
         patch.object(ma, "store_fact") as mock_store:
        result = ma.memory_agent(state)

    mock_store.assert_not_called()
    assert "empty" in result["worker_response"].lower()


def test_content_capped_to_max_chars():
    long_body = "x" * 5000
    state = _state("remember the content of note Big")
    with patch.object(ma, "_extract_note_title", return_value="Big"), \
         patch.object(ma, "ObsidianReadConnector", return_value=_FakeConnector(
             {"status": "success", "output": long_body})), \
         patch.object(ma, "store_fact", return_value=1) as mock_store:
        ma.memory_agent(state)

    fact = mock_store.call_args.kwargs["fact"]
    # prefix + capped body, never the full 5000 chars
    assert fact.count("x") <= ma._NOTE_CONTENT_MAX_CHARS


def test_blank_title_asks_which_note():
    state = _state("remember the content of that note")
    with patch.object(ma, "_extract_note_title", return_value=""), \
         patch.object(ma, "store_fact") as mock_store:
        result = ma.memory_agent(state)

    mock_store.assert_not_called()
    assert "which note" in result["worker_response"].lower()
