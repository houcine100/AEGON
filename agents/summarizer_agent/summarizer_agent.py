# agents/summarizer_agent/summarizer_agent.py
# Summarizer Agent — handles summarization, problem breakdown, and analysis.
# Single responsibility: help Sir think clearly and structure information.
# Uses conversation_history for multi-turn context.

from core.orchestration.state import AegonState
from core.orchestration.llm_client import call_llm
from agents.summarizer_agent.summarizer_agent_prompt import (
    SUMMARIZER_PROMPT,
    SUMMARIZER_BREAKDOWN_PROMPT,
    SUMMARIZER_ANALYSIS_PROMPT,
)


# --- Keywords that signal a breakdown request ---
BREAKDOWN_KEYWORDS = [
    "break down",
    "break it down",
    "step by step",
    "steps to",
    "how do i",
    "how can i",
    "what steps",
    "action plan",
    "roadmap for",
    "plan for",
    "how to",
]

# --- Keywords that signal an analysis request ---
ANALYSIS_KEYWORDS = [
    "analyse",
    "analyze",
    "compare",
    "comparison",
    "pros and cons",
    "tradeoffs",
    "trade-offs",
    "which is better",
    "what do you think about",
    "evaluate",
    "assessment",
    "review",
    "your opinion on",
]

# --- Keywords that signal a summarization request ---
SUMMARY_KEYWORDS = [
    "summarize",
    "summarise",
    "summary",
    "sum up",
    "tldr",
    "tl;dr",
    "brief",
    "overview",
    "key points",
    "main points",
    "what are the main",
    "what is the main",
]


def _detect_mode(payload: str) -> str:
    """
    Returns the summarizer mode based on the payload.
    Modes: breakdown | analysis | summary
    Default: summary
    """
    payload_lower = payload.lower()

    if any(kw in payload_lower for kw in BREAKDOWN_KEYWORDS):
        return "breakdown"

    if any(kw in payload_lower for kw in ANALYSIS_KEYWORDS):
        return "analysis"

    return "summary"


def summarizer_agent(state: AegonState) -> AegonState:
    """
    Summarizer Agent node.
    Handles summarization, problem breakdown, and structured analysis.
    Uses conversation_history for multi-turn follow-up context.
    """
    a2a_payload = state.get("a2a_payload") or {}
    payload = a2a_payload.get("payload", state.get("raw_input", ""))
    memory_context = state.get("memory_context") or ""
    conversation_history = state.get("conversation_history") or ""
    decision_log = state.get("decision_log") or []

    # Detect which mode to use
    mode = _detect_mode(payload)

    # Select the correct system prompt
    if mode == "breakdown":
        base_prompt = SUMMARIZER_BREAKDOWN_PROMPT
    elif mode == "analysis":
        base_prompt = SUMMARIZER_ANALYSIS_PROMPT
    else:
        base_prompt = SUMMARIZER_PROMPT

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
        temperature=0.4,
    )

    # Log the decision
    decision_log.append({
        "node": "summarizer_agent",
        "mode": mode,
        "active_mode": active_mode,
        "payload_received": payload,
        "history_injected": bool(conversation_history),
        "worker_response": response,
    })

    return {
        **state,
        "worker_response": response,
        "decision_log": decision_log,
    }