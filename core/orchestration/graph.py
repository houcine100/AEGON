# core/orchestration/graph.py
# Builds and compiles the LangGraph state machine.
# Defines all nodes and edges.
# Single source of truth for the flow.
# All communication passes through the orchestrator — no direct agent-to-agent.

from langgraph.graph import StateGraph, END
from core.orchestration.state import AegonState
from core.orchestration.nodes.intent_classifier import intent_classifier
from core.orchestration.nodes.orchestrator_node import orchestrator_node
from core.orchestration.nodes.conversation_node import conversation_node
from core.orchestration.nodes.task_node import task_node
from core.orchestration.nodes.governance_node import governance_node
from core.orchestration.nodes.response_synthesizer import response_synthesizer
from core.orchestration.nodes.approval_handler import approval_handler   # Phase 5 — Step 1
from core.orchestration.nodes.tool_node import tool_node                 # Phase 5 — Step 3d
from agents.memory_agent.memory_agent import memory_agent
from agents.summarizer_agent.summarizer_agent import summarizer_agent
from agents.planner_agent.planner_agent import planner_agent
from core.security.governance_rules import RULE_OVERRIDE_RESPONSE
from prompts.mode_prompts import Mode


# --- Mode switch node ---
# No Groq call needed — just updates active_mode in state.
# Lightweight — 20 lines maximum.

def mode_switch_node(state: AegonState) -> AegonState:
    requested_mode = state.get("requested_mode")
    decision_log = state.get("decision_log") or []

    if requested_mode and requested_mode in Mode.ALL:
        new_mode = requested_mode
        response = f"Switching to {new_mode} mode, Sir."
    else:
        new_mode = Mode.STANDARD
        response = "Switching to standard mode, Sir."

    decision_log.append({
        "node": "mode_switch_node",
        "requested_mode": requested_mode,
        "new_mode": new_mode,
    })

    if new_mode == Mode.MORNING:
        from core.modes.morning_briefing import start_briefing_async
        start_briefing_async()

    return {
        **state,
        "active_mode": new_mode,
        "worker_response": response,
        "governance_result": "pass",
        "governance_reason": "Mode switch — no axiom check needed.",
        "decision_log": decision_log,
    }


# --- Clarification node ---
def clarification_node(state: AegonState) -> AegonState:
    decision_log = state.get("decision_log") or []
    decision_log.append({
        "node": "clarification_node",
        "reason": "Input was too vague or ambiguous.",
    })
    return {
        **state,
        "worker_response": "I did not understand that clearly enough to act, Sir. Could you rephrase?",
        "governance_result": "pass",
        "governance_reason": "Clarification path — no axiom check needed.",
        "decision_log": decision_log,
    }


# --- Feedback node ---
def feedback_node(state: AegonState) -> AegonState:
    from core.feedback.feedback_store import record_response
    from core.sentinel.sentinel import get_last_surfaced_id

    raw = (state.get("raw_input") or "").lower()
    finding_id = get_last_surfaced_id()
    decision_log = state.get("decision_log") or []

    if not finding_id:
        response = "I have no recent finding to rate, Sir."
    else:
        useful_words = ("useful", "good", "relevant", "helpful", "correct", "good catch")
        irrelevant_words = ("not relevant", "irrelevant", "ignore", "wrong", "useless", "skip")
        if any(w in raw for w in useful_words):
            record_response(finding_id, "useful")
            response = "Noted, Sir. I will keep surfacing similar findings."
        elif any(w in raw for w in irrelevant_words):
            record_response(finding_id, "not_relevant")
            response = "Understood, Sir. I will adjust."
        else:
            response = "I did not catch that, Sir. Say 'useful' or 'not relevant'."

    decision_log.append({"node": "feedback_node", "finding_id": finding_id})
    return {
        **state,
        "worker_response": response,
        "governance_result": "pass",
        "governance_reason": "Feedback path — no axiom check needed.",
        "decision_log": decision_log,
    }


# --- Rule override node ---
def rule_override_node(state: AegonState) -> AegonState:
    decision_log = state.get("decision_log") or []
    decision_log.append({
        "node": "rule_override_node",
        "violated_axiom": "axiom_3",
        "reason": "User attempted to override Aegon's rules or constraints.",
        "original_input": state.get("raw_input", ""),
    })
    return {
        **state,
        "worker_response": RULE_OVERRIDE_RESPONSE,
        "governance_result": "fail",
        "governance_reason": "Axiom 3 violation — rule override attempt detected at classifier.",
        "requires_approval": False,
        "decision_log": decision_log,
    }


# --- Routing functions ---

