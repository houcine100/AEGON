# tests/test_vault_privacy.py
# Privacy gate (Sir's rule, 2026-06-20): the default vault sync stores a note's
# IDENTITY only — title + optional frontmatter 'purpose:'. The note BODY must
# NEVER appear in a stored fact.

from pathlib import Path

from core.memory.vault_sync import _note_to_fact, _extract_purpose


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_body_never_stored_without_purpose(tmp_path):
    note = _write(
        tmp_path,
        "Banking.md",
        "# Banking\nMy account number is 123456789 and the PIN is 4242.\n",
    )
    fact = _note_to_fact(note)
    assert "123456789" not in fact
    assert "4242" not in fact
    assert fact == "Obsidian note 'Banking' exists in the vault."


def test_purpose_stored_body_excluded(tmp_path):
    note = _write(
        tmp_path,
        "Reading.md",
        "---\npurpose: tracks my reading list\n---\n# Reading\n"
        "Secret: I am quitting my job in March.\n",
    )
    fact = _note_to_fact(note)
    assert "tracks my reading list" in fact
    assert "Obsidian note 'Reading'" in fact
    # body content must not leak
    assert "quitting my job" not in fact
    assert "Secret" not in fact


def test_extract_purpose_stops_at_frontmatter_close():
    # a 'purpose:' line in the BODY (after the closing ---) must be ignored
    raw = "---\ntitle: X\n---\npurpose: this is body text, not metadata\n"
    assert _extract_purpose(raw) == ""


def test_no_frontmatter_returns_empty_purpose():
    assert _extract_purpose("# Just a heading\nsome body\n") == ""
