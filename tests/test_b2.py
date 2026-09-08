# tests/test_b2.py
# Gate test for Phase B2 — Proactive Intelligence Upgrade.
# No DB, no LLM, no calendar API, no live sentinel.
#
# Run: python -m pytest tests/test_b2.py -v

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest


# ── rule_topic_frequency ─────────────────────────────────────────────────────

class TestRuleTopicFrequency:
    def _fact(self, text: str) -> dict:
        return {"fact": text, "created_at": datetime.now(timezone.utc)}

    def test_fires_when_word_in_three_facts(self):
        from core.sentinel.rules import rule_topic_frequency
        facts = [
            self._fact("Sir is building scheduler assistant"),
            self._fact("scheduler needs voice module"),
            self._fact("scheduler phase is next"),
        ]
        findings = rule_topic_frequency(facts, [])
        types = [f.type for f in findings]
        assert "topic_frequency" in types

    def test_skips_word_covered_by_project_model(self):
        from core.sentinel.rules import rule_topic_frequency
        facts = [
            self._fact("scheduler is being built"),
            self._fact("scheduler needs testing"),
            self._fact("scheduler phase underway"),
        ]
        models = [{"name": "scheduler"}]
        findings = rule_topic_frequency(facts, models)
        assert findings == []

    def test_needs_three_distinct_facts(self):
        from core.sentinel.rules import rule_topic_frequency
        facts = [
            self._fact("scheduler voice module"),
            self._fact("scheduler sentinel rule"),
        ]
        findings = rule_topic_frequency(facts, [])
        assert findings == []

    def test_fewer_than_three_facts_returns_empty(self):
        from core.sentinel.rules import rule_topic_frequency
        assert rule_topic_frequency([self._fact("scheduler thing"), self._fact("scheduler test")], []) == []

    def test_short_words_ignored(self):
        from core.sentinel.rules import rule_topic_frequency
        facts = [self._fact("go do it now"), self._fact("go do it now"), self._fact("go do it now")]
        findings = rule_topic_frequency(facts, [])
        assert findings == []

    def test_urgency_is_low(self):
        from core.sentinel.rules import rule_topic_frequency
        facts = [
            self._fact("tracker project started"),
            self._fact("tracker needs design"),
            self._fact("tracker is important"),
        ]
        findings = rule_topic_frequency(facts, [])
        assert all(f.urgency == "low" for f in findings)

    def test_timing_is_session_start(self):
        from core.sentinel.rules import rule_topic_frequency
        facts = [
            self._fact("fitness tracker app"),
            self._fact("fitness goals matter"),
            self._fact("fitness routine daily"),
        ]
        findings = rule_topic_frequency(facts, [])
        assert all(f.timing == "session_start" for f in findings)


# ── hit-rate gating in run_all_rules ─────────────────────────────────────────

class TestHitRateGating:
    def test_suppressed_rule_not_called(self):
        from core.sentinel import rules

        def suppressed_for_deadline(rule_type):
            return rule_type == "deadline"

        with patch("core.memory.memory_store.get_facts_by_form", return_value=[]), \
             patch("core.memory.memory_store.get_recent_facts", return_value=[]), \
             patch("core.memory.project_model_store.get_all_project_models", return_value=[]), \
             patch("core.feedback.feedback_store.should_suppress", side_effect=suppressed_for_deadline), \
             patch.object(rules, "rule_deadline") as mock_deadline:
            rules.run_all_rules()

        mock_deadline.assert_not_called()

    def test_non_suppressed_rule_still_called(self):
        from core.sentinel import rules

        with patch("core.memory.memory_store.get_facts_by_form", return_value=[]), \
             patch("core.memory.memory_store.get_recent_facts", return_value=[]), \
             patch("core.memory.project_model_store.get_all_project_models", return_value=[]), \
             patch("core.feedback.feedback_store.should_suppress", return_value=False), \
             patch.object(rules, "rule_deadline", return_value=[]) as mock_deadline:
            rules.run_all_rules()

        mock_deadline.assert_called_once()

    def test_feedback_store_unavailable_runs_all(self):
        """If feedback_store import fails, all rules still run."""
        from core.sentinel import rules

        with patch("core.memory.memory_store.get_facts_by_form", return_value=[]), \
             patch("core.memory.memory_store.get_recent_facts", return_value=[]), \
             patch("core.memory.project_model_store.get_all_project_models", return_value=[]), \
             patch.dict("sys.modules", {"core.feedback.feedback_store": None}), \
             patch.object(rules, "rule_deadline", return_value=[]) as mock_deadline:
            rules.run_all_rules()

        mock_deadline.assert_called_once()

    def test_topic_frequency_included_when_not_suppressed(self):
        from core.sentinel import rules

        with patch("core.memory.memory_store.get_facts_by_form", return_value=[]), \
             patch("core.memory.memory_store.get_recent_facts", return_value=[]), \
             patch("core.memory.project_model_store.get_all_project_models", return_value=[]), \
             patch("core.feedback.feedback_store.should_suppress", return_value=False), \
             patch.object(rules, "rule_topic_frequency", return_value=[]) as mock_tf:
            rules.run_all_rules()

        mock_tf.assert_called_once()


