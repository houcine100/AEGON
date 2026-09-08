# tests/test_b1.py
# Gate test for Phase B1 — Domain Understanding Layer.
# No DB, no LLM, no live orchestrator.
#
# Run: python -m pytest tests/test_b1.py -v

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest


# ── project_model_store ──────────────────────────────────────────────────────

class TestProjectModelStore:
    def _mock_conn(self, rows=None):
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchall.return_value = rows or []
        mock_cur.fetchone.return_value = rows[0] if rows else None
        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        return mock_conn, mock_cur

    def test_get_all_returns_list(self):
        import core.memory.project_model_store as pms
        mock_conn, _ = self._mock_conn(rows=[{"id": 1, "name": "Aegon", "blockers": None}])
        with patch("core.memory.project_model_store.psycopg2.connect", return_value=mock_conn):
            result = pms.get_all_project_models()
        assert isinstance(result, list)
        assert result[0]["name"] == "Aegon"

    def test_get_project_model_not_found(self):
        import core.memory.project_model_store as pms
        mock_conn, _ = self._mock_conn(rows=[])
        with patch("core.memory.project_model_store.psycopg2.connect", return_value=mock_conn):
            result = pms.get_project_model("nonexistent")
        assert result is None

    def test_upsert_executes_sql(self):
        import core.memory.project_model_store as pms
        mock_conn, mock_cur = self._mock_conn()
        with patch("core.memory.project_model_store.psycopg2.connect", return_value=mock_conn):
            pms.upsert_project_model(
                name="Aegon",
                domain="software",
                current_state="Building B1",
                next_decision="Write tests",
                blockers=None,
                confidence=0.9,
            )
        mock_cur.execute.assert_called_once()
        sql = mock_cur.execute.call_args[0][0]
        assert "INSERT INTO project_models" in sql
        assert "ON CONFLICT" in sql

    def test_clear_blocker_executes_update(self):
        import core.memory.project_model_store as pms
        mock_conn, mock_cur = self._mock_conn()
        with patch("core.memory.project_model_store.psycopg2.connect", return_value=mock_conn):
            pms.clear_blocker("Aegon")
        sql = mock_cur.execute.call_args[0][0]
        assert "blockers = NULL" in sql


# ── project_model_updater ────────────────────────────────────────────────────

class TestProjectModelUpdater:
    def test_no_project_keywords_skips_llm(self):
        import core.memory.project_model_updater as pmu
        with patch.object(pmu, "call_llm") as mock_llm:
            pmu.maybe_update_project_models("how are you today", "I am well.")
        mock_llm.assert_not_called()

    def test_project_keyword_calls_llm(self):
        import core.memory.project_model_updater as pmu
        with patch.object(pmu, "call_llm", return_value="{}"), \
             patch.object(pmu, "upsert_project_model"):
            pmu.maybe_update_project_models("I am building a new project", "Got it.")

    def test_empty_json_skips_upsert(self):
        import core.memory.project_model_updater as pmu
        with patch.object(pmu, "call_llm", return_value="{}"), \
             patch.object(pmu, "upsert_project_model") as mock_upsert:
            pmu.maybe_update_project_models("working on project x", "Noted.")
        mock_upsert.assert_not_called()

    def test_no_name_field_skips_upsert(self):
        import core.memory.project_model_updater as pmu
        payload = json.dumps({"domain": "software", "confidence": 0.8})
        with patch.object(pmu, "call_llm", return_value=payload), \
             patch.object(pmu, "upsert_project_model") as mock_upsert:
            pmu.maybe_update_project_models("building something", "Sure.")
        mock_upsert.assert_not_called()

    def test_valid_extraction_calls_upsert(self):
        import core.memory.project_model_updater as pmu
        payload = json.dumps({
            "name": "Aegon",
            "domain": "software",
            "current_state": "Building B1",
            "confidence": 0.9,
        })
        with patch.object(pmu, "call_llm", return_value=payload), \
             patch.object(pmu, "upsert_project_model") as mock_upsert:
            pmu.maybe_update_project_models("working on building Aegon", "Understood.")
        mock_upsert.assert_called_once_with(
            name="Aegon",
            domain="software",
            current_state="Building B1",
            confidence=0.9,
        )

    def test_invalid_json_does_not_raise(self):
        import core.memory.project_model_updater as pmu
        with patch.object(pmu, "call_llm", return_value="not json at all"), \
             patch.object(pmu, "upsert_project_model") as mock_upsert:
            pmu.maybe_update_project_models("building something", ".")
        mock_upsert.assert_not_called()

    def test_unknown_fields_stripped(self):
        import core.memory.project_model_updater as pmu
        payload = json.dumps({"name": "X", "evil_field": "injected", "confidence": 0.5})
        with patch.object(pmu, "call_llm", return_value=payload), \
             patch.object(pmu, "upsert_project_model") as mock_upsert:
            pmu.maybe_update_project_models("project x is being built", ".")
        call_kwargs = mock_upsert.call_args[1]
        assert "evil_field" not in call_kwargs


