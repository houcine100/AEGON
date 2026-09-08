# tests/test_memory_recall.py
# Bug B (2026-06-20): "what do you know about me" must do a GENERAL recall, not a
# narrow user_profile-form lookup that dead-ends when facts live under other forms.

from unittest.mock import patch
import agents.memory_agent.memory_agent as ma


# ── _detect_form: general phrases are NOT a form ───────────────────────────────

def test_about_me_is_not_a_form():
    assert ma._detect_form("what do you know about me") is None


def test_who_am_i_is_not_a_form():
    assert ma._detect_form("who am i") is None


def test_specific_form_still_detected():
    # genuine form-specific phrases must still narrow
    assert ma._detect_form("what are my preferences") == "user_profile"
    assert ma._detect_form("what are my habits") == "habit"


# ── _handle_read: empty form falls back to general recall ──────────────────────

def test_empty_form_falls_back_to_general_recall():
    # form detected ("habit") but no habit facts stored -> fall through to semantic search
    with patch.object(ma, "get_facts_by_form", return_value=[]), \
         patch.object(ma, "search_facts", return_value=[{"fact": "Sir is building Aegon.", "form": "project", "source": "explicit", "similarity": 0.9}]), \
         patch.object(ma, "call_llm", return_value="Here is what I know, Sir.") as mock_llm:
        result = ma._handle_read("what are my habits", memory_context="")
    # must NOT dead-end with "nothing stored under habit"
    assert "nothing stored under" not in result.lower()
    mock_llm.assert_called_once()
    assert "building Aegon" in mock_llm.call_args.kwargs["system_prompt"]


def test_specific_query_can_retrieve_reference_material():
    # A specific topic question (not a personal summary) may pull back vault/reference
    # content Sir saved "for future use" — that is the point of saving it.
    with patch.object(ma, "get_facts_by_form", return_value=[]), \
         patch.object(ma, "search_facts", return_value=[{"fact": "Content of Obsidian note 'Budget': the numbers", "form": "project", "source": "vault", "similarity": 0.9}]), \
         patch.object(ma, "call_llm", return_value="Here it is, Sir.") as mock_llm:
        ma._handle_read("what did I save about the budget", memory_context="")
    assert "Budget" in mock_llm.call_args.kwargs["system_prompt"]


def test_general_query_uses_broad_retrieval_not_form():
    # general recall self-retrieves broadly (decoupled from the relevance-gated
    # injected context) — form lookup is never used, get_all_active_facts is.
    with patch.object(ma, "get_facts_by_form") as mock_form, \
         patch.object(ma, "get_all_active_facts", return_value=[{"fact": "Sir drinks black coffee.", "form": "habit", "source": "explicit"}]), \
         patch.object(ma, "call_llm", return_value="Recalled, Sir.") as mock_llm:
        ma._handle_read("what do you know about me", memory_context="")
    mock_form.assert_not_called()
    assert "black coffee" in mock_llm.call_args.kwargs["system_prompt"]


def test_vault_facts_excluded_from_personal_recall():
    # Sir's rule: vault-sourced facts (notes, vault stubs) never appear in personal recall.
    facts = [
        {"fact": "Sir drinks black coffee.", "form": "habit", "source": "explicit"},
        {"fact": "Content of Obsidian note 'Welcome': # Aegon Vault", "form": "project", "source": "vault"},
    ]
    with patch.object(ma, "get_facts_by_form"), \
         patch.object(ma, "get_all_active_facts", return_value=facts), \
         patch.object(ma, "call_llm", return_value="Recalled, Sir.") as mock_llm:
        ma._handle_read("what do you know about me", memory_context="")
    prompt = mock_llm.call_args.kwargs["system_prompt"]
    assert "black coffee" in prompt
    # the vault fact's content must not be in the injected facts
    # (note: the word "Obsidian" appears in the prompt template's rule 8 — that is the
    # instruction not to mention the vault, not the leaked fact, so we check the content)
    assert "Aegon Vault" not in prompt
    assert "Content of Obsidian note" not in prompt
