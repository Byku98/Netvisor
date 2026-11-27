"""Automatic DB migrations at app startup (issue #7).

2026-11-27: a prod deploy shipped code reading a new column while the prod
DB was never migrated (migrations were manual) — every DB-touching endpoint
500'd until a manual 'alembic upgrade head'. This module makes the app bring
its own DB to alembic head at startup so that failure mode disappears.
"""

from src.config import settings
from src.logging import get_logger

logger = get_logger("migrations")


def run_auto_migrations() -> None:
    """Run 'alembic upgrade head' against the app's configured DB.

    Called from startup_init() (src/api/main.py) — the single funnel point
    for BOTH entry points: the FastAPI lifespan (uvicorn / Docker) and the
    import-time init that Passenger deployments hit (passenger_wsgi.py
    imports src.api.main, whose module scope calls startup_init()). Alembic
    is idempotent at head, so the import-time + lifespan double call inside
    one uvicorn process is a cheap no-op. Multi-worker deployments may see
    a benign "database is locked" when two workers upgrade simultaneously —
    caught and logged below, never fatal.

    Failure behavior: NEVER raises out of startup. A crash-looping
    Passenger app is worse than DB-route 500s, and a transient SQLite lock
    must not kill the app — failures are logged loudly with the manual
    remediation and startup continues.
    """
    if not settings.auto_migrate:
        logger.info("Auto-migration disabled (NETVISOR_AUTO_MIGRATE=false)")
        return
    try:
        # Imported lazily: keeps app import light and turns a missing
        # alembic install into a logged failure instead of a startup crash.
        from alembic.config import Config

        from alembic import command

        # alembic.ini sits next to the backend package root (config.py's
        # base_dir): /app in the Docker image, the backend dir on shared
        # hosting. Its script_location uses %(here)s, so it resolves from
        # any working directory.
        ini_path = settings.base_dir / "alembic.ini"
        cfg = Config(str(ini_path))
        # env.py reads the DB URL from src.config.settings, so this targets
        # the SAME database the app uses (NETVISOR_DB_PATH / data dir).
        # The in_process attribute tells env.py to skip its fileConfig()
        # call — applying alembic's logging config in-process would clobber
        # the app's logging (disables the netvisor.* loggers and replaces
        # the root handler). Standalone CLI runs are unaffected.
        cfg.attributes["in_process"] = True
        # Fresh-deploy insurance: alembic does not create the DB's parent
        # directory (e.g. a new named volume mount point).
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        command.upgrade(cfg, "head")
        logger.info("DB migrations up to date (alembic head)")
    except Exception:
        logger.exception(
            "AUTO-MIGRATION FAILED - DB schema may be out of date and "
            "DB-touching endpoints may return 500. Manual fix: run "
            "'alembic upgrade head' in the app venv from the backend "
            "directory. Continuing startup."
        )
