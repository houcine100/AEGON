# tests/test_f5_live_extraction.py
# F.5 live gate — requires Docker PostgreSQL running.
# Sends scripted turns through the orchestrator, reads the DB before and after
# each block, and asserts fact counts match only Sir-statement turns.
#
# Run: .venv\Scripts\python.exe -m pytest tests/test_f5_live_extraction.py -v -s
#
# IMPORTANT: This test mutates the live memory DB. It does NOT clean up inserted
# facts — they may be deduplicated naturally but will remain in memory_records.
# Run against a test DB or accept that a few innocuous facts will be stored.

import sys, os, time, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector

# Must import orchestrator AFTER sys.path insert — it connects Postgres at import.
from apps.orchestrator.aegon_orchestrator import on_user_turn_complete, drain_extraction_threads


DB_CONFIG = {
    "host": "localhost", "port": 5432, "dbname": "aegon_memory",
    "user": "aegon", "password": os.environ.get("AEGON_DB_PASSWORD", "aegon_secure_2026"),
}


def count_facts() -> int:
    conn = psycopg2.connect(**DB_CONFIG)
    register_vector(conn)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memory_records WHERE status = 'active'")
            return cur.fetchone()[0]
    finally:
        conn.close()


def get_recent_facts(limit: int = 20) -> list[dict]:
    conn = psycopg2.connect(**DB_CONFIG)
    register_vector(conn)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, fact, form FROM memory_records WHERE status = 'active' "
                "ORDER BY id DESC LIMIT %s", (limit,)
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def send(text: str) -> str:
    response = on_user_turn_complete(text)
    time.sleep(1)
    return response


def settle(timeout: int = 180, stable_secs: int = 10) -> int:
    """Wait until the fact count stops changing, then return it.
    Extraction runs on background threads and can be slowed massively by the
    Groq rate-limit -> Ollama fallback, so a fixed sleep is not reliable."""
    last = count_facts()
    stable_since = time.time()
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        current = count_facts()
        if current != last:
            last = current
            stable_since = time.time()
        elif time.time() - stable_since >= stable_secs:
            break
    return last


# ── External content phrases that must NOT appear in Tier-3 facts ────────────
BANNED_CONTENT_MARKERS = [
    "http", "www.", "search result", "from github", "spotify",
    "subject:", "from:", "re:", "weather",
]


class TestF5LiveExtraction:

    def test_f16_gate_live(self):
        baseline = count_facts()
        print(f"\n[F.5] Baseline fact count: {baseline}")

        # Block 1 — 5 tool turns (should produce ZERO new facts)
        tool_turns = [
            "what's the weather today",
            "search the web for latest AI news",
            "check my email",
            "what time is it",
            "play some music",
        ]
        for turn in tool_turns:
            send(turn)
        drain_extraction_threads()
        after_tools = count_facts()
        tool_delta = after_tools - baseline
        print(f"[F.5] After 5 tool turns: delta={tool_delta} (expected 0)")
        assert tool_delta == 0, f"Tool turns produced {tool_delta} facts — expected 0"

        # Block 2 — 5 memory_query turns (should produce ZERO new facts)
        memory_turns = [
            "what do you know about me",
            "what are my habits",
            "do you remember anything about my work",
            "what are my active projects",
            "summarize what you know about me",
        ]
        for turn in memory_turns:
            send(turn)
        drain_extraction_threads()
        after_memory = count_facts()
        memory_delta = after_memory - after_tools
        print(f"[F.5] After 5 memory_query turns: delta={memory_delta} (expected 0)")
        assert memory_delta == 0, f"memory_query turns produced {memory_delta} facts — expected 0"

        # Block 3 — 5 Sir-statement turns (should produce facts).
        # A per-run nonce keeps each statement novel so the 0.90 dedup threshold
        # cannot mask extraction with facts left over from earlier test runs.
        nonce = uuid.uuid4().hex[:8]
        statement_turns = [
            f"I usually start work at 9am and finish around midnight, on schedule {nonce}",
            f"I prefer working in silence — no music when I am coding, note {nonce}",
            f"I am building Aegon as my personal AI assistant, build {nonce}",
            f"I drink coffee in the morning and tea in the evening, routine {nonce}",
            f"my main goal this year is to finish Aegon and ship it, goal {nonce}",
        ]
        for turn in statement_turns:
            send(turn)
        drain_extraction_threads()
        after_statements = count_facts()
        statement_delta = after_statements - after_memory
        print(f"[F.5] After 5 Sir-statement turns: delta={statement_delta} (expected >0)")
        assert statement_delta > 0, "Sir-statement turns produced zero facts — extraction broken"

        # Block 4 — 5 more tool turns (should produce ZERO additional facts)
        for turn in tool_turns:
            send(turn)
        drain_extraction_threads()
        after_final_tools = count_facts()
        final_tool_delta = after_final_tools - after_statements
        print(f"[F.5] After 5 final tool turns: delta={final_tool_delta} (expected 0)")
        assert final_tool_delta == 0, f"Final tool turns produced {final_tool_delta} facts — expected 0"

        # Check: no external content in recently stored facts
        recent = get_recent_facts(30)
        for record in recent:
            fact_lower = record["fact"].lower()
            for marker in BANNED_CONTENT_MARKERS:
                assert marker not in fact_lower, (
                    f"External content marker '{marker}' found in fact: {record['fact']}"
                )

        print(f"[F.5] PASS — tool/memory turns: 0 facts; "
              f"Sir-statement turns: {statement_delta} facts; "
              f"no external content in Tier-3.")
