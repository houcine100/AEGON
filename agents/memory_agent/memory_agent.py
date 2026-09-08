# agents/memory_agent/memory_agent.py
# Memory Agent — manages all reads and writes to the six memory forms.
# Single responsibility: everything Aegon knows about Sir.
# Tested in isolation before wiring into graph.py.

import json
from core.orchestration.state import AegonState
from core.orchestration.llm_client import call_llm
from schemas.intent_schema import Intent
from core.memory.memory_store import (
    store_fact,
    search_facts,
    get_facts_by_form,
    get_all_active_facts,
    find_contradiction,
)
from agents.memory_agent.memory_agent_prompt import (
    MEMORY_AGENT_PROMPT,
    MEMORY_WRITE_PROMPT,
)
from tools.obsidian_read.obsidian_read_tool import ObsidianReadConnector

# Part 2 (2026-06-20): the ONLY sanctioned path for an Obsidian note's body to
# enter memory — Sir must explicitly ask ("remember the content of note X").
# The vault sync stores identity only; this stores content on deliberate request.
_NOTE_CONTENT_MAX_CHARS = 2000  # cap a single note fact so it embeds coherently

_NOTE_TITLE_PROMPT = """Extract ONLY the Obsidian note title from Sir's request to remember a note's content.
Return just the title text — no quotes, no explanation, nothing else.
Examples:
- "remember the content of note Groceries" -> Groceries
- "save the content of my Project Plan note" -> Project Plan
- "memorize what's in the note called Ideas" -> Ideas"""


# --- Keywords that signal a write request ---
WRITE_KEYWORDS = [
    "remember that",
    "remember this",
    "don't forget",
    "make a note",
    "note that",
    "save that",
    "keep in mind",
]

# --- Keywords that signal a delete request ---
DELETE_KEYWORDS = [
    "forget that",
    "forget this",
    "remove that",
    "delete that",
    "don't remember",
    "erase that",
]

# Write keywords take priority over delete keywords.
# "dont forget" and "don't forget" are write requests — not delete requests.
WRITE_PRIORITY_KEYWORDS = [
    "dont forget",
    "don't forget",
    "do not forget",
]

# Delete tuning. A delete request resolves EVERY stored fact whose semantic
# similarity to the request clears the threshold — so "delete everything about X"
# removes all of X, not just the single closest note.
# The local embedding model scores conservatively: clearly-related facts land
# around 0.45-0.63 against a full delete sentence, while unrelated facts sit near
# 0.03. The threshold lives in that wide gap — low enough to catch every genuine
# match, far above the noise floor. Delete is always confirmed by Sir, so erring
# toward inclusion is safe (he sees the list and can decline).
DELETE_SIMILARITY_THRESHOLD = 0.40
DELETE_MAX_MATCHES = 10

# --- Form keywords for targeted queries ---
FORM_KEYWORDS = {
    "habit": ["habit", "habits", "routine", "routines", "pattern", "patterns"],
    "project": ["project", "projects", "goal", "goals", "plan", "plans", "building", "working on"],
    "decision": ["decision", "decisions", "choice", "choices", "decided"],
    "user_profile": ["profile", "preferences", "personality"],
    "error": ["mistake", "mistakes", "error", "errors", "wrong", "avoid"],
}