# ── rule_stale_blocker ───────────────────────────────────────────────────────

class TestRuleStaleBlocker:
    def _model(self, name: str, blockers, age_days: float) -> dict:
        last_updated = datetime.now(timezone.utc) - timedelta(days=age_days)
        return {"name": name, "blockers": blockers, "last_updated": last_updated}

    def test_fires_at_seven_days(self):
        from core.sentinel.rules import rule_stale_blocker
        findings = rule_stale_blocker([self._model("Aegon", "GPU driver issue", 8)])
        assert len(findings) == 1
        assert findings[0].type == "stale_blocker"
        assert "Aegon" in findings[0].content

    def test_no_blocker_skipped(self):
        from core.sentinel.rules import rule_stale_blocker
        assert rule_stale_blocker([self._model("Aegon", None, 10)]) == []

    def test_fresh_blocker_skipped(self):
        from core.sentinel.rules import rule_stale_blocker
        assert rule_stale_blocker([self._model("Aegon", "Still debugging", 3)]) == []

    def test_no_last_updated_skipped(self):
        from core.sentinel.rules import rule_stale_blocker
        assert rule_stale_blocker([{"name": "X", "blockers": "something", "last_updated": None}]) == []

    def test_multiple_models_mixed(self):
        from core.sentinel.rules import rule_stale_blocker
        findings = rule_stale_blocker([
            self._model("Old", "stuck on auth", 9),
            self._model("New", "minor issue", 2),
            self._model("NoBlocker", None, 20),
        ])
        assert len(findings) == 1
        assert "Old" in findings[0].content

    def test_urgency_is_medium(self):
        from core.sentinel.rules import rule_stale_blocker
        assert rule_stale_blocker([self._model("X", "blocked", 8)])[0].urgency == "medium"


# ── run_all_rules calls project_model_store ──────────────────────────────────

class TestRunAllRulesB1:
    def test_project_model_store_queried(self):
        from core.sentinel import rules
        with patch("core.memory.memory_store.get_facts_by_form", return_value=[]), \
             patch("core.memory.project_model_store.get_all_project_models", return_value=[]) as mock_get:
            rules.run_all_rules()
        mock_get.assert_called_once()

    def test_stale_blocker_finding_included(self):
        from core.sentinel import rules
        stale = {
            "name": "TestProject",
            "blockers": "Cannot connect to DB",
            "last_updated": datetime.now(timezone.utc) - timedelta(days=10),
        }
        with patch("core.memory.memory_store.get_facts_by_form", return_value=[]), \
             patch("core.memory.project_model_store.get_all_project_models", return_value=[stale]):
            findings = rules.run_all_rules()
        types = [f.type for f in findings]
        assert "stale_blocker" in types


# ── planner agent model injection ───────────────────────────────────────────

class TestPlannerProjectModelInjection:
    def _run_planner(self, raw_input: str, models: list) -> str:
        from agents.planner_agent.planner_agent import planner_agent
        state = {
            "raw_input": raw_input,
            "a2a_payload": {"payload": raw_input},
            "memory_context": "",
            "conversation_history": "",
            "decision_log": [],
            "active_mode": "standard",
        }
        captured = {}
        def fake_llm(system_prompt="", user_message="", **kw):
            captured["prompt"] = system_prompt
            return "response"

        with patch("core.memory.project_model_store.get_all_project_models", return_value=models), \
             patch("agents.planner_agent.planner_agent.call_llm", side_effect=fake_llm):
            planner_agent(state)
        return captured.get("prompt", "")

    def test_review_injects_project_models(self):
        models = [{"name": "Aegon", "current_state": "Phase B", "blockers": None, "next_decision": "Build B1"}]
        prompt = self._run_planner("what are my tasks", models)
        assert "Project models" in prompt
        assert "Aegon" in prompt

    def test_prioritize_injects_project_models(self):
        models = [{"name": "X", "current_state": "started", "blockers": "auth issue", "next_decision": None}]
        prompt = self._run_planner("what should I focus on", models)
        assert "Project models" in prompt
        assert "Blocked: auth issue" in prompt

    def test_goal_mode_does_not_inject_models(self):
        models = [{"name": "Y", "current_state": "early", "blockers": None, "next_decision": None}]
        prompt = self._run_planner("I want to build a fitness tracker", models)
        assert "Project models" not in prompt

    def test_empty_models_list_no_injection(self):
        prompt = self._run_planner("what are my tasks", [])
        assert "Project models" not in prompt
