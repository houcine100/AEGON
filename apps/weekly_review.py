# apps/weekly_review.py
# Weekly review — terminal only, not spoken.
# Run every Sunday: python -m apps.weekly_review
# Covers: memory health, sentinel performance, session stats, memory quality check.

import random
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime


_DIV = "─" * 52
_HEADER = "═" * 52


def _section(title: str) -> None:
    print(f"\n{_DIV}")
    print(f"  {title}")
    print(_DIV)


def _print_memory_health() -> None:
    _section("MEMORY HEALTH")
    try:
        from core.memory.memory_store import get_memory_health_stats
        s = get_memory_health_stats()
        print(f"  Total active facts:    {s['total_active']}")
        print(f"  New this week:         {s['new_this_week']}")
        print(f"  Stale (30+ days old):  {s['stale_30_days']}")
        print(f"  Inferences generated:  {s['inferences']}")
    except Exception as e:
        print(f"  [unavailable — {e}]")


def _print_sentinel_performance() -> None:
    _section("SENTINEL PERFORMANCE  (last 7 days)")
    try:
        from core.feedback.feedback_store import get_hit_rate, should_suppress
        finding_types = [
            "deadline", "habit_deviation", "stale_decision",
            "dormant_project", "recurring_error", "stale_blocker",
            "topic_frequency", "deep_work_gap", "calendar_approaching",
        ]
        any_data = False
        for ft in finding_types:
            rate, count = get_hit_rate(ft, days=7)
            if count == 0:
                continue
            any_data = True
            label = ft.replace("_", " ").title().ljust(22)
            tag = "  [suppressed]" if should_suppress(ft) else ""
            print(f"  {label} {int(rate * 100):>3}% useful  ({count} rated){tag}")
        if not any_data:
            print("  No rated findings in the past week.")
    except Exception as e:
        print(f"  [unavailable — {e}]")


def _print_session_stats() -> None:
    _section("SESSION SUMMARY  (last 7 days)")
    try:
        from core.observability.decision_logger import get_session_stats
        s = get_session_stats(days=7)
        print(f"  Sessions:              {s['session_count']}")
        print(f"  Avg turns / session:   {s['avg_turns']}")
        if s["top_intents"]:
            intent_str = ",  ".join(f"{k} ({v})" for k, v in s["top_intents"])
            print(f"  Top intents:           {intent_str}")
        print(f"  Governance blocks:     {s['governance_violations']}")
    except Exception as e:
        print(f"  [unavailable — {e}]")


def _run_memory_quality_check() -> None:
    _section("MEMORY QUALITY CHECK")
    print("  Reviewing 3 random facts.")
    print("  y = accurate   n = inaccurate (delete)   c = correct it\n")

    try:
        from core.memory.memory_store import get_all_active_facts, update_fact_status, store_fact
    except Exception as e:
        print(f"  [unavailable — {e}]")
        return

    try:
        facts = get_all_active_facts()
    except Exception as e:
        print(f"  [could not load facts — {e}]")
        return

    if not facts:
        print("  No facts in memory yet.")
        return

    sample = random.sample(facts, min(3, len(facts)))

    for i, fact in enumerate(sample, 1):
        print(f"  [{i}/3] \"{fact['fact']}\"")
        while True:
            answer = input("  Accurate? (y/n/c): ").strip().lower()
            if answer == "y":
                print("  Kept.\n")
                break
            elif answer == "n":
                try:
                    update_fact_status(fact["id"], "resolved", "Marked inaccurate during weekly review.")
                    print("  Removed.\n")
                except Exception as e:
                    print(f"  [delete failed — {e}]\n")
                break
            elif answer == "c":
                correction = input("  Correction: ").strip()
                if correction:
                    try:
                        update_fact_status(fact["id"], "resolved", "Superseded by weekly review correction.")
                        store_fact(correction, form=fact.get("form", "profile"), source="weekly_review")
                        print("  Corrected and stored.\n")
                    except Exception as e:
                        print(f"  [correction failed — {e}]\n")
                else:
                    print("  Skipped.\n")
                break
            else:
                print("  Please enter y, n, or c.")


def run() -> None:
    today = datetime.now().strftime("%A %Y-%m-%d")
    print(f"\n{_HEADER}")
    print(f"  AEGON WEEKLY REVIEW  —  {today}")
    print(_HEADER)

    _print_memory_health()
    _print_sentinel_performance()
    _print_session_stats()
    _run_memory_quality_check()

    print(f"\n{_HEADER}")
    print("  Review complete.")
    print(_HEADER)


if __name__ == "__main__":
    run()
