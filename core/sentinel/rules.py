# core/sentinel/rules.py
# Five deterministic sentinel rules. No LLM calls.
# Each rule takes a list of fact dicts and returns a list of Findings.
# run_all_rules() fetches from memory and runs all five.

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from core.sentinel.findings import Finding

_ISO_DATE = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')
_DEADLINE_WORDS = ("deadline", "due by", "due on", "must finish by", "ship by", "complete by")
_DAILY_WORDS = ("every day", "daily", "each morning", "each evening", "each night")
_WEEKLY_WORDS = ("every week", "weekly", "each week")
_STOP_WORDS = frozenset(("again", "every", "often", "keeps", "which", "their", "about",
                          "these", "those", "aegon", "noted", "memory", "record"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _age_days(fact: dict) -> float:
    created = fact.get("created_at")
    if created is None:
        return 0.0
    if isinstance(created, datetime) and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (_utcnow() - created).total_seconds() / 86400


def rule_deadline(facts: list) -> list:
    """High urgency: project fact mentions an ISO deadline within 3 days."""
    findings = []
    now = _utcnow()
    window = timedelta(days=3)
    for fact in facts:
        text = fact.get("fact", "")
        if not any(kw in text.lower() for kw in _DEADLINE_WORDS):
            continue
        for match in _ISO_DATE.finditer(text):
            try:
                d = datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if now <= d <= now + window:
                    findings.append(Finding(
                        type="deadline",
                        content=text,
                        urgency="high",
                        timing="session_start",
                    ))
                    break
            except ValueError:
                continue
    return findings


def rule_habit_deviation(facts: list) -> list:
    """Medium urgency: a daily habit not referenced for 2+ days, or weekly for 9+ days."""
    findings = []
    for fact in facts:
        text = fact.get("fact", "").lower()
        age = _age_days(fact)
        if any(kw in text for kw in _DAILY_WORDS) and age > 2:
            findings.append(Finding(
                type="habit_deviation",
                content=fact["fact"],
                urgency="medium",
                timing="session_start",
            ))
        elif any(kw in text for kw in _WEEKLY_WORDS) and age > 9:
            findings.append(Finding(
                type="habit_deviation",
                content=fact["fact"],
                urgency="medium",
                timing="session_start",
            ))
    return findings


def rule_stale_decision(facts: list) -> list:
    """Low urgency: an open decision fact older than 7 days."""
    return [
        Finding(type="stale_decision", content=f["fact"], urgency="low", timing="session_start")
        for f in facts if _age_days(f) > 7
    ]


def rule_dormant_project(facts: list) -> list:
    """Low urgency: a project fact created 14+ days ago (proxy for unreferenced)."""
    return [
        Finding(type="dormant_project", content=f["fact"], urgency="low", timing="session_start")
        for f in facts if _age_days(f) > 14
    ]


def rule_recurring_error(facts: list) -> list:
    """Medium urgency: a content word appears in 3+ distinct error facts."""
    if len(facts) < 3:
        return []
    word_counts: Counter = Counter()
    for fact in facts:
        words = {
            w.lower() for w in re.findall(r'\b\w{5,}\b', fact.get("fact", ""))
            if w.lower() not in _STOP_WORDS
        }
        word_counts.update(words)
    findings = []
    seen: set = set()
    for word, count in word_counts.items():
        if count >= 3 and word not in seen:
            seen.add(word)
            findings.append(Finding(
                type="recurring_error",
                content=f"Pattern '{word}' appears in {count} error records.",
                urgency="medium",
                timing="session_start",
            ))
    return findings


def rule_topic_frequency(recent_facts: list, project_models: list) -> list:
    """Low urgency: a word appears in 3+ distinct recent facts with no matching project model."""
    if len(recent_facts) < 3:
        return []
    project_names_lower = {m["name"].lower() for m in project_models if m.get("name")}
    word_to_facts: dict = {}
    for fact in recent_facts:
        text = fact.get("fact", "")
        words = {
            w.lower() for w in re.findall(r'\b\w{5,}\b', text)
            if w.lower() not in _STOP_WORDS
        }
        for word in words:
            word_to_facts.setdefault(word, set()).add(text)
    findings = []
    seen: set = set()
    for word, fact_texts in word_to_facts.items():
        if len(fact_texts) < 3:
            continue
        if any(word in name or name in word for name in project_names_lower):
            continue
        if word in seen:
            continue
        seen.add(word)
        findings.append(Finding(
            type="topic_frequency",
            content=f"Topic '{word}' appears in {len(fact_texts)} recent facts with no project model. Consider creating one.",
            urgency="low",
            timing="session_start",
        ))
    return findings


def rule_stale_blocker(project_models: list) -> list:
    """Medium urgency: a project model has a blocker unchanged for 7+ days."""
    findings = []
    now = _utcnow()
    for model in project_models:
        if not model.get("blockers"):
            continue
        last_updated = model.get("last_updated")
        if last_updated is None:
            continue
        if isinstance(last_updated, datetime) and last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
        age = (now - last_updated).total_seconds() / 86400
        if age >= 7:
            name = model.get("name", "unknown project")
            findings.append(Finding(
                type="stale_blocker",
                content=f"Project '{name}' has had a blocker for {int(age)} days: {model['blockers']}",
                urgency="medium",
                timing="session_start",
            ))
    return findings


def run_all_rules() -> list:
    """Fetch memory and run all rules. Skips suppressed types (hit-rate < 0.30, ≥5 samples)."""
    from core.memory.memory_store import get_facts_by_form, get_recent_facts
    from core.memory.project_model_store import get_all_project_models
    try:
        from core.feedback.feedback_store import should_suppress
    except Exception:
        def should_suppress(_t): return False  # noqa

    findings = []
    try:
        project_facts = get_facts_by_form("project")
        habit_facts = get_facts_by_form("habit")
        decision_facts = get_facts_by_form("decision")
        error_facts = get_facts_by_form("error")
        project_models = get_all_project_models()
        recent_facts = get_recent_facts(minutes=10080)  # 7 days
    except Exception as e:
        print(f"[sentinel/rules] Memory read failed: {e}")
        return []

    if not should_suppress("deadline"):
        findings.extend(rule_deadline(project_facts))
    if not should_suppress("habit_deviation"):
        findings.extend(rule_habit_deviation(habit_facts))
    if not should_suppress("stale_decision"):
        findings.extend(rule_stale_decision(decision_facts))
    if not should_suppress("dormant_project"):
        findings.extend(rule_dormant_project(project_facts))
    if not should_suppress("recurring_error"):
        findings.extend(rule_recurring_error(error_facts))
    if not should_suppress("stale_blocker"):
        findings.extend(rule_stale_blocker(project_models))
    if not should_suppress("topic_frequency"):
        findings.extend(rule_topic_frequency(recent_facts, project_models))
    return findings