def _detect_write(text: str) -> bool:
    """Returns True if the input is a write request."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in WRITE_KEYWORDS)


def _detect_delete(text: str) -> bool:
    """
    Returns True if the input is a delete request.
    Write priority keywords override delete detection.
    """
    text_lower = text.lower()
    # Write priority keywords take precedence — never treat as delete
    if any(kw in text_lower for kw in WRITE_PRIORITY_KEYWORDS):
        return False
    return any(kw in text_lower for kw in DELETE_KEYWORDS)


# Phrases that ask for a broad summary of Sir-the-person. These exclude vault/reference
# material (note content Sir saved "for future use" is not a fact about him). A specific
# topic question is NOT a personal summary — it may legitimately pull that reference back.
_PERSONAL_SUMMARY_PHRASES = [
    "about me", "about myself", "who am i", "know about me", "remember about me",
]


def _is_personal_summary(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in _PERSONAL_SUMMARY_PHRASES)


def _detect_form(text: str):
    """Returns the specific memory form being asked about, or None."""
    text_lower = text.lower()
    for form, keywords in FORM_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return form
    return None


def _handle_write(payload: str, session_id: str) -> str:
    """
    Handles a write request — extracts the fact and stores it.
    Checks for contradictions before storing.
    Returns Aegon's confirmation response.
    """
    raw_response = call_llm(
        system_prompt=MEMORY_WRITE_PROMPT,
        user_message=payload,
        temperature=0.1,
    )

    try:
        parsed = json.loads(raw_response)
        fact = parsed.get("fact", "")
        form = parsed.get("form", "user_profile")
        emotional_weight = parsed.get("emotional_weight", "neutral")
        stability = parsed.get("stability", "permanent")
        source = parsed.get("source", "explicit")

        if not fact:
            return "I could not extract a clear fact to store, Sir. Could you rephrase?"

        # Reject meaningless facts — too short or no real content
        if len(fact.strip()) < 10:
            return "That is too vague to store, Sir. Could you be more specific?"

        # Reject facts that are just meta-statements about remembering
        meta_phrases = [
            "sir asked me to remember",
            "sir wants me to remember",
            "remember something",
            "asked to remember",
        ]
        if any(phrase in fact.lower() for phrase in meta_phrases):
            return "I did not catch what you wanted me to remember, Sir. Could you rephrase?"

        # Check for contradiction before storing
        contradiction = find_contradiction(fact)
        if contradiction:
            existing_fact = contradiction["fact"]
            similarity = contradiction["similarity"]

            # Store the new fact as active
            result = store_fact(
                fact=fact,
                form=form,
                emotional_weight=emotional_weight,
                stability=stability,
                source=source,
            )

            if result == -1:
                return "I already have that recorded, Sir."

            # Mark the old contradicting fact as superseded
            update_fact_status(
                record_id=contradiction["id"],
                status="superseded",
                resolution_notes=f"Superseded by new fact: {fact}",
            )

            return (
                f"Noted, Sir. I have updated my memory. "
                f"Previously I had: '{existing_fact}'. "
                f"Now replaced with: '{fact}'."
            )

        # No contradiction — store normally
        result = store_fact(
            fact=fact,
            form=form,
            emotional_weight=emotional_weight,
            stability=stability,
            source=source,
        )

        if result == -1:
            return "I already have that recorded, Sir."

        return f"Noted, Sir. I have stored: {fact}"

    except (json.JSONDecodeError, ValueError):
        return "I had trouble parsing that, Sir. Could you rephrase what you want me to remember?"



def _extract_note_title(payload: str) -> str:
    """Pull the Obsidian note title out of Sir's request. LLM, by meaning."""
    raw = call_llm(system_prompt=_NOTE_TITLE_PROMPT, user_message=payload, temperature=0.0)
    return (raw or "").strip().strip('"').strip("'")


def _handle_note_remember(payload: str) -> str:
    """Read a named Obsidian note and store its body as a Tier-3 fact.
    The only path that persists note CONTENT — Sir asked for it explicitly."""
    title = _extract_note_title(payload)
    if not title:
        return "Which note's content shall I remember, Sir?"

    result = ObsidianReadConnector().execute({"title": title})
    if result.get("status") != "success":
        return f"I could not find a note called '{title}' in your vault, Sir."

    body = (result.get("output") or "").strip()
    if not body:
        return f"The note '{title}' is empty, Sir — there is nothing to remember."

    body = body[:_NOTE_CONTENT_MAX_CHARS]
    fact = f"Content of Obsidian note '{title}': {body}"
    stored = store_fact(
        fact=fact,
        form="project",
        emotional_weight="neutral",
        stability="permanent",
        source="vault",   # vault-sourced — stored, but excluded from personal recall
    )
    if stored == -1:
        return f"I already have the content of '{title}' stored, Sir."
    return f"Noted, Sir. I have remembered the content of '{title}'."


def _handle_read(payload: str, memory_context: str, conversation_history: str = "") -> str:
    """
    Handles a read request — returns relevant memory facts.
    Uses targeted form lookup if a specific form is detected.
    Falls back to semantic search for general queries.
    Uses conversation history for follow-up context.
    """
    form = _detect_form(payload)

    # A detected form gives a targeted lookup — but only when it actually has facts.
    # If the form is empty, fall through to the general recall below rather than
    # dead-ending: facts the user means may be stored under a different form.
    facts = get_facts_by_form(form) if form else []

    if form and facts:
        fact_lines = "\n".join([f"- {f['fact']}" for f in facts])
        system_prompt = MEMORY_AGENT_PROMPT + f"\n\nRelevant memory:\n{fact_lines}"
    else:
        # Two different needs share this path:
        #  - Broad "what do you know about me" → facts about Sir-the-person only.
        #    Vault/reference material (note content saved for future use) is NOT
        #    about him, so it is excluded (Sir's rule).
        #  - A specific topic question → semantic search across everything, INCLUDING
        #    reference material, so saved note content can be pulled back when wanted.
        # Either way recall self-retrieves here, decoupled from the relevance-gated
        # injected context (a narrow injection would re-break general recall — Bug B).
        if _is_personal_summary(payload):
            facts_out = [f for f in get_all_active_facts() if f.get("source") != "vault"]
        else:
            # search_facts has no relevance floor of its own — it always returns up to
            # top_k rows even when nothing actually matches. Apply the same 0.35 cutoff
            # already used for ambient context injection (context_injector.py) so an
            # irrelevant "closest available" fact can't slip through and get answered
            # from conversation history instead (the Retest Note hallucination).
            facts_out = [f for f in search_facts(payload, top_k=8)
                         if f.get("similarity", 0) >= 0.35]
        if not facts_out:
            return "I have nothing stored in memory yet, Sir."
        fact_lines = "\n".join([f"- {f['fact']}" for f in facts_out])
        system_prompt = MEMORY_AGENT_PROMPT + f"\n\nRelevant memory:\n{fact_lines}"

    # Inject conversation history for follow-up context — EXCEPT for broad personal
    # summaries. Recent turns may quote vault/reference content (e.g. a note read
    # aloud two turns ago); feeding that history here would let the LLM fold it back
    # into "what do you know about me", bypassing the vault exclusion above.
    if conversation_history and not _is_personal_summary(payload):
        system_prompt += f"\n\nRecent conversation:\n{conversation_history}"

    response = call_llm(
        system_prompt=system_prompt,
        user_message=payload,
        temperature=0.3,
    )
    return response


def memory_agent(state: AegonState) -> AegonState:
    """
    Memory Agent node.
    Handles all memory-related requests — reads, writes, deletes.
    Routes internally based on request type.
    """
    a2a_payload = state.get("a2a_payload") or {}
    payload = a2a_payload.get("payload", state.get("raw_input", ""))
    memory_context = state.get("memory_context") or ""
    conversation_history = state.get("conversation_history") or ""
    session_id = state.get("session_id", "")
    decision_log = state.get("decision_log") or []
    intent = state.get("intent", "")

    # Note-content remember (Part 2): driven purely by the classifier intent.
    if intent == Intent.NOTE_REMEMBER:
        request_type = "note_remember"
        response = _handle_note_remember(payload)
        decision_log.append({
            "node": "memory_agent",
            "request_type": request_type,
            "payload_received": payload,
            "worker_response": response,
        })
        return {**state, "worker_response": response, "decision_log": decision_log}

    # Detect request type. Delete is driven by the classifier intent (by meaning),
    # with the keyword check kept only as a backward-compatible fallback.
    is_delete = intent == Intent.MEMORY_DELETE or _detect_delete(payload)

    if not is_delete and _detect_write(payload):
        request_type = "write"
        response = _handle_write(payload, session_id)

    elif is_delete:
        request_type = "delete"
        results = search_facts(payload, top_k=DELETE_MAX_MATCHES)
        matches = [r for r in results if r.get("similarity", 0) >= DELETE_SIMILARITY_THRESHOLD]

        if not matches:
            response = "I could not find anything matching that in memory, Sir."
        else:
            fact_ids = [m["id"] for m in matches]
            fact_texts = [m["fact"] for m in matches]

            if len(matches) == 1:
                prompt = f"Shall I remove this from memory: '{fact_texts[0]}'?"
            else:
                listed = "; ".join(f"'{t}'" for t in fact_texts)
                prompt = f"Shall I remove these {len(matches)} memories: {listed}?"

            decision_log.append({
                "node": "memory_agent",
                "request_type": "delete_pending",
                "payload_received": payload,
                "fact_id": fact_ids[0],
                "fact_text": fact_texts[0],
                "fact_ids": fact_ids,
            })
            return {
                **state,
                "worker_response": prompt,
                "requires_approval": True,
                "pending_approval": {
                    "action_type": "memory_delete",
                    "tool": "memory_agent",
                    "fact_id": fact_ids[0],
                    "fact_text": fact_texts[0],
                    "fact_ids": fact_ids,
                    "fact_texts": fact_texts,
                    "prompt_shown": prompt,
                },
                "decision_log": decision_log,
            }

    else:
        request_type = "read"
        response = _handle_read(payload, memory_context, conversation_history)

    # Log the decision
    decision_log.append({
        "node": "memory_agent",
        "request_type": request_type,
        "payload_received": payload,
        "worker_response": response,
    })

    return {
        **state,
        "worker_response": response,
        "decision_log": decision_log,
    }