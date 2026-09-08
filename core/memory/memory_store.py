#core/memory/memory_store.py
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

AUDIT_LOG = Path(__file__).resolve().parent / "memory_audit.jsonl"

def _log_audit(action: str, fact_id: int, detail: str = ""):
    """Write an audit record for every memory write, update, or delete."""
    record = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "fact_id": fact_id,
        "detail": detail
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "aegon_memory",
    "user": "aegon",
    "password": os.environ.get("AEGON_DB_PASSWORD")
}

EMBEDDING_MODEL = str(Path(__file__).resolve().parent / "embedding_model")
TOP_K = 10

_model = None


def get_embedding_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    register_vector(conn)
    return conn

def fact_exists(fact: str, similarity_threshold: float = 0.90) -> bool:
    """Returns True if a semantically similar fact already exists in active records."""
    model = get_embedding_model()
    embedding = model.encode(fact).tolist()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                        SELECT 1 - (embedding <=> %s::vector) AS similarity
                        FROM memory_records
                        WHERE status = 'active'
                        ORDER BY embedding <=> %s::vector
                            LIMIT 1
                        """, (embedding, embedding))
            row = cur.fetchone()
            if row and row[0] >= similarity_threshold:
                return True
            return False
    finally:
        conn.close()

def find_contradiction(fact: str, similarity_threshold: float = 0.75) -> Optional[dict]:
    """
    Check if a new fact contradicts an existing active fact.
    Returns the conflicting record if found, None otherwise.
    Contradiction threshold is lower than duplicate threshold —
    we want to catch related but conflicting facts.
    """
    model = get_embedding_model()
    embedding = model.encode(fact).tolist()

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT id, fact, form, emotional_weight, stability, status,
                               1 - (embedding <=> %s::vector) AS similarity
                        FROM memory_records
                        WHERE status = 'active'
                        ORDER BY embedding <=> %s::vector
                            LIMIT 1
                        """, (embedding, embedding))
            row = cur.fetchone()
            if not row:
                return None
            # Similar enough to be related but below duplicate threshold
            if 0.75 <= row["similarity"] < 0.90:
                return dict(row)
            return None
    finally:
        conn.close()

# ─────────────────────────────────────────
# WRITE
# ─────────────────────────────────────────

def store_fact(
        fact: str,
        form: str,
        emotional_weight: str = "neutral",
        stability: str = "permanent",
        source: str = "inferred",
        resolution_notes: Optional[str] = None
) -> int:
    """Store a fact in memory. Returns the record id or -1 if duplicate."""
    if fact_exists(fact):
        return -1

    model = get_embedding_model()
    embedding = model.encode(fact).tolist()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                        INSERT INTO memory_records
                        (fact, form, emotional_weight, stability, source, resolution_notes, embedding)
                        VALUES
                            (%s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                        """, (fact, form, emotional_weight, stability, source, resolution_notes, embedding))
            record_id = cur.fetchone()[0]
        conn.commit()
        _log_audit("write", record_id, f"[{form}] {fact}")
        return record_id
    finally:
        conn.close()


def update_fact_status(record_id: int, status: str, resolution_notes: Optional[str] = None):
    """Update status of an existing fact — active, resolved, superseded."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                        UPDATE memory_records
                        SET status = %s,
                            resolution_notes = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """, (status, resolution_notes, record_id))
        conn.commit()
        _log_audit("update", record_id, f"status={status} notes={resolution_notes}")
    finally:
        conn.close()


# ─────────────────────────────────────────
# READ
# ─────────────────────────────────────────

def search_facts(query: str, top_k: int = TOP_K, status: str = "active") -> list:
    """Semantic search — returns most relevant facts for a query."""
    model = get_embedding_model()
    embedding = model.encode(query).tolist()

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT id, fact, form, emotional_weight, stability, status, source,
                               created_at, resolution_notes,
                               1 - (embedding <=> %s::vector) AS similarity
                        FROM memory_records
                        WHERE status = %s
                        ORDER BY embedding <=> %s::vector
                            LIMIT %s
                        """, (embedding, status, embedding, top_k))
            return cur.fetchall()
    finally:
        conn.close()


def get_all_active_facts() -> list:
    """Return all active facts — used for context injection."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT id, fact, form, emotional_weight, stability, source, created_at
                        FROM memory_records
                        WHERE status = 'active'
                        ORDER BY form, created_at
                        """)
            return cur.fetchall()
    finally:
        conn.close()


def get_memory_health_stats() -> dict:
    """Return memory stats for the weekly review."""
    cutoff_week = datetime.utcnow() - timedelta(days=7)
    cutoff_stale = datetime.utcnow() - timedelta(days=30)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS n FROM memory_records WHERE status='active'")
            total = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM memory_records WHERE status='active' AND created_at >= %s", (cutoff_week,))
            new_this_week = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM memory_records WHERE status='active' AND created_at < %s", (cutoff_stale,))
            stale = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM memory_records WHERE status='active' AND form='inference'")
            inferences = cur.fetchone()["n"]
        return {"total_active": total, "new_this_week": new_this_week, "stale_30_days": stale, "inferences": inferences}
    finally:
        conn.close()


def get_recent_facts(minutes: int = 60) -> list:
    """Return active facts stored in the last N minutes."""
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, fact, form, created_at
                FROM memory_records
                WHERE status = 'active' AND created_at >= %s
                ORDER BY created_at DESC
            """, (cutoff,))
            return cur.fetchall()
    finally:
        conn.close()


def get_facts_by_form(form: str) -> list:
    """Return all active facts for a specific memory form."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT id, fact, form, emotional_weight, stability, source, created_at
                        FROM memory_records
                        WHERE status = 'active' AND form = %s
                        ORDER BY created_at
                        """, (form,))
            return cur.fetchall()
    finally:
        conn.close()