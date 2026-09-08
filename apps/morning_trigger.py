# apps/morning_trigger.py
# External morning mode trigger. Run this 30 minutes after Sir's alarm.
# Bypasses the LangGraph intent classifier — calls the runner directly.
#
# Usage (from project root, venv active):
#   python -m apps.morning_trigger
#
# Scheduling (Windows Task Scheduler or cron):
#   Set trigger: 30 minutes after alarm time.
#
# Future: before run_briefing(), add smart home calls here:
#   CurtainsConnector().execute({})      — opens curtains (always_gated → auto-approve here)
#   CoffeeMachineConnector().execute({}) — starts coffee  (always_gated → auto-approve here)

import sys
from core.modes.morning_mode_runner import run_briefing


def main() -> None:
    print("[morning_trigger] Starting morning briefing...")
    try:
        briefing = run_briefing()
    except Exception as e:
        print(f"[morning_trigger] Briefing failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nAegon: {briefing}\n")
    # TTS hook: when voice is wired, replace the print above with speak(briefing).


if __name__ == "__main__":
    main()
