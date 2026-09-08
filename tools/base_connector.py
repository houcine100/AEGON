# tools/base_connector.py
# The template every connector (tool) must follow.
# A connector is executable code that performs a real-world action.
# Every tool inherits from BaseConnector and fills in the blanks.

from abc import ABC, abstractmethod

# The only permission levels allowed. Must match connector.json.
READ_ONLY = "read_only"        # runs freely, no approval (e.g. web search)
WRITE_GATED = "write_gated"    # needs approval to act (e.g. file write)
ALWAYS_GATED = "always_gated"  # always needs approval (e.g. house security)

VALID_PERMISSION_LEVELS = frozenset({READ_ONLY, WRITE_GATED, ALWAYS_GATED})


class BaseConnector(ABC):
    """Every tool inherits this. Defines what a tool must provide."""

    # Each tool sets these from its connector.json (loaded by the registry).
    name: str = "unnamed"
    version: str = "0.0.0"
    description: str = ""
    permission_level: str = WRITE_GATED   # safe default: needs approval

    @abstractmethod
    def validate(self, payload: dict) -> bool:
        """Check the input is well-formed BEFORE running. Return True if OK."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, payload: dict) -> dict:
        """Do the actual work. Return {"status": ..., "output": ...}."""
        raise NotImplementedError

    def requires_approval(self) -> bool:
        """True if this tool needs Sir's sign-off before acting."""
        return self.permission_level in (WRITE_GATED, ALWAYS_GATED)

    def approval_prompt(self, payload: dict) -> str:
        """Message shown before a gated action runs. Override for a richer prompt."""
        if payload.get("path"):
            return f"This will write to {payload.get('path')}. Shall I proceed, Sir?"
        return f"This will run {self.name}. Shall I proceed, Sir?"

    def redact_for_log(self, payload: dict, result: dict) -> tuple:
        """Return (payload, result) safe to write to the tool log.
        Override to hide sensitive content (e.g. email bodies)."""
        return payload, result

    def describe(self) -> dict:
        """Return the tool's ID card — used by the registry and logs."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "permission_level": self.permission_level,
            "requires_approval": self.requires_approval(),
        }