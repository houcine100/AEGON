# tests/test_a6.py
# Gate test for Phase A6.1 — Weekly Review.
# Tests stats functions and review sections in isolation.
# No DB, no live sentinel, no interactive input.
#
# Run: python -m pytest tests/test_a6.py -v

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import pytest


# ── get_session_stats ────────────────────────────────────────────────────────

class TestGetSessionStats:
    def _make_log(self, tmp_path: Path, records: list) -> Path:
        log = tmp_path / "decisions.jsonl"
        log.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        return log

    def test_empty_log_returns_zeros(self, tmp_path):
        import core.observability.decision_logger as dl
        log = tmp_path / "decisions.jsonl"
        with patch.object(dl, "LOG_FILE", str(log)):
            s = dl.get_session_stats()
        assert s["session_count"] == 0
        assert s["governance_violations"] == 0

    def test_counts_sessions_correctly(self, tmp_path):
        import core.observability.decision_logger as dl
        now = datetime.utcnow()
        records = [
            {"timestamp": now.isoformat(), "session_id": "s1", "intent": "task", "governance_result": "pass"},
            {"timestamp": now.isoformat(), "session_id": "s1", "intent": "task", "governance_result": "pass"},
            {"timestamp": now.isoformat(), "session_id": "s2", "intent": "conversation", "governance_result": "pass"},
        ]
        log = self._make_log(tmp_path, records)
        with patch.object(dl, "LOG_FILE", str(log)):
            s = dl.get_session_stats()
        assert s["session_count"] == 2

    def test_avg_turns_computed(self, tmp_path):
        import core.observability.decision_logger as dl
        now = datetime.utcnow()
        records = [
            {"timestamp": now.isoformat(), "session_id": "s1", "intent": "task", "governance_result": "pass"},
            {"timestamp": now.isoformat(), "session_id": "s1", "intent": "task", "governance_result": "pass"},
            {"timestamp": now.isoformat(), "session_id": "s2", "intent": "task", "governance_result": "pass"},
        ]
        log = self._make_log(tmp_path, records)
        with patch.object(dl, "LOG_FILE", str(log)):
            s = dl.get_session_stats()
        assert s["avg_turns"] == 1.5

    def test_governance_violations_counted(self, tmp_path):
        import core.observability.decision_logger as dl
        now = datetime.utcnow()
        records = [
            {"timestamp": now.isoformat(), "session_id": "s1", "intent": "rule_override_attempt", "governance_result": "fail"},
            {"timestamp": now.isoformat(), "session_id": "s1", "intent": "task", "governance_result": "pass"},
        ]
        log = self._make_log(tmp_path, records)
        with patch.object(dl, "LOG_FILE", str(log)):
            s = dl.get_session_stats()
        assert s["governance_violations"] == 1

    def test_old_records_excluded(self, tmp_path):
        import core.observability.decision_logger as dl
        old = (datetime.utcnow() - timedelta(days=10)).isoformat()
        recent = datetime.utcnow().isoformat()
        records = [
            {"timestamp": old, "session_id": "s_old", "intent": "task", "governance_result": "pass"},
            {"timestamp": recent, "session_id": "s_new", "intent": "task", "governance_result": "pass"},
        ]
        log = self._make_log(tmp_path, records)
        with patch.object(dl, "LOG_FILE", str(log)):
            s = dl.get_session_stats(days=7)
        assert s["session_count"] == 1

    def test_top_intents_returned(self, tmp_path):
        import core.observability.decision_logger as dl
        now = datetime.utcnow().isoformat()
        records = [
            {"timestamp": now, "session_id": "s1", "intent": "task", "governance_result": "pass"},
            {"timestamp": now, "session_id": "s1", "intent": "task", "governance_result": "pass"},
            {"timestamp": now, "session_id": "s1", "intent": "conversation", "governance_result": "pass"},
        ]
        log = self._make_log(tmp_path, records)
        with patch.object(dl, "LOG_FILE", str(log)):
            s = dl.get_session_stats()
        top = dict(s["top_intents"])
        assert top["task"] == 2
        assert top["conversation"] == 1


# ── get_memory_health_stats ──────────────────────────────────────────────────

class TestGetMemoryHealthStats:
    def test_returns_expected_keys(self):
        """Stats dict has all required keys."""
        import core.memory.memory_store as ms
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = {"n": 42}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        with patch.object(ms, "get_connection", return_value=mock_conn):
            stats = ms.get_memory_health_stats()
        assert set(stats.keys()) == {"total_active", "new_this_week", "stale_30_days", "inferences"}


# ── weekly_review sections ───────────────────────────────────────────────────

class TestWeeklyReviewSections:
    def test_print_sentinel_no_crash_when_empty(self, capsys):
        import apps.weekly_review as wr
        feedback_mock = MagicMock()
        feedback_mock.get_hit_rate.return_value = (1.0, 0)
        feedback_mock.should_suppress.return_value = False
        with patch.dict("sys.modules", {"core.feedback.feedback_store": feedback_mock}):
            wr._print_sentinel_performance()
        out = capsys.readouterr().out
        assert "No rated findings" in out

    def test_memory_quality_check_no_facts(self, capsys):
        import apps.weekly_review as wr
        mem_mock = MagicMock()
        mem_mock.get_all_active_facts.return_value = []
        with patch.dict("sys.modules", {"core.memory.memory_store": mem_mock}):
            wr._run_memory_quality_check()
        out = capsys.readouterr().out
        assert "No facts" in out

    def test_memory_quality_check_stores_correction(self, capsys):
        import apps.weekly_review as wr
        facts = [{"id": 1, "fact": "Sir wakes at 5am.", "form": "habit"}]
        mem_mock = MagicMock()
        mem_mock.get_all_active_facts.return_value = facts
        with patch.dict("sys.modules", {"core.memory.memory_store": mem_mock}), \
             patch("builtins.input", side_effect=["c", "Sir wakes at 6am."]):
            wr._run_memory_quality_check()
        mem_mock.update_fact_status.assert_called_once_with(1, "resolved", "Superseded by weekly review correction.")
        mem_mock.store_fact.assert_called_once_with("Sir wakes at 6am.", form="habit", source="weekly_review")

    def test_memory_quality_check_deletes_on_n(self, capsys):
        import apps.weekly_review as wr
        facts = [{"id": 2, "fact": "Sir drinks tea.", "form": "preference"}]
        mem_mock = MagicMock()
        mem_mock.get_all_active_facts.return_value = facts
        with patch.dict("sys.modules", {"core.memory.memory_store": mem_mock}), \
             patch("builtins.input", return_value="n"):
            wr._run_memory_quality_check()
        mem_mock.update_fact_status.assert_called_once_with(2, "resolved", "Marked inaccurate during weekly review.")
        mem_mock.store_fact.assert_not_called()

    def test_memory_quality_check_y_keeps_fact(self, capsys):
        import apps.weekly_review as wr
        facts = [{"id": 3, "fact": "Sir prefers dark mode.", "form": "preference"}]
        mem_mock = MagicMock()
        mem_mock.get_all_active_facts.return_value = facts
        with patch.dict("sys.modules", {"core.memory.memory_store": mem_mock}), \
             patch("builtins.input", return_value="y"):
            wr._run_memory_quality_check()
        mem_mock.update_fact_status.assert_not_called()
        mem_mock.store_fact.assert_not_called()
