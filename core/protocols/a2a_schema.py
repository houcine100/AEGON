# core/protocols/a2a_schema.py
# Defines the A2A message schema.
# Every message between nodes uses this structure.
# No free-form strings passed between agents — typed payloads only.

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class A2AMessage:
    sender: str            # which node sent this
    receiver: str          # which node receives this
    intent: str            # the classified intent label
    payload: str           # the actual content to process
    session_id: str        # ties back to AegonState
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    confidence: float = 1.0
    requires_approval: bool = False
    tool_name: str = ""        # Phase 5: which tool to run, "" if not a tool route
    tool_input: dict = None    # Phase 5: tool input, e.g. {"query": "..."}
    tool_calls: list = None    # Bug 1b: multiple tools for one turn, [{tool_name, tool_input}, ...]

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "intent": self.intent,
            "payload": self.payload,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "requires_approval": self.requires_approval,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_calls": self.tool_calls,
        }