def route_after_classifier(state: AegonState) -> str:
    # Phase 5 — Step 1: a parked approval ALWAYS short-circuits intent,
    # so a confirmation turn ("yes"/"no") is never misrouted as a fresh request.
    if state.get("pending_approval"):
        return "approval_handler"

    intent = state.get("intent", "conversation")

    if intent == "clarification_needed":
        return "clarification_node"
    elif intent == "rule_override_attempt":
        return "rule_override_node"
    elif intent == "mode_switch":
        return "mode_switch_node"
    elif intent == "finding_feedback":
        return "feedback_node"
    elif intent == "memory_query":
        return "memory_agent"
    elif intent == "memory_delete":
        return "memory_agent"
    elif intent == "note_remember":
        return "memory_agent"
    elif intent == "summarize_request":
        return "summarizer_agent"
    elif intent == "plan_request":
        return "planner_agent"
    return "orchestrator_node"


def route_to_worker(state: AegonState) -> str:
    # Phase 5 — Step 3d: respect the orchestrator's receiver decision,
    # so a task that needs a tool reaches tool_node. Fail closed to conversation.
    a2a_payload = state.get("a2a_payload") or {}
    receiver = a2a_payload.get("receiver", "conversation_node")
    if receiver == "tool_node":
        return "tool_node"
    if receiver == "task_node":
        return "task_node"
    return "conversation_node"

# Phase 5 — Step 1: route after approval_handler gives its verdict.
#   approved -> tool_node (Step 3). Until then -> marked placeholder.
#   rejected / unclear -> synthesizer (worker_response already set).
def route_after_approval(state: AegonState) -> str:
    # Phase 5 — Step 4b: an approved action now runs in tool_node.
    if state.get("approval_verdict") == "approved":
        return "tool_node"
    return "response_synthesizer"

# --- Build the graph ---

def build_graph(checkpointer=None) -> StateGraph:
    graph = StateGraph(AegonState)

    # Register all nodes
    graph.add_node("intent_classifier", intent_classifier)
    graph.add_node("orchestrator_node", orchestrator_node)
    graph.add_node("conversation_node", conversation_node)
    graph.add_node("task_node", task_node)
    graph.add_node("governance_node", governance_node)
    graph.add_node("response_synthesizer", response_synthesizer)
    graph.add_node("clarification_node", clarification_node)
    graph.add_node("rule_override_node", rule_override_node)
    graph.add_node("mode_switch_node", mode_switch_node)
    graph.add_node("memory_agent", memory_agent)
    graph.add_node("summarizer_agent", summarizer_agent)
    graph.add_node("planner_agent", planner_agent)
    graph.add_node("approval_handler", approval_handler)   # Phase 5 — Step 1
    graph.add_node("tool_node", tool_node)                 # Phase 5 — Step 3d
    graph.add_node("feedback_node", feedback_node)         # A1.4


    # Entry point
    graph.set_entry_point("intent_classifier")

    # Conditional edge after classifier
    graph.add_conditional_edges(
        "intent_classifier",
        route_after_classifier,
        {
            "approval_handler": "approval_handler",          # Phase 5 — Step 1
            "clarification_node": "clarification_node",
            "rule_override_node": "rule_override_node",
            "mode_switch_node": "mode_switch_node",
            "memory_agent": "memory_agent",
            "summarizer_agent": "summarizer_agent",
            "planner_agent": "planner_agent",
            "feedback_node": "feedback_node",
            "orchestrator_node": "orchestrator_node",
        }
    )

    # Phase 5 — Step 1: conditional edge after approval_handler.
    graph.add_conditional_edges(
        "approval_handler",
        route_after_approval,
        {
            "tool_node": "tool_node",
            "response_synthesizer": "response_synthesizer",
        }
    )

    # Clarification goes straight to synthesizer
    graph.add_edge("clarification_node", "response_synthesizer")

    # Rule override goes straight to synthesizer
    graph.add_edge("rule_override_node", "response_synthesizer")

    # Mode switch goes straight to synthesizer — no governance needed
    graph.add_edge("mode_switch_node", "response_synthesizer")

    # Feedback goes straight to synthesizer — no governance needed
    graph.add_edge("feedback_node", "response_synthesizer")

    # All agents go to governance
    graph.add_edge("memory_agent", "governance_node")
    graph.add_edge("summarizer_agent", "governance_node")
    graph.add_edge("planner_agent", "governance_node")

    # Conditional edge after orchestrator
    graph.add_conditional_edges(
        "orchestrator_node",
        route_to_worker,
        {
            "conversation_node": "conversation_node",
            "task_node": "task_node",
            "tool_node": "tool_node",                       # Phase 5 — Step 3d
        }
    )

    # Both workers feed into governance
    graph.add_edge("conversation_node", "governance_node")
    graph.add_edge("task_node", "governance_node")
    graph.add_edge("tool_node", "governance_node")          # Phase 5 — Step 3d

    # Governance feeds into synthesizer
    graph.add_edge("governance_node", "response_synthesizer")

    # Synthesizer is the final node
    graph.add_edge("response_synthesizer", END)

    return graph.compile(checkpointer=checkpointer) if checkpointer else graph.compile()


# --- Compiled graph instance ---
aegon_graph = build_graph()