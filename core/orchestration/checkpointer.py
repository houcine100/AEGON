# core/orchestration/checkpointer.py
# Persistent state storage using the existing PostgreSQL instance.
# Never uses InMemorySaver — a restart must never wipe state.
# Maps thread_id to session_id for conversation resumption.

import os
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import dict_row

DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = os.environ.get("POSTGRES_PORT", "5432")
DB_NAME = os.environ.get("POSTGRES_DB", "aegon_memory")
DB_USER = os.environ.get("POSTGRES_USER", "aegon")
DB_PASSWORD = os.environ.get("AEGON_DB_PASSWORD", "aegon_secure_2026")

CONNECTION_STRING = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


def get_checkpointer() -> PostgresSaver:
    """
    Returns a PostgresSaver instance connected to the aegon_memory database.
    Called once at startup by aegon_orchestrator.py.
    """
    try:
        conn = Connection.connect(
            CONNECTION_STRING,
            autocommit=True,
            row_factory=dict_row,
            connect_timeout=5,
        )
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
        print("[checkpointer] PostgreSQL checkpointer ready.")
        return checkpointer
    except Exception as e:
        print(f"[checkpointer] Failed to connect to PostgreSQL: {e}")
        print("[checkpointer] State will not persist across restarts.")
        return None