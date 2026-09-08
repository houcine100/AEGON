# tests/test_a3.py
# Gate test for Phase A3 — Session Context Synthesis + Inference Engine.
# No DB, no LLM — all external calls mocked.
#
# Run: python -m pytest tests/test_a3.py -v

from unittest.mock import patch
from datetime import datetime, timezone, timedelta


# ── A3.1 — build_session_context ──────────────────────────────────────────────

class TestBuildSessionContext:
    # Context is now relevance-gated: build_session_context retrieves via search_facts
    # against the current input. Tests mock search_facts and pass a relevant query.
    QUERY = "tell me about my projects and work"

    def _facts(self):
        return [
            {"form": "project", "fact": "Sir is building Aegon.", "emotional_weight": "neutral", "similarity": 0.6},
            {"form": "project", "fact": "Sir is building a second project.", "emotional_weight": "neutral", "similarity": 0.6},
            {"form": "decision", "fact": "Sir decided to use FastAPI.", "emotional_weight": "neutral", "similarity": 0.6},
            {"form": "habit", "fact": "Sir works at night.", "emotional_weight": "neutral", "similarity": 0.6},
            {"form": "user_profile", "fact": "Sir is a developer.", "emotional_weight": "stressed", "similarity": 0.6},
            {"form": "inference", "fact": "Sir prefers async approaches.", "emotional_weight": "neutral", "similarity": 0.6},
        ]

    def test_returns_string(self):
        from core.memory.context_injector import build_session_context
        with patch("core.memory.context_injector.search_facts", return_value=self._facts()):
            assert isinstance(build_session_context(self.QUERY), str)

    def test_includes_projects(self):
        from core.memory.context_injector import build_session_context
        with patch("core.memory.context_injector.search_facts", return_value=self._facts()):
            result = build_session_context(self.QUERY)
            assert "Aegon" in result and "Active projects" in result

    def test_includes_decisions(self):
        from core.memory.context_injector import build_session_context
        with patch("core.memory.context_injector.search_facts", return_value=self._facts()):
            result = build_session_context(self.QUERY)
            assert "FastAPI" in result and "Open decisions" in result

    def test_includes_emotional_signals(self):
        from core.memory.context_injector import build_session_context
        with patch("core.memory.context_injector.search_facts", return_value=self._facts()):
            result = build_session_context(self.QUERY)
            assert "Recent stressors" in result and "developer" in result

    def test_includes_inferences(self):
        from core.memory.context_injector import build_session_context
        with patch("core.memory.context_injector.search_facts", return_value=self._facts()):
            result = build_session_context(self.QUERY)
            assert "Patterns inferred" in result and "async" in result

    def test_returns_empty_when_no_facts(self):
        from core.memory.context_injector import build_session_context
        with patch("core.memory.context_injector.search_facts", return_value=[]):
            assert build_session_context(self.QUERY) == ""

    def test_omits_sections_with_no_data(self):
        from core.memory.context_injector import build_session_context
        facts = [{"form": "project", "fact": "Aegon.", "emotional_weight": "neutral", "similarity": 0.6}]
        with patch("core.memory.context_injector.search_facts", return_value=facts):
            result = build_session_context(self.QUERY)
            assert "Open decisions" not in result
            assert "Recent stressors" not in result
            assert "Patterns inferred" not in result

    def test_no_llm_call(self):
        from core.memory.context_injector import build_session_context
        with patch("core.memory.context_injector.search_facts", return_value=self._facts()):
            with patch("core.memory.context_injector.call_llm") as mock_llm:
                build_session_context(self.QUERY)
                mock_llm.assert_not_called()


# ── A3.2 — inference_engine ───────────────────────────────────────────────────

class TestIsDue:
    def test_due_when_no_timestamp(self, tmp_path):
        import core.memory.inference_engine as ie
        with patch.object(ie, "_TS_FILE", tmp_path / ".inference_ts"):
            assert ie.is_due() is True

    def test_not_due_when_run_today(self, tmp_path):
        import core.memory.inference_engine as ie
        ts_file = tmp_path / ".inference_ts"
        ts_file.write_text(str(datetime.now(timezone.utc).timestamp()))
        with patch.object(ie, "_TS_FILE", ts_file):
            assert ie.is_due() is False

    def test_due_when_run_8_days_ago(self, tmp_path):
        import core.memory.inference_engine as ie
        ts_file = tmp_path / ".inference_ts"
        old = datetime.now(timezone.utc) - timedelta(days=8)
        ts_file.write_text(str(old.timestamp()))
        with patch.object(ie, "_TS_FILE", ts_file):
            assert ie.is_due() is True


