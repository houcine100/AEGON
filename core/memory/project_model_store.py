# core/memory/project_model_store.py
# CRUD for the project_models table.
# Stores Aegon's working model of Sir's active projects — not just that they
# exist, but their current state, next decision, and blockers.

import psycopg2
import psycopg2.extras
from core.memory.db_init import DB_CONFIG


def get_all_project_models() -> list[dict]:
    """Return all project models, most recently updated first."""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM project_models ORDER BY last_updated DESC"
            )
            return [dict(r) for r in cur.fetchall()]


def get_project_model(name: str) -> dict | None:
    """Return the model for a single project by name, or None."""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM project_models WHERE name = %s", (name,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_project_model(
    name: str,
    domain: str | None = None,
    current_state: str | None = None,
    next_decision: str | None = None,
    blockers: str | None = None,
    confidence: float = 0.5,
) -> None:
    """
    Insert or update a project model. Existing fields are preserved when the
    new value is None — partial updates are safe.
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO project_models
                    (name, domain, current_state, next_decision, blockers, confidence, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (name) DO UPDATE SET
                    domain        = COALESCE(EXCLUDED.domain,        project_models.domain),
                    current_state = COALESCE(EXCLUDED.current_state, project_models.current_state),
                    next_decision = COALESCE(EXCLUDED.next_decision, project_models.next_decision),
                    blockers      = COALESCE(EXCLUDED.blockers,       project_models.blockers),
                    confidence    = EXCLUDED.confidence,
                    last_updated  = NOW()
                """,
                (name, domain, current_state, next_decision, blockers, confidence),
            )
        conn.commit()


def clear_blocker(name: str) -> None:
    """Remove the blocker field for a project (call when Sir resolves one)."""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE project_models SET blockers = NULL, last_updated = NOW() WHERE name = %s",
                (name,),
            )
        conn.commit()
