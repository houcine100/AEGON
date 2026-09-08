# tests/test_context_relevance.py
# 2026-06-21: context injection is relevance-gated, not a dump. Facts reach a turn's
# prompt only when they bear on what Sir just said. A greeting pulls nothing.

from unittest.mock import patch
import core.memory.context_injector as ci


def _fact(text, form="project", sim=0.6, weight="neutral"):
    return {"fact": text, "form": form, "emotional_weight": weight, "similarity": sim}


# ── empty / greeting → nothing ─────────────────────────────────────────────────

def test_empty_query_injects_nothing():
    assert ci.build_memory_context("") == ""
    assert ci.build_session_context("") == ""


def test_greeting_pulls_no_history():
    # greeting has no semantic match → search returns low-similarity rows only
    with patch.object(ci, "search_facts", return_value=[_fact("Sir is building Aegon.", sim=0.05)]):
        assert ci.build_memory_context("hello how are you") == ""


# ── relevance gating ───────────────────────────────────────────────────────────

def test_below_threshold_excluded():
    with patch.object(ci, "search_facts", return_value=[_fact("unrelated note", sim=ci.RELEVANCE_THRESHOLD - 0.05)]):
        assert ci.build_memory_context("tell me about my car") == ""


def test_relevant_fact_included():
    with patch.object(ci, "search_facts", return_value=[_fact("Sir is building Aegon.", sim=0.6)]):
        out = ci.build_memory_context("how is aegon going")
    assert "Sir is building Aegon." in out


def test_session_context_only_relevant():
    with patch.object(ci, "search_facts", return_value=[_fact("Sir is building Aegon.", sim=0.6)]):
        out = ci.build_session_context("how is aegon going")
    assert "Active projects" in out
    assert "Sir is building Aegon." in out
