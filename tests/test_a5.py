# tests/test_a5.py
# Gate test for Phase A5.1 — Mode Auto-Detection.
# Tests infer_mode_from_context() and helpers in isolation.
# No DB, no calendar API, no voice.
#
# Run: python -m pytest tests/test_a5.py -v

from unittest.mock import patch, MagicMock
from datetime import datetime


def _at_hour(hour: int):
    """Return a datetime mock fixed to the given hour."""
    return datetime(2026, 6, 13, hour, 0, 0)


# ── infer_mode_from_context ──────────────────────────────────────────────────

class TestInferModeFromContext:
    def test_hour_7_returns_morning(self):
        import core.modes.mode_detector as md
        with patch.object(md, "datetime") as mock_dt:
            mock_dt.now.return_value = _at_hour(7)
            assert md.infer_mode_from_context() == "morning"

    def test_hour_6_returns_morning(self):
        import core.modes.mode_detector as md
        with patch.object(md, "datetime") as mock_dt:
            mock_dt.now.return_value = _at_hour(6)
            assert md.infer_mode_from_context() == "morning"

    def test_hour_9_not_morning(self):
        """09:00 is no longer morning — boundary check."""
        import core.modes.mode_detector as md
        with patch.object(md, "datetime") as mock_dt, \
             patch.object(md, "_has_imminent_event", return_value=False), \
             patch.object(md, "_infer_from_recent_activity", return_value=""):
            mock_dt.now.return_value = _at_hour(9)
            assert md.infer_mode_from_context() == "standard"

    def test_hour_23_returns_night(self):
        import core.modes.mode_detector as md
        with patch.object(md, "datetime") as mock_dt:
            mock_dt.now.return_value = _at_hour(23)
            assert md.infer_mode_from_context() == "night"

    def test_hour_2_returns_night(self):
        import core.modes.mode_detector as md
        with patch.object(md, "datetime") as mock_dt:
            mock_dt.now.return_value = _at_hour(2)
            assert md.infer_mode_from_context() == "night"

    def test_imminent_event_returns_focus(self):
        import core.modes.mode_detector as md
        with patch.object(md, "datetime") as mock_dt, \
             patch.object(md, "_has_imminent_event", return_value=True):
            mock_dt.now.return_value = _at_hour(14)
            assert md.infer_mode_from_context() == "focus"

    def test_coding_activity_returns_deep_work(self):
        import core.modes.mode_detector as md
        with patch.object(md, "datetime") as mock_dt, \
             patch.object(md, "_has_imminent_event", return_value=False), \
             patch.object(md, "_infer_from_recent_activity", return_value="deep_work"):
            mock_dt.now.return_value = _at_hour(14)
            assert md.infer_mode_from_context() == "deep_work"

    def test_research_activity_returns_research(self):
        import core.modes.mode_detector as md
        with patch.object(md, "datetime") as mock_dt, \
             patch.object(md, "_has_imminent_event", return_value=False), \
             patch.object(md, "_infer_from_recent_activity", return_value="research"):
            mock_dt.now.return_value = _at_hour(14)
            assert md.infer_mode_from_context() == "research"

    def test_no_signals_returns_standard(self):
        import core.modes.mode_detector as md
        with patch.object(md, "datetime") as mock_dt, \
             patch.object(md, "_has_imminent_event", return_value=False), \
             patch.object(md, "_infer_from_recent_activity", return_value=""):
            mock_dt.now.return_value = _at_hour(14)
            assert md.infer_mode_from_context() == "standard"

    def test_time_takes_priority_over_calendar(self):
        """Morning time (hour 7) fires before calendar check is even called."""
        import core.modes.mode_detector as md
        with patch.object(md, "datetime") as mock_dt, \
             patch.object(md, "_has_imminent_event") as mock_cal:
            mock_dt.now.return_value = _at_hour(7)
            result = md.infer_mode_from_context()
        assert result == "morning"
        mock_cal.assert_not_called()

    def test_calendar_takes_priority_over_activity(self):
        """Calendar focus fires before activity check is called."""
        import core.modes.mode_detector as md
        with patch.object(md, "datetime") as mock_dt, \
             patch.object(md, "_has_imminent_event", return_value=True), \
             patch.object(md, "_infer_from_recent_activity") as mock_act:
            mock_dt.now.return_value = _at_hour(14)
            result = md.infer_mode_from_context()
        assert result == "focus"
        mock_act.assert_not_called()


# ── _has_imminent_event — exception safety ───────────────────────────────────

class TestHasImminentEventSafety:
    def test_calendar_service_none_returns_false(self):
        """Returns False when calendar service is unavailable, never raises."""
        import core.modes.mode_detector as md
        gmail_mock = MagicMock()
        gmail_mock.get_calendar_service.return_value = None
        with patch.dict("sys.modules", {"core.security.gmail_auth": gmail_mock}):
            result = md._has_imminent_event()
        assert result is False

    def test_exception_returns_false(self):
        """Any exception in calendar path returns False — never crashes session start."""
        import core.modes.mode_detector as md
        gmail_mock = MagicMock()
        gmail_mock.get_calendar_service.side_effect = RuntimeError("no auth")
        with patch.dict("sys.modules", {"core.security.gmail_auth": gmail_mock}):
            result = md._has_imminent_event()
        assert result is False


# ── _infer_from_recent_activity — signal detection ──────────────────────────

class TestInferFromRecentActivity:
    def test_no_facts_returns_empty(self):
        """No recent facts → standard (no signal)."""
        import core.modes.mode_detector as md
        mem_mock = MagicMock()
        mem_mock.get_recent_facts.return_value = []
        with patch.dict("sys.modules", {"core.memory.memory_store": mem_mock}):
            result = md._infer_from_recent_activity()
        assert result == ""

    def test_coding_keyword_returns_deep_work(self):
        import core.modes.mode_detector as md
        mem_mock = MagicMock()
        mem_mock.get_recent_facts.return_value = [
            {"fact": "Sir was debugging a Python function.", "form": "event"}
        ]
        with patch.dict("sys.modules", {"core.memory.memory_store": mem_mock}):
            result = md._infer_from_recent_activity()
        assert result == "deep_work"

    def test_research_keyword_returns_research(self):
        import core.modes.mode_detector as md
        mem_mock = MagicMock()
        mem_mock.get_recent_facts.return_value = [
            {"fact": "Sir was reading a research paper on LLMs.", "form": "event"}
        ]
        with patch.dict("sys.modules", {"core.memory.memory_store": mem_mock}):
            result = md._infer_from_recent_activity()
        assert result == "research"

    def test_db_exception_returns_empty(self):
        """DB failure silently returns '' — never crashes session start."""
        import core.modes.mode_detector as md
        mem_mock = MagicMock()
        mem_mock.get_recent_facts.side_effect = RuntimeError("DB down")
        with patch.dict("sys.modules", {"core.memory.memory_store": mem_mock}):
            result = md._infer_from_recent_activity()
        assert result == ""

    def test_coding_takes_priority_over_research_when_both_present(self):
        """If both signals present, coding wins (deep_work checked first)."""
        import core.modes.mode_detector as md
        mem_mock = MagicMock()
        mem_mock.get_recent_facts.return_value = [
            {"fact": "Sir was coding while reading research notes.", "form": "event"}
        ]
        with patch.dict("sys.modules", {"core.memory.memory_store": mem_mock}):
            result = md._infer_from_recent_activity()
        assert result == "deep_work"
