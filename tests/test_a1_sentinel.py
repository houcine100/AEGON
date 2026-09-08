# tests/test_a1_sentinel.py
# Gate test for Phase A1.1 — Sentinel Engine.
# Rules tested in isolation with fake facts. No DB required.
#
# Run: python -m pytest tests/test_a1_sentinel.py -v

import time
import threading
from datetime import datetime, timedelta, timezone

from core.sentinel.findings import Finding
from core.sentinel.rules import (
    rule_deadline,
    rule_habit_deviation,
    rule_stale_decision,
    rule_dormant_project,
    rule_recurring_error,
)
from core.sentinel import proactive_queue, sentinel


def _fact(text: str, form: str = "project", age_days: float = 0.0) -> dict:
    created = datetime.now(timezone.utc) - timedelta(days=age_days)
    return {"id": "test-id", "fact": text, "form": form, "created_at": created}


def _future_date(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")

def _past_date(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


class TestRuleDeadline:
    def test_fires_on_deadline_within_3_days(self):
        date = _future_date(2)
        facts = [_fact(f"Aegon project deadline {date} must finish by then")]
        result = rule_deadline(facts)
        assert len(result) == 1
        assert result[0].type == "deadline"
        assert result[0].urgency == "high"

    def test_does_not_fire_when_deadline_past(self):
        date = _past_date(1)
        facts = [_fact(f"Project deadline {date} due by")]
        assert rule_deadline(facts) == []

    def test_does_not_fire_when_deadline_far_future(self):
        date = _future_date(10)
        facts = [_fact(f"Project deadline {date} complete by")]
        assert rule_deadline(facts) == []

    def test_does_not_fire_without_deadline_keyword(self):
        date = _future_date(1)
        facts = [_fact(f"Working on a project started {date}")]
        assert rule_deadline(facts) == []

    def test_does_not_fire_on_empty(self):
        assert rule_deadline([]) == []


class TestRuleHabitDeviation:
    def test_fires_on_daily_habit_older_than_2_days(self):
        facts = [_fact("Sir exercises every day at 7am", form="habit", age_days=3)]
        result = rule_habit_deviation(facts)
        assert len(result) == 1
        assert result[0].type == "habit_deviation"
        assert result[0].urgency == "medium"

    def test_does_not_fire_on_daily_habit_within_2_days(self):
        facts = [_fact("Sir drinks coffee daily", form="habit", age_days=1)]
        assert rule_habit_deviation(facts) == []

    def test_fires_on_weekly_habit_older_than_9_days(self):
        facts = [_fact("Sir reviews goals weekly", form="habit", age_days=10)]
        result = rule_habit_deviation(facts)
        assert len(result) == 1

    def test_does_not_fire_on_weekly_habit_within_9_days(self):
        facts = [_fact("Sir cleans up code each week", form="habit", age_days=5)]
        assert rule_habit_deviation(facts) == []

    def test_does_not_fire_on_empty(self):
        assert rule_habit_deviation([]) == []


class TestRuleStaleDecision:
    def test_fires_on_decision_older_than_7_days(self):
        facts = [_fact("Sir decided to switch to FastAPI", form="decision", age_days=8)]
        result = rule_stale_decision(facts)
        assert len(result) == 1
        assert result[0].type == "stale_decision"
        assert result[0].urgency == "low"

    def test_does_not_fire_on_recent_decision(self):
        facts = [_fact("Sir decided to use Postgres", form="decision", age_days=3)]
        assert rule_stale_decision(facts) == []

    def test_does_not_fire_on_empty(self):
        assert rule_stale_decision([]) == []


class TestRuleDormantProject:
    def test_fires_on_project_older_than_14_days(self):
        facts = [_fact("Sir is building Aegon voice auth", age_days=15)]
        result = rule_dormant_project(facts)
        assert len(result) == 1
        assert result[0].type == "dormant_project"
        assert result[0].urgency == "low"

    def test_does_not_fire_on_recent_project(self):
        facts = [_fact("Sir is building the sentinel engine", age_days=5)]
        assert rule_dormant_project(facts) == []

    def test_does_not_fire_on_empty(self):
        assert rule_dormant_project([]) == []


class TestRuleRecurringError:
    def test_fires_when_word_appears_in_3_error_facts(self):
        facts = [
            _fact("Spotify keeps failing when no device connected", form="error"),
            _fact("Spotify connection fails on cold start", form="error"),
            _fact("Spotify playback fails after sleep", form="error"),
        ]
        result = rule_recurring_error(facts)
        assert len(result) >= 1
        assert result[0].type == "recurring_error"
        assert result[0].urgency == "medium"

    def test_does_not_fire_with_fewer_than_3_facts(self):
        facts = [
            _fact("Error one", form="error"),
            _fact("Error two", form="error"),
        ]
        assert rule_recurring_error(facts) == []

    def test_does_not_fire_on_empty(self):
        assert rule_recurring_error([]) == []


class TestProactiveQueue:
    def setup_method(self):
        proactive_queue.drain(max_items=1000)

    def test_push_and_drain(self):
        f = Finding(type="deadline", content="test", urgency="high", timing="session_start")
        proactive_queue.push(f)
        result = proactive_queue.drain()
        assert len(result) == 1
        assert result[0].urgency == "high"

    def test_drain_returns_high_urgency_first(self):
        proactive_queue.push(Finding(type="dormant_project", content="low", urgency="low", timing="session_start"))
        proactive_queue.push(Finding(type="deadline", content="high", urgency="high", timing="session_start"))
        proactive_queue.push(Finding(type="recurring_error", content="med", urgency="medium", timing="session_start"))
        result = proactive_queue.drain()
        assert result[0].urgency == "high"
        assert result[1].urgency == "medium"
        assert result[2].urgency == "low"

    def test_drain_max_items_keeps_remainder(self):
        for _ in range(5):
            proactive_queue.push(Finding(type="stale_decision", content="x", urgency="low", timing="session_start"))
        result = proactive_queue.drain(max_items=3)
        assert len(result) == 3
        assert proactive_queue.size() == 2

    def test_empty_drain_returns_empty(self):
        assert proactive_queue.drain() == []


class TestFormatFindings:
    def setup_method(self):
        proactive_queue.drain(max_items=1000)

    def test_format_single_finding(self):
        findings = [Finding(type="deadline", content="Ship Aegon by 2026-06-15.", urgency="high", timing="session_start")]
        text = proactive_queue.format_findings_for_speech(findings)
        assert "1 observation" in text
        assert "Deadline alert" in text
        assert "Ship Aegon" in text

    def test_format_multiple_findings(self):
        findings = [
            Finding(type="deadline", content="Deadline soon.", urgency="high", timing="session_start"),
            Finding(type="stale_decision", content="Old decision.", urgency="low", timing="session_start"),
        ]
        text = proactive_queue.format_findings_for_speech(findings)
        assert "2 observations" in text
        assert "Deadline alert" in text
        assert "Open decision" in text

    def test_format_marks_findings_as_surfaced(self):
        f = Finding(type="dormant_project", content="Aegon auth.", urgency="low", timing="session_start")
        proactive_queue.format_findings_for_speech([f])
        assert f.surfaced is True

    def test_format_empty_returns_empty_string(self):
        assert proactive_queue.format_findings_for_speech([]) == ""

    def test_morning_briefing_prepends_findings(self):
        from core.modes.morning_briefing import build_briefing
        proactive_queue.push(Finding(
            type="deadline", content="Project X deadline 2026-06-15.",
            urgency="high", timing="session_start"
        ))
        briefing = build_briefing()
        assert "Deadline alert" in briefing
        assert briefing.startswith("Sir, here is your briefing.")


class TestSentinelThread:
    def test_starts_as_daemon_thread(self):
        sentinel.stop()
        time.sleep(0.1)
        sentinel.start()
        assert sentinel.is_running()
        threads = [t for t in threading.enumerate() if t.name == "sentinel"]
        assert len(threads) == 1
        assert threads[0].daemon is True
        sentinel.stop()

    def test_start_is_idempotent(self):
        sentinel.stop()
        time.sleep(0.1)
        sentinel.start()
        sentinel.start()
        sentinels = [t for t in threading.enumerate() if t.name == "sentinel"]
        assert len(sentinels) == 1
        sentinel.stop()

    def test_start_spawns_calendar_thread(self):
        sentinel.stop()
        time.sleep(0.1)
        sentinel.start()
        cal_threads = [t for t in threading.enumerate() if t.name == "sentinel-calendar"]
        assert len(cal_threads) == 1
        assert cal_threads[0].daemon is True
        sentinel.stop()


class TestEventTriggers:
    def setup_method(self):
        proactive_queue.drain(max_items=1000)

    def test_on_fact_stored_spawns_background_thread(self):
        from unittest.mock import patch
        with patch("core.sentinel.sentinel.run_all_rules", return_value=[]) as mock_rules:
            sentinel.on_fact_stored()
            time.sleep(0.2)
            mock_rules.assert_called()

    def test_dispatch_immediate_finding_calls_surface(self):
        from unittest.mock import patch
        from core.sentinel.sentinel import _dispatch
        f = Finding(type="calendar_approaching", content="Meeting in 5 minutes.",
                    urgency="high", timing="immediate")
        with patch("core.sentinel.sentinel._surface_immediate") as mock_surface:
            _dispatch([f])
            mock_surface.assert_called_once_with(f)
        assert proactive_queue.size() == 0

    def test_dispatch_session_start_finding_queues(self):
        from core.sentinel.sentinel import _dispatch
        f = Finding(type="stale_decision", content="Old decision.", urgency="low", timing="session_start")
        _dispatch([f])
        assert proactive_queue.size() == 1
        proactive_queue.drain(max_items=10)

    def test_dispatch_mixed_findings_routes_correctly(self):
        from unittest.mock import patch
        from core.sentinel.sentinel import _dispatch
        immediate = Finding(type="calendar_approaching", content="Now.", urgency="high", timing="immediate")
        queued = Finding(type="dormant_project", content="Old project.", urgency="low", timing="session_start")
        with patch("core.sentinel.sentinel._surface_immediate") as mock_surface:
            _dispatch([immediate, queued])
            mock_surface.assert_called_once_with(immediate)
        assert proactive_queue.size() == 1
        proactive_queue.drain(max_items=10)

    def test_calendar_approaching_finding_has_correct_fields(self):
        f = Finding(type="calendar_approaching", content="Standup in 5 minutes.",
                    urgency="high", timing="immediate")
        assert f.type == "calendar_approaching"
        assert f.urgency == "high"
        assert f.timing == "immediate"
        text = proactive_queue.format_findings_for_speech([f])
        assert "Calendar alert" in text
        assert "Standup in 5 minutes" in text
