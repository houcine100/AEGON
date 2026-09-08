# schemas/intent_schema.py
# Single source of truth for all valid intent labels.
# Every node that reads or writes intent imports from here.
# Never hardcode intent strings anywhere else.

class Intent:
    CONVERSATION = "conversation"
    TASK = "task"
    MEMORY_QUERY = "memory_query"
    MEMORY_DELETE = "memory_delete"
    SUMMARIZE_REQUEST = "summarize_request"
    PLAN_REQUEST = "plan_request"
    MODE_SWITCH = "mode_switch"
    CLARIFICATION_NEEDED = "clarification_needed"
    RULE_OVERRIDE_ATTEMPT = "rule_override_attempt"
    FINDING_FEEDBACK = "finding_feedback"
    NOTE_REMEMBER = "note_remember"

    ALL = [
        CONVERSATION,
        TASK,
        MEMORY_QUERY,
        MEMORY_DELETE,
        SUMMARIZE_REQUEST,
        PLAN_REQUEST,
        MODE_SWITCH,
        CLARIFICATION_NEEDED,
        RULE_OVERRIDE_ATTEMPT,
        FINDING_FEEDBACK,
        NOTE_REMEMBER,
    ]