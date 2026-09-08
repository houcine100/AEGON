# tests/test_a4.py
# Gate test for Phase A4.1 — Challenge Layer.
# Tests _challenge_check() and response_synthesizer() in isolation.
# No DB, no voice, no live LLM.
#
# Run: python -m pytest tests/test_a4.py -v

from unittest.mock import patch, MagicMock
import pytest


# ── Helper ──────────────────────────────────────────────────────────────────

def _make_fact(text: str) -> dict:
    return {"fact": text, "form": "habit", "similarity": 0.85}


def _make_state(**overrides) -> dict:
    base = {
        "raw_input": "schedule a 9am meeting tomorrow",
        "intent": "task",
        "worker_response": "Done. Meeting scheduled for 9am.",
        "governance_result": "pass",
        "decision_log": [],
    }
    base.update(overrides)
    return base


# ── _challenge_check ─────────────────────────────────────────────────────────

class TestChallengeCheck:
    def test_habit_conflict_surfaced(self):
        """Task conflicting with a stored habit returns a challenge sentence."""
        import core.orchestration.nodes.response_synthesizer as rs
        facts = [_make_fact("Sir protects his mornings — no meetings before 10am.")]
        with patch.object(rs, "search_facts", return_value=facts), \
             patch.object(rs, "call_llm", return_value="This conflicts with your habit of protecting mornings. Still confirm?"):
            result = rs._challenge_check("schedule a 9am meeting")
        assert "Still confirm?" in result

    def test_decision_conflict_surfaced(self):
        """Task reversing a stored decision returns a challenge sentence."""
        import core.orchestration.nodes.response_synthesizer as rs
        facts = [_make_fact("Sir decided to stop using Twitter in January 2026.")]
        with patch.object(rs, "search_facts", return_value=facts), \
             patch.object(rs, "call_llm", return_value="You decided to stop using Twitter. Still confirm?"):
            result = rs._challenge_check("post a tweet about the new release")
        assert "Still confirm?" in result

    def test_no_conflict_returns_empty(self):
        """Task with no conflict returns empty string."""
        import core.orchestration.nodes.response_synthesizer as rs
        facts = [_make_fact("Sir prefers dark mode in all apps.")]
        with patch.object(rs, "search_facts", return_value=facts), \
             patch.object(rs, "call_llm", return_value=""):
            result = rs._challenge_check("send an email to the team")
        assert result == ""

    def test_no_facts_returns_empty(self):
        """Empty memory returns empty string without calling LLM."""
        import core.orchestration.nodes.response_synthesizer as rs
        with patch.object(rs, "search_facts", return_value=[]) as mock_sf, \
             patch.object(rs, "call_llm") as mock_llm:
            result = rs._challenge_check("book a flight")
        assert result == ""
        mock_llm.assert_not_called()

    def test_llm_without_still_confirm_rejected(self):
        """LLM response missing 'Still confirm?' is rejected."""
        import core.orchestration.nodes.response_synthesizer as rs
        facts = [_make_fact("Sir exercises every morning.")]
        with patch.object(rs, "search_facts", return_value=facts), \
             patch.object(rs, "call_llm", return_value="That might conflict with your exercise habit."):
            result = rs._challenge_check("skip the gym today")
        assert result == ""

    def test_multi_sentence_llm_response_rejected(self):
        """Multi-sentence LLM response is rejected — challenge must be one sentence."""
        import core.orchestration.nodes.response_synthesizer as rs
        facts = [_make_fact("Sir exercises every morning.")]
        with patch.object(rs, "search_facts", return_value=facts), \
             patch.object(rs, "call_llm", return_value="You exercise every morning. This conflicts with skipping. Still confirm?"):
            result = rs._challenge_check("skip the gym today")
        assert result == ""

    def test_challenge_is_prepended_to_response(self):
        """When challenge fires, it is prepended to the final response."""
        import core.orchestration.nodes.response_synthesizer as rs
        facts = [_make_fact("Sir protects his mornings — no meetings before 10am.")]
        challenge_sentence = "This conflicts with your morning protection habit. Still confirm?"
        state = _make_state()

        with patch.object(rs, "search_facts", return_value=facts), \
             patch.object(rs, "call_llm", side_effect=[challenge_sentence, state["worker_response"]]), \
             patch.object(rs, "speak"):
            result = rs.response_synthesizer(state)

        assert result["final_response"].startswith(challenge_sentence)

    def test_challenge_logged_in_decision_log(self):
        """challenge_fired is recorded in the decision log."""
        import core.orchestration.nodes.response_synthesizer as rs
        facts = [_make_fact("Sir protects his mornings — no meetings before 10am.")]
        challenge_sentence = "This conflicts with your morning protection habit. Still confirm?"
        state = _make_state()

        with patch.object(rs, "search_facts", return_value=facts), \
             patch.object(rs, "call_llm", side_effect=[challenge_sentence, state["worker_response"]]), \
             patch.object(rs, "speak"):
            result = rs.response_synthesizer(state)

        log_entry = result["decision_log"][-1]
        assert log_entry["challenge_fired"] is True


# ── response_synthesizer integration ────────────────────────────────────────

class TestSynthesizerChallengeGating:
    def test_challenge_does_not_fire_for_conversation_intent(self):
        """Conversation intent never triggers challenge check."""
        import core.orchestration.nodes.response_synthesizer as rs
        state = _make_state(intent="conversation", raw_input="how are you?")

        with patch.object(rs, "search_facts") as mock_sf, \
             patch.object(rs, "speak"):
            rs.response_synthesizer(state)

        mock_sf.assert_not_called()

    def test_challenge_does_not_fire_for_memory_query(self):
        """Memory query intent never triggers challenge check."""
        import core.orchestration.nodes.response_synthesizer as rs
        state = _make_state(intent="memory_query", raw_input="what do you know about me?")

        with patch.object(rs, "search_facts") as mock_sf, \
             patch.object(rs, "speak"):
            rs.response_synthesizer(state)

        mock_sf.assert_not_called()

    def test_challenge_does_not_fire_when_governance_failed(self):
        """Governance fail suppresses challenge check entirely."""
        import core.orchestration.nodes.response_synthesizer as rs
        state = _make_state(governance_result="fail")

        with patch.object(rs, "search_facts") as mock_sf, \
             patch.object(rs, "speak"):
            rs.response_synthesizer(state)

        mock_sf.assert_not_called()

    def test_plan_request_triggers_challenge(self):
        """plan_request intent triggers challenge check."""
        import core.orchestration.nodes.response_synthesizer as rs
        state = _make_state(intent="plan_request", raw_input="plan my week with early morning meetings")

        with patch.object(rs, "search_facts", return_value=[]) as mock_sf, \
             patch.object(rs, "speak"):
            rs.response_synthesizer(state)

        mock_sf.assert_called_once()

    def test_no_challenge_no_prepend(self):
        """When no conflict found, final_response is unchanged."""
        import core.orchestration.nodes.response_synthesizer as rs
        state = _make_state()

        with patch.object(rs, "search_facts", return_value=[]), \
             patch.object(rs, "speak"):
            result = rs.response_synthesizer(state)

        assert result["final_response"] == state["worker_response"]
        assert result["decision_log"][-1]["challenge_fired"] is False

    def test_challenge_skipped_when_tool_ran(self):
        """Bug 2: a read-only tool turn (tool_result set) never triggers the challenge."""
        import core.orchestration.nodes.response_synthesizer as rs
        state = _make_state(
            intent="task",
            raw_input="search my notes for the project plan",
            worker_response="Here is what I found, Sir: ...",
            tool_result=[{"status": "success"}],
        )

        with patch.object(rs, "search_facts") as mock_sf, \
             patch.object(rs, "speak"):
            result = rs.response_synthesizer(state)

        mock_sf.assert_not_called()
        assert result["decision_log"][-1]["challenge_fired"] is False
