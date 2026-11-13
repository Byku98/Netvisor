"""Migration c5d6e7f8a9b0 backfill: old-shaped rows -> one ai_chats per group."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, text
from sqlalchemy.exc import IntegrityError

MIGRATION_FILE = (
    Path(__file__).parent.parent
    / "alembic"
    / "versions"
    / "c5d6e7f8a9b0_add_ai_chats_multi_chat.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("ai_chats_migration", MIGRATION_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def old_shape_db(tmp_path):
    """SQLite DB with the PRE-migration schema and old-shaped message rows.

    Groups: (u1, s1) user+assistant with a 60-char question (title truncation),
    (u1, s2) short user question, (u1, s3) assistant-only (title NULL).
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    meta = MetaData()
    Table("users", meta, Column("id", String(36), primary_key=True))
    Table(
        "sessions", meta,
        Column("id", String(36), primary_key=True),
        Column("user_id", String(36)),
    )
    Table(
        "ai_chat_messages", meta,
        Column("id", Integer, primary_key=True),
        Column("user_id", String(36), nullable=False),
        Column("session_id", String(36), nullable=False),
        Column("role", String(16), nullable=False),
        Column("content", Text, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )
    meta.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id) VALUES ('u1')"))
        for sid in ("s1", "s2", "s3"):
            conn.execute(
                text("INSERT INTO sessions (id, user_id) VALUES (:s, 'u1')"),
                {"s": sid},
            )
        conn.execute(text(
            "INSERT INTO ai_chat_messages (id, user_id, session_id, role, content, created_at) "
            "VALUES (1, 'u1', 's1', 'user', :q, '2026-11-13 10:00:00.000000')"
        ), {"q": "A" * 60})
        conn.execute(text(
            "INSERT INTO ai_chat_messages (id, user_id, session_id, role, content, created_at) "
            "VALUES (2, 'u1', 's1', 'assistant', 'answer one', '2026-11-13 10:00:01.000000')"
        ))
        conn.execute(text(
            "INSERT INTO ai_chat_messages (id, user_id, session_id, role, content, created_at) "
            "VALUES (3, 'u1', 's2', 'user', 'short question', '2026-11-13 10:01:00.000000')"
        ))
        conn.execute(text(
            "INSERT INTO ai_chat_messages (id, user_id, session_id, role, content, created_at) "
            "VALUES (4, 'u1', 's3', 'assistant', 'orphan answer', '2026-11-13 10:02:00.000000')"
        ))
    return engine


def _run_upgrade(engine):
    mod = _load_migration()
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mod.upgrade()
        conn.commit()


class TestMigrationBackfill:
    def test_one_chat_per_group_with_titles(self, old_shape_db):
        _run_upgrade(old_shape_db)
        with old_shape_db.connect() as conn:
            chats = conn.execute(text(
                "SELECT session_id, title, created_at FROM ai_chats "
                "ORDER BY session_id"
            )).fetchall()

            assert len(chats) == 3
            by_session = {c.session_id: c for c in chats}
            # Title = first user message's first 50 chars.
            assert by_session["s1"].title == "A" * 50
            assert by_session["s2"].title == "short question"
            # Assistant-only group -> NULL title.
            assert by_session["s3"].title is None
            # Chat created_at = the group's earliest message.
            assert str(by_session["s1"].created_at).startswith("2026-11-13 10:00")

    def test_all_messages_point_at_their_group_chat(self, old_shape_db):
        _run_upgrade(old_shape_db)
        with old_shape_db.connect() as conn:
            rows = conn.execute(text(
                "SELECT m.id, m.session_id, m.chat_id, c.id AS chat_exists "
                "FROM ai_chat_messages m LEFT JOIN ai_chats c ON c.id = m.chat_id "
                "ORDER BY m.id"
            )).fetchall()

            assert len(rows) == 4
            chat_by_session = {}
            for r in rows:
                assert r.chat_id is not None
                assert r.chat_exists is not None
                chat_by_session.setdefault(r.session_id, r.chat_id)
                assert chat_by_session[r.session_id] == r.chat_id
            assert len(chat_by_session) == 3  # one chat per (user, session) group

    def test_chat_id_is_not_null_after_backfill(self, old_shape_db):
        _run_upgrade(old_shape_db)
        with old_shape_db.begin() as conn:
            with pytest.raises(IntegrityError):
                conn.execute(text(
                    "INSERT INTO ai_chat_messages "
                    "(id, user_id, session_id, chat_id, role, content, created_at) "
                    "VALUES (99, 'u1', 's1', NULL, 'user', 'x', "
                    "'2026-11-13 12:00:00.000000')"
                ))

    def test_downgrade_restores_old_shape(self, old_shape_db):
        _run_upgrade(old_shape_db)
        mod = _load_migration()
        with old_shape_db.connect() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                mod.downgrade()
            conn.commit()
        with old_shape_db.connect() as conn:
            tables = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "ORDER BY name"
            )).fetchall()
            names = {t.name for t in tables}
            assert "ai_chats" not in names
            cols = conn.execute(text(
                "PRAGMA table_info(ai_chat_messages)"
            )).fetchall()
            assert "chat_id" not in {c.name for c in cols}
