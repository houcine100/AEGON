# core/memory/context_injector.py
# Formats Tier 3 memory facts as Groq system prompt addition.
# Uses llm_client.py for behavioral delta detection — no own Groq instance.

from core.memory.memory_store import get_all_active_facts, search_facts
from core.orchestration.llm_client import call_llm

# Relevance gating: facts are injected per turn only when they bear on what Sir
# just said — not the whole history. A greeting pulls nothing. The local embedder
# scores conservatively (clearly-related ~0.44-0.63, unrelated ~0.03), so the
# threshold sits in that gap: low enough to catch real matches, high above noise.
RELEVANCE_TOP_K = 8
RELEVANCE_THRESHOLD = 0.35


def _retrieve_relevant(query: str) -> list:
    """Facts semantically relevant to the current input, above the noise floor.
    Empty for a greeting or anything with no real match."""
    if not query or not query.strip():
        return []
    try:
        results = search_facts(query, top_k=RELEVANCE_TOP_K)
    except Exception:
        return []
    # Vault-sourced facts are documents, not things to surface about Sir — never
    # inject them into a turn's context (Sir's rule). Filter by relevance and source.
    return [
        r for r in results
        if r.get("similarity", 0) >= RELEVANCE_THRESHOLD and r.get("source") != "vault"
    ]

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

FORM_LABELS = {
    "user_profile": "About Sir",
    "decision": "Past decisions",
    "project": "Active projects",
    "habit": "Known habits",
    "error": "Mistakes to avoid",
    "inference": "Inferred patterns",
}

NEGATIVE_WEIGHTS = {
    "stressed", "anxious", "frustrated", "angry", "sad", "worried",
    "exhausted", "overwhelmed", "scared", "nervous", "terrible", "awful"
}

POSITIVE_WORDS = {
    "better", "good", "great", "fine", "resolved", "done", "finished",
    "fixed", "happy", "relieved", "calm", "okay", "sorted", "managed"
}

BEHAVIORAL_DELTA_PROMPT = """You detect positive behavioral shifts.
Given previously stressed facts and recent conversation,
determine if Sir seems better now regarding any of those stressors.
If yes, respond with ONE short natural acknowledgment Aegon would say.
Keep it under 15 words. Start with 'Sir,'.
If no shift detected, respond with exactly: none"""


# ─────────────────────────────────────────
# MEMORY CONTEXT
# ─────────────────────────────────────────

def build_memory_context(query: str = "") -> str:
    """Format the facts RELEVANT to the current input as a Groq system prompt
    addition. Relevance-gated, not a dump: a greeting pulls nothing, so Aegon
    never carries Sir's whole history into a turn that does not need it."""
    facts = _retrieve_relevant(query)
    if not facts:
        return ""

    grouped = {}
    for fact in facts:
        form = fact["form"]
        if form not in grouped:
            grouped[form] = []
        grouped[form].append(fact["fact"])

    lines = ["--- Memory context ---"]
    for form, label in FORM_LABELS.items():
        if form in grouped:
            lines.append(f"\n{label}:")
            for f in grouped[form]:
                lines.append(f"  - {f}")
    lines.append("--- End of memory context ---")

    return "\n".join(lines)


# ─────────────────────────────────────────
# SESSION CONTEXT (A3.1)
# ─────────────────────────────────────────

def build_session_context(query: str = "") -> str:
    """Build a paragraph narrative of Sir's current state — but only the parts
    RELEVANT to the current input. No LLM call. Relevance-gated like
    build_memory_context: a greeting yields no narrative. Current screen activity
    is present-moment awareness (not history), so it is surfaced regardless."""
    facts = _retrieve_relevant(query)

    projects = [f for f in facts if f["form"] == "project"][:3]
    decisions = [f for f in facts if f["form"] == "decision"][:2]
    emotional = [f for f in facts if f.get("emotional_weight") in NEGATIVE_WEIGHTS][:2]
    inferences = [f for f in facts if f["form"] == "inference"][:2]

    parts = []
    if projects:
        parts.append("Active projects: " + "; ".join(f["fact"] for f in projects) + ".")
    if decisions:
        parts.append("Open decisions: " + "; ".join(f["fact"] for f in decisions) + ".")
    if emotional:
        parts.append("Recent stressors: " + "; ".join(f["fact"] for f in emotional) + ".")
    if inferences:
        parts.append("Patterns inferred: " + "; ".join(f["fact"] for f in inferences) + ".")

    if not parts:
        return ""

    return "--- Session context ---\n" + " ".join(parts) + "\n--- End session context ---"


# ─────────────────────────────────────────
# BEHAVIORAL DELTA
# ─────────────────────────────────────────

def get_stressed_facts() -> list:
    """Return all active facts with negative emotional weight."""
    facts = get_all_active_facts()
    return [
        f for f in facts
        if f.get("emotional_weight", "neutral") in NEGATIVE_WEIGHTS
    ]


def check_behavioral_delta(recent_text: str, stressed_facts: list) -> str:
    """
    Check if recent conversation shows positive shift from previously stressed states.
    Returns acknowledgment text if delta detected, empty string otherwise.
    Uses llm_client.py — no own Groq instance.
    """
    if not stressed_facts or not recent_text.strip():
        return ""

    text_lower = recent_text.lower()
    if not any(word in text_lower for word in POSITIVE_WORDS):
        return ""

    stressed_text = "\n".join([f"- {f['fact']}" for f in stressed_facts])

    result = call_llm(
        system_prompt=BEHAVIORAL_DELTA_PROMPT,
        user_message=(
            f"Previously stressed about:\n{stressed_text}\n\n"
            f"Recent conversation:\n{recent_text}"
        ),
        temperature=0.3,
    )

    if result.lower().strip() == "none":
        return ""
    return result