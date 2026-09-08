# tests/phase5/test_tool_routing.py
# Phase 5 — Step 3d/3e: full end-to-end. Type a search request, watch it flow
# classifier -> orchestrator -> tool_node -> governance -> synthesizer.
# Uses live Groq + live web search. Run: python -m tests.phase5.test_tool_routing

from core.orchestration.graph import build_graph

graph = build_graph()

initial_state = {
    "session_id": "test", "thread_id": "t1",
    "raw_input": "search the web for the weather in Tokyo",
    "active_mode": "standard", "conversation_history": "",
    "intent": None, "confidence": None, "requested_mode": None,
    "a2a_payload": None, "worker_response": None,
    "governance_result": None, "governance_reason": None, "requires_approval": None,
    "final_response": None, "decision_log": [], "memory_context": None,
    "pending_approval": None, "tool_result": None, "approval_verdict": None,
}

result = graph.invoke(initial_state)

print("PATH:", [d.get("node") for d in result.get("decision_log", [])])
print("-" * 40)
print("RESPONSE:", result.get("final_response"))
print("GOV REASON:", result.get("governance_reason"))