# ── deep_work_gap sentinel check ─────────────────────────────────────────────

class TestCheckDeepWorkGap:
    def _make_service(self, events: list):
        service = MagicMock()
        service.events().list().execute.return_value = {"items": events}
        return service

    def _event(self, start_hour: int, end_hour: int) -> dict:
        base = datetime.now().astimezone().replace(minute=0, second=0, microsecond=0)
        start = base.replace(hour=start_hour)
        end = base.replace(hour=end_hour)
        return {
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }

    def test_fires_when_gap_exists(self):
        import core.sentinel.sentinel as s
        s._deep_work_gap_date = None
        service = self._make_service([self._event(12, 13)])
        pushed = []
        now = datetime.now().astimezone().replace(hour=9, minute=0, second=0, microsecond=0)
        with patch("core.security.gmail_auth.get_calendar_service", return_value=service), \
             patch("core.sentinel.sentinel.datetime") as mock_dt, \
             patch("core.sentinel.sentinel.push", side_effect=pushed.append):
            mock_dt.now.return_value = now
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            s._check_deep_work_gap()
        assert len(pushed) == 1
        assert pushed[0].type == "deep_work_gap"

    def test_no_gap_no_finding(self):
        import core.sentinel.sentinel as s
        s._deep_work_gap_date = None
        service = self._make_service([
            self._event(9, 11), self._event(11, 13),
            self._event(13, 15), self._event(15, 17),
        ])
        pushed = []
        now = datetime.now().astimezone().replace(hour=9, minute=0, second=0, microsecond=0)
        with patch("core.security.gmail_auth.get_calendar_service", return_value=service), \
             patch("core.sentinel.sentinel.datetime") as mock_dt, \
             patch("core.sentinel.sentinel.push", side_effect=pushed.append):
            mock_dt.now.return_value = now
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            s._check_deep_work_gap()
        assert pushed == []

    def test_dedup_same_day(self):
        import core.sentinel.sentinel as s
        today = datetime.now().strftime("%Y-%m-%d")
        s._deep_work_gap_date = today
        pushed = []
        with patch("core.sentinel.sentinel.push", side_effect=pushed.append):
            s._check_deep_work_gap()
        assert pushed == []

    def test_no_service_no_crash(self):
        import core.sentinel.sentinel as s
        s._deep_work_gap_date = None
        with patch("core.security.gmail_auth.get_calendar_service", return_value=None):
            s._check_deep_work_gap()

    def test_urgency_low_timing_session_start(self):
        import core.sentinel.sentinel as s
        s._deep_work_gap_date = None
        service = self._make_service([])
        now = datetime.now().astimezone().replace(hour=9, minute=0, second=0, microsecond=0)
        pushed = []
        with patch("core.security.gmail_auth.get_calendar_service", return_value=service), \
             patch("core.sentinel.sentinel.datetime") as mock_dt, \
             patch("core.sentinel.sentinel.push", side_effect=pushed.append):
            mock_dt.now.return_value = now
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            s._check_deep_work_gap()
        assert len(pushed) == 1
        assert pushed[0].urgency == "low"
        assert pushed[0].timing == "session_start"