class TestRunInference:
    def _facts(self, n=6):
        return [{"form": "project", "fact": f"Fact {i}", "emotional_weight": "neutral"} for i in range(n)]

    def test_skips_when_too_few_facts(self, tmp_path):
        import core.memory.inference_engine as ie
        with patch.object(ie, "_TS_FILE", tmp_path / ".inference_ts"):
            with patch("core.memory.inference_engine.get_all_active_facts", return_value=self._facts(3)):
                with patch("core.memory.inference_engine.call_llm") as mock_llm:
                    result = ie.run_inference()
                    mock_llm.assert_not_called()
                    assert result == 0

    def test_calls_llm_with_enough_facts(self, tmp_path):
        import core.memory.inference_engine as ie
        with patch.object(ie, "_TS_FILE", tmp_path / ".inference_ts"):
            with patch("core.memory.inference_engine.get_all_active_facts", return_value=self._facts(6)):
                with patch("core.memory.inference_engine.call_llm", return_value="[]") as mock_llm:
                    with patch("core.memory.inference_engine.store_fact"):
                        ie.run_inference()
                        mock_llm.assert_called_once()

    def test_stores_inferences_with_correct_form_and_source(self, tmp_path):
        import core.memory.inference_engine as ie
        llm_resp = '[{"inference": "Sir works at night.", "confidence": "high", "supporting_count": 3}]'
        with patch.object(ie, "_TS_FILE", tmp_path / ".inference_ts"):
            with patch("core.memory.inference_engine.get_all_active_facts", return_value=self._facts(6)):
                with patch("core.memory.inference_engine.call_llm", return_value=llm_resp):
                    with patch("core.memory.inference_engine.store_fact", return_value=1) as mock_store:
                        ie.run_inference()
                        mock_store.assert_called_once()
                        kw = mock_store.call_args.kwargs
                        assert kw.get("form") == "inference"
                        assert kw.get("source") == "inference_engine"

    def test_excludes_existing_inferences_from_source(self, tmp_path):
        import core.memory.inference_engine as ie
        facts = self._facts(6) + [{"form": "inference", "fact": "Existing.", "emotional_weight": "neutral"}]
        with patch.object(ie, "_TS_FILE", tmp_path / ".inference_ts"):
            with patch("core.memory.inference_engine.get_all_active_facts", return_value=facts):
                with patch("core.memory.inference_engine.call_llm", return_value="[]") as mock_llm:
                    with patch("core.memory.inference_engine.store_fact"):
                        ie.run_inference()
                        prompt = mock_llm.call_args.kwargs.get("user_message", "")
                        assert "Existing" not in prompt

    def test_saves_timestamp_after_run(self, tmp_path):
        import core.memory.inference_engine as ie
        ts_file = tmp_path / ".inference_ts"
        with patch.object(ie, "_TS_FILE", ts_file):
            with patch("core.memory.inference_engine.get_all_active_facts", return_value=self._facts(6)):
                with patch("core.memory.inference_engine.call_llm", return_value="[]"):
                    with patch("core.memory.inference_engine.store_fact"):
                        ie.run_inference()
                        assert ts_file.exists()

    def test_handles_malformed_llm_response(self, tmp_path):
        import core.memory.inference_engine as ie
        with patch.object(ie, "_TS_FILE", tmp_path / ".inference_ts"):
            with patch("core.memory.inference_engine.get_all_active_facts", return_value=self._facts(6)):
                with patch("core.memory.inference_engine.call_llm", return_value="not valid json"):
                    with patch("core.memory.inference_engine.store_fact"):
                        assert ie.run_inference() == 0


class TestMaybeRunInference:
    def test_does_not_run_when_not_due(self, tmp_path):
        import core.memory.inference_engine as ie
        ts_file = tmp_path / ".inference_ts"
        ts_file.write_text(str(datetime.now(timezone.utc).timestamp()))
        with patch.object(ie, "_TS_FILE", ts_file):
            with patch("core.memory.inference_engine.run_inference") as mock_run:
                ie.maybe_run_inference()
                mock_run.assert_not_called()

    def test_runs_when_due(self, tmp_path):
        import core.memory.inference_engine as ie
        with patch.object(ie, "_TS_FILE", tmp_path / ".inference_ts"):
            with patch("core.memory.inference_engine.run_inference", return_value=2) as mock_run:
                result = ie.maybe_run_inference()
                mock_run.assert_called_once()
                assert result == 2
