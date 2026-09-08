#core/memory/db_init.py
import os
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "aegon_memory",
    "user": "aegon",
    "password": os.environ.get("AEGON_DB_PASSWORD")
}

SCHEMA = """
         CREATE EXTENSION IF NOT EXISTS vector;

         CREATE TABLE IF NOT EXISTS memory_records (
                                                       id SERIAL PRIMARY KEY,
                                                       fact TEXT NOT NULL,
                                                       form TEXT NOT NULL,
                                                       emotional_weight TEXT NOT NULL DEFAULT 'neutral',
                                                       stability TEXT NOT NULL DEFAULT 'permanent',
                                                       status TEXT NOT NULL DEFAULT 'active',
                                                       source TEXT NOT NULL DEFAULT 'inferred',
                                                       created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
             updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
             resolution_notes TEXT,
             embedding vector(384)
             );

         CREATE INDEX IF NOT EXISTS memory_embedding_idx
             ON memory_records USING ivfflat (embedding vector_cosine_ops)
             WITH (lists = 100);

         CREATE INDEX IF NOT EXISTS memory_status_idx
             ON memory_records (status);

         CREATE INDEX IF NOT EXISTS memory_form_idx
             ON memory_records (form);

         CREATE TABLE IF NOT EXISTS project_models (
             id            SERIAL PRIMARY KEY,
             name          TEXT UNIQUE NOT NULL,
             domain        TEXT,
             current_state TEXT,
             next_decision TEXT,
             blockers      TEXT,
             confidence    REAL NOT NULL DEFAULT 0.5,
             last_updated  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
             created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
         );
         """

def init_db():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
        conn.commit()
        print("Database initialized successfully.")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()