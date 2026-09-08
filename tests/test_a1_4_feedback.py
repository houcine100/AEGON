# tests/test_a1_4_feedback.py
# Gate test for Phase A1.4 — Feedback Store.
# Tests feedback_store in isolation. No DB, no voice, no LLM.
#
# Run: python -m pytest tests/test_a1_4_feedback.py -v

import json
from pathlib import Path
from unittest.mock import patch


# ── TestLogFinding ─────────────────────────────────────────────────────────────

class TestLogFinding:
    def test_returns_uuid_string(self, tmp_path):
        import core.feedback.feedback_store as fs
        with patch.object(fs, "_LOG_FILE", tmp_path / "feedback_log.json"):
            fid = fs.log_finding("deadline", "Ship by Friday.", "high")
            assert isinstance(fid, str) and len(fid) == 36

    def test_record_written_to_file(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            fid = fs.log_finding("deadline", "Ship by Friday.", "high")
            records = json.loads(log.read_text())
            assert len(records) == 1
            assert records[0]["id"] == fid
            assert records[0]["type"] == "deadline"
            assert records[0]["verdict"] is None

    def test_multiple_findings_accumulate(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            fs.log_finding("deadline", "A", "high")
            fs.log_finding("dormant_project", "B", "low")
            records = json.loads(log.read_text())
            assert len(records) == 2


# ── TestRecordResponse ─────────────────────────────────────────────────────────

class TestRecordResponse:
    def test_records_useful_verdict(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            fid = fs.log_finding("deadline", "Soon.", "high")
            result = fs.record_response(fid, "useful")
            assert result is True
            records = json.loads(log.read_text())
            assert records[0]["verdict"] == "useful"

    def test_records_not_relevant_verdict(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            fid = fs.log_finding("habit_deviation", "Exercise.", "medium")
            fs.record_response(fid, "not_relevant")
            records = json.loads(log.read_text())
            assert records[0]["verdict"] == "not_relevant"

    def test_returns_false_for_unknown_id(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            result = fs.record_response("nonexistent-id", "useful")
            assert result is False

    def test_responded_at_field_set(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            fid = fs.log_finding("deadline", "Now.", "high")
            fs.record_response(fid, "useful")
            records = json.loads(log.read_text())
            assert "responded_at" in records[0]


# ── TestHitRate ────────────────────────────────────────────────────────────────

class TestHitRate:
    def test_all_useful_returns_1(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            for _ in range(3):
                fid = fs.log_finding("deadline", "x", "high")
                fs.record_response(fid, "useful")
            rate, count = fs.get_hit_rate("deadline")
            assert rate == 1.0 and count == 3

    def test_all_irrelevant_returns_0(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            for _ in range(3):
                fid = fs.log_finding("habit_deviation", "x", "medium")
                fs.record_response(fid, "not_relevant")
            rate, count = fs.get_hit_rate("habit_deviation")
            assert rate == 0.0 and count == 3

    def test_no_data_returns_1_and_0(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            rate, count = fs.get_hit_rate("deadline")
            assert rate == 1.0 and count == 0

    def test_unrated_findings_excluded(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            fs.log_finding("deadline", "unrated", "high")
            fid = fs.log_finding("deadline", "rated", "high")
            fs.record_response(fid, "useful")
            rate, count = fs.get_hit_rate("deadline")
            assert count == 1 and rate == 1.0


# ── TestSuppression ────────────────────────────────────────────────────────────

class TestSuppression:
    def test_not_suppressed_with_insufficient_samples(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            for _ in range(3):
                fid = fs.log_finding("dormant_project", "x", "low")
                fs.record_response(fid, "not_relevant")
            assert fs.should_suppress("dormant_project") is False

    def test_suppressed_when_low_hit_rate_and_enough_samples(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            for _ in range(5):
                fid = fs.log_finding("dormant_project", "x", "low")
                fs.record_response(fid, "not_relevant")
            assert fs.should_suppress("dormant_project") is True

    def test_not_suppressed_when_high_hit_rate(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            for _ in range(5):
                fid = fs.log_finding("deadline", "x", "high")
                fs.record_response(fid, "useful")
            assert fs.should_suppress("deadline") is False


# ── TestWeeklyReport ───────────────────────────────────────────────────────────

class TestWeeklyReport:
    def test_empty_returns_no_rated_message(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            report = fs.get_weekly_report()
            assert "No rated findings" in report

    def test_report_includes_finding_type(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            fid = fs.log_finding("deadline", "Ship it.", "high")
            fs.record_response(fid, "useful")
            report = fs.get_weekly_report()
            assert "Deadline" in report
            assert "100%" in report

    def test_report_marks_suppressed_types(self, tmp_path):
        import core.feedback.feedback_store as fs
        log = tmp_path / "feedback_log.json"
        with patch.object(fs, "_LOG_FILE", log):
            for _ in range(5):
                fid = fs.log_finding("dormant_project", "x", "low")
                fs.record_response(fid, "not_relevant")
            report = fs.get_weekly_report()
            assert "suppressed" in report
