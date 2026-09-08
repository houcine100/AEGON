# core/sentinel/findings.py
# The Finding dataclass — what the sentinel produces and the orchestrator consumes.

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Finding:
    type: str           # deadline | habit_deviation | stale_decision | dormant_project | recurring_error
    content: str        # the triggering fact text or summary
    urgency: str        # high | medium | low
    timing: str         # session_start | immediate
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    surfaced: bool = False
    sir_response: Optional[str] = None  # acted_on | dismissed | not_relevant
