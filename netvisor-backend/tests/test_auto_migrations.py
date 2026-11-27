"""Auto-migration at startup (issue #7): src.db.migrations.run_auto_migrations()."""

import sqlite3

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

from src.config import settings
from src.db.migrations import run_auto_migrations


def _alembic_head() -> str:
    """Head revision according to the repo's migration scripts."""
    cfg = AlembicConfig(str(settings.base_dir / "alembic.ini"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def _table_names(db_path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _stamped_revisions(db_path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    return [r[0] for r in rows]


class TestAutoMigrations:
    def test_fresh_db_migrates_to_head(self, tmp_path, monkeypatch):
        """Empty DB -> full schema created and alembic_version stamped at head."""
        db_path = tmp_path / "fresh.db"
        monkeypatch.setattr(settings, "db_path", db_path)

        run_auto_migrations()

        tables = _table_names(db_path)
        assert "sessions" in tables
        assert "users" in tables
        assert _stamped_revisions(db_path) == [_alembic_head()]

    def test_second_call_is_a_noop(self, tmp_path, monkeypatch):
        """Already at head -> second call neither raises nor changes the stamp."""
        db_path = tmp_path / "fresh.db"
        monkeypatch.setattr(settings, "db_path", db_path)

        run_auto_migrations()
        before = _stamped_revisions(db_path)
        run_auto_migrations()

        assert _stamped_revisions(db_path) == before == [_alembic_head()]

    def test_disabled_flag_does_not_touch_db(self, tmp_path, monkeypatch):
        """NETVISOR_AUTO_MIGRATE=false -> alembic never connects (no file at all)."""
        db_path = tmp_path / "off.db"
        monkeypatch.setattr(settings, "db_path", db_path)
        monkeypatch.setattr(settings, "auto_migrate", False)

        run_auto_migrations()

        assert not db_path.exists()

    def test_failure_is_logged_not_raised(self, tmp_path, monkeypatch, caplog):
        """A raising alembic must not propagate out of startup (log + continue)."""
        db_path = tmp_path / "boom.db"
        monkeypatch.setattr(settings, "db_path", db_path)

        def boom(cfg, revision):
            raise RuntimeError("simulated migration failure")

        monkeypatch.setattr("alembic.command.upgrade", boom)
        with caplog.at_level("ERROR", logger="netvisor.migrations"):
            run_auto_migrations()

        assert any("AUTO-MIGRATION FAILED" in r.getMessage() for r in caplog.records)
