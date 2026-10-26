import threading
from contextlib import nullcontext
from types import SimpleNamespace

import asyncio

from tier1.knowledge import Knowledge
from tier1.chat import Chat


class PostgresSchemaProbe:
    backend = "postgres"

    def __init__(self):
        self.lock = threading.RLock()
        self.statements = []
        self.db = SimpleNamespace(executescript=lambda _: (_ for _ in ()).throw(AssertionError("SQLite schema used")))

    def x(self, sql, args=()):
        self.statements.append((sql, args))


class PostgresOperationProbe(PostgresSchemaProbe):
    """Records PostgreSQL-specific operations without requiring a live server."""

    def transaction(self):
        return nullcontext()

    def q(self, sql, args=()):
        self.statements.append((sql, args))
        if "SELECT id, sha FROM kb_sources" in sql:
            return []
        if "RETURNING id" in sql:
            return [{"id": 41}]
        if "to_tsvector" in sql:
            return [{"name": "note", "ord": 0, "text": "Grid balancing facts", "score": 0.25}]
        if "COUNT(*) n FROM chat_msgs" in sql:
            return [{"n": 0}]
        return []


def test_postgres_knowledge_initialization_avoids_sqlite_fts_schema():
    store = PostgresSchemaProbe()
    Knowledge(store, SimpleNamespace())
    assert any("kb_sources" in sql for sql, _ in store.statements)


def test_postgres_chat_initialization_avoids_sqlite_schema():
    store = PostgresSchemaProbe()
    Chat(store, None, None)
    assert any("chat_msgs" in sql for sql, _ in store.statements)


def test_postgres_knowledge_uses_native_upsert_and_full_text_search():
    store = PostgresOperationProbe()
    knowledge = Knowledge(store, SimpleNamespace())
    assert knowledge.index_text("nb", "note", "Grid balancing facts.")["status"] == "added"
    hits = knowledge.search("nb", "grid balancing")
    sql = "\n".join(statement for statement, _ in store.statements)
    assert "RETURNING id" in sql
    assert "to_tsvector" in sql and "websearch_to_tsquery" in sql
    assert "strftime" not in sql and "MATCH" not in sql and hits[0]["score"] == 0.25


def test_postgres_chat_uses_conflict_safe_session_insert():
    class Modes:
        async def run(self, *args, **kwargs):
            return {"answer": "hello", "status": "ok"}

    store = PostgresOperationProbe()
    chat = Chat(store, None, Modes())
    asyncio.run(chat.send("session", "hello"))
    sql = "\n".join(statement for statement, _ in store.statements)
    assert "ON CONFLICT (id) DO NOTHING" in sql
    assert "INSERT OR IGNORE" not in sql
