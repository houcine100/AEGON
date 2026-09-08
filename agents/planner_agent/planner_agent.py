# agents/planner_agent/planner_agent.py
# Planner Agent — breaks goals into steps, tracks active tasks, manages commitments.
# Single responsibility: help Sir plan and execute.
# Stores active plans in memory as project form facts.
# Uses conversation_history for multi-turn context.

from core.orchestration.state import AegonState
from core.orchestration.llm_client import call_llm
from core.memory.memory_store import store_fact
from agents.planner_agent.planner_agent_prompt import (
    PLANNER_PROMPT,
    PLANNER_GOAL_PROMPT,
    PLANNER_REVIEW_PROMPT,
    PLANNER_PRIORITIZE_PROMPT,
)


# --- Keywords that signal a goal breakdown request ---
GOAL_KEYWORDS = [
    "plan for",
    "plan to",
    "how do i achieve",
    "help me achieve",
    "i want to",
    "i need to",
    "my goal is",
    "help me reach",
    "roadmap for",
    "strategy for",
    "how to achieve",
    "help me build",
    "help me start",
    "help me finish",
]

# --- Keywords that signal a task review request ---
REVIEW_KEYWORDS = [
    "what are my tasks",
    "what do i need to do",
    "show my tasks",
    "list my tasks",
    "what is pending",
    "what is outstanding",
    "what have i committed to",
    "what did i say i would do",
    "what should i be working on",
    "review my tasks",
    "task list",
    "to do list",
    "todo list",
]

# --- Keywords that signal a prioritization request ---
PRIORITIZE_KEYWORDS = [
    "what should i focus on",
    "what is most important",
    "prioritize",
    "what first",
    "where to start",
    "what to do first",
    "help me prioritize",
    "what is urgent",
    "what is the priority",
    "order of priority",
]


def _detect_mode(payload: str) -> str:
    """
    Returns the planner mode based on the payload.
    Modes: goal | review | prioritize | general
    Default: general
    """
    payload_lower = payload.lower()

    if any(kw in payload_lower for kw in REVIEW_KEYWORDS):
        return "review"

    if any(kw in payload_lower for kw in PRIORITIZE_KEYWORDS):
        return "prioritize"

    if any(kw in payload_lower for kw in GOAL_KEYWORDS):
        return "goal"

    return "general"


def _extract_goal_summary(payload: str) -> str:
    """
    Extracts a short one-sentence goal summary from the payload.
    Used for storing the active plan in memory.
    """
    # Remove common filler phrases to get the core goal
    payload_lower = payload.lower()
    for phrase in ["i want to", "i need to", "help me", "my goal is", "plan for",
                   "help me build", "help me start", "help me finish", "how to"]:
        if phrase in payload_lower:
            # Extract the part after the keyword
            idx = payload_lower.find(phrase) + len(phrase)
            goal = payload[idx:].strip()
            if goal:
                return f"Sir is working on: {goal}"
    return f"Sir is working on: {payload}"


def planner_agent(state: AegonState) -> AegonState:
    """
    Planner Agent node.
    Handles goal breakdown, task review, prioritization, and general planning.
    Stores active plans in memory as project form facts.
    Uses conversation_history for multi-turn context.
    """
    a2a_payload = state.get("a2a_payload") or {}
    payload = a2a_payload.get("payload", state.get("raw_input", ""))
    memory_context = state.get("memory_context") or ""
    conversation_history = state.get("conversation_history") or ""
    decision_log = state.get("decision_log") or []

    # Detect which mode to use
    mode = _detect_mode(payload)

    # Select the correct system prompt
    if mode == "goal":
        base_prompt = PLANNER_GOAL_PROMPT
    elif mode == "review":
        base_prompt = PLANNER_REVIEW_PROMPT
    elif mode == "prioritize":
        base_prompt = PLANNER_PRIORITIZE_PROMPT
    else:
        base_prompt = PLANNER_PROMPT

    # Inject project model summaries for review and prioritize modes
    if mode in ("review", "prioritize"):
        try:
            from core.memory.project_model_store import get_all_project_models
            models = get_all_project_models()
            if models:
                lines = []
                for m in models:
                    line = f"- {m['name']}"
                    if m.get("current_state"):
                        line += f": {m['current_state']}"
                    if m.get("blockers"):
                        line += f" | Blocked: {m['blockers']}"
                    if m.get("next_decision"):
                        line += f" | Next: {m['next_decision']}"
                    lines.append(line)
                base_prompt += "\n\nProject models:\n" + "\n".join(lines)
        except Exception as e:
            print(f"[planner_agent] Project model injection failed: {e}")

    # Inject memory context if available
    if memory_context:
        base_prompt += f"\n\nMemory context:\n{memory_context}"

    # Inject conversation history for follow-up context
    if conversation_history:
        base_prompt += f"\n\nRecent conversation:\n{conversation_history}"

    # Inject mode instruction
    from prompts.mode_prompts import get_mode_instruction
    active_mode = state.get("active_mode") or "standard"
    mode_instruction = get_mode_instruction(active_mode)
    if mode_instruction:
        base_prompt += f"\n\n{mode_instruction}"

    # Call LLM
    response = call_llm(
        system_prompt=base_prompt,
        user_message=payload,
        temperature=0.3,
    )

    # Store active plan in memory if this is a goal breakdown
    # This ensures the plan persists across sessions
    if mode == "goal":
        try:
            goal_summary = _extract_goal_summary(payload)
            store_fact(
                fact=goal_summary,
                form="project",
                emotional_weight="neutral",
                stability="temporary",
                source="explicit",
            )
        except Exception as e:
            print(f"[planner_agent] Failed to store plan in memory: {e}")

    # Log the decision
    decision_log.append({
        "node": "planner_agent",
        "mode": mode,
        "active_mode": active_mode,
        "payload_received": payload,
        "history_injected": bool(conversation_history),
        "plan_stored": mode == "goal",
        "worker_response": response,
    })

    return {
        **state,
        "worker_response": response,
        "decision_log": decision_log,
    }