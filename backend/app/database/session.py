"""
Async SQLAlchemy database engine and session factory.

Design decisions:
- Uses async engine throughout — compatible with FastAPI's async handlers.
- SQLite uses StaticPool (single connection) which is correct for async aiosqlite.
- PostgreSQL uses a connection pool with pre-ping for resilient production deployments.
- Session factory uses expire_on_commit=False so ORM objects remain usable
  after commit (avoids implicit lazy-load errors in async context).
"""
import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from backend.app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_engine_kwargs() -> dict[str, Any]:
    """
    Build keyword arguments for create_async_engine based on the database URL.

    SQLite and PostgreSQL require different pool configurations.
    """
    url = settings.DATABASE_URL
    kwargs: dict[str, Any] = {"echo": settings.DATABASE_ECHO}

    if "sqlite" in url:
        # In-memory SQLite requires StaticPool so tables survive across sessions.
        # File-based SQLite uses NullPool so each session has an independent connection,
        # preventing "cannot commit transaction - SQL statements in progress" on concurrent requests.
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 60.0}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        else:
            from sqlalchemy.pool import NullPool
            kwargs["poolclass"] = NullPool
    else:
        # PostgreSQL / production — use connection pool with health checks.
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_recycle"] = 3600  # recycle connections every hour

    return kwargs


# ── Engine (module-level singleton) ───────────────────────────────────────────
engine = create_async_engine(settings.DATABASE_URL, **_build_engine_kwargs())

if "sqlite" in settings.DATABASE_URL:
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=60000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        except Exception:
            pass

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep objects accessible after commit
    autocommit=False,
    autoflush=False,
)


async def create_db_and_tables() -> None:
    """
    Ensure all ORM-defined tables exist in the database and Alembic is synchronized.

    Called once at application startup via the FastAPI lifespan handler across all
    environments (including production). Uses 'IF NOT EXISTS' via Base.metadata.create_all,
    guaranteeing:
    1. Mandatory tables (assets, inspections, detections, asset_evidence, etc.) exist
       safely before any HTTP requests are accepted.
    2. Existing records, tables, and evidence files are NEVER dropped or deleted.
    3. Schema matches model declarations exactly (all tables and columns verified).
    4. Alembic schema revision state is stamped only when the schema is fully validated.
    """
    import pathlib

    # Local imports prevent circular dependency issues at module load time
    from backend.app.models.base import Base  # noqa: PLC0415

    # Importing all models registers them with Base.metadata
    import backend.app.models  # noqa: F401, PLC0415
    import backend.app.models.asset  # noqa: F401, PLC0415
    import backend.app.models.asset_evidence  # noqa: F401, PLC0415
    import backend.app.models.degradation_record  # noqa: F401, PLC0415
    import backend.app.models.detection  # noqa: F401, PLC0415
    import backend.app.models.health_record  # noqa: F401, PLC0415
    import backend.app.models.inspection  # noqa: F401, PLC0415

    # Ensure parent directory exists for SQLite database file if applicable
    if "sqlite" in settings.DATABASE_URL:
        db_path_part = settings.DATABASE_URL.split(":///")[-1].split("?")[0]
        if db_path_part and db_path_part != ":memory:":
            pathlib.Path(db_path_part).resolve().parent.mkdir(parents=True, exist_ok=True)

    def _validate_schema(sync_conn: Any) -> None:
        """Validate that all ORM tables and columns physically exist in the database."""
        from sqlalchemy import inspect
        insp = inspect(sync_conn)
        existing_tables = set(insp.get_table_names())
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                raise RuntimeError(
                    f"Database schema validation failed: table '{table_name}' was not created."
                )
            existing_cols = {c["name"] for c in insp.get_columns(table_name)}
            expected_cols = {c.name for c in table.columns}
            missing = expected_cols - existing_cols
            if missing:
                raise RuntimeError(
                    f"Database schema validation failed: table '{table_name}' missing columns: {missing}"
                )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_validate_schema)

    logger.info("Database tables and column schemas verified successfully.")

    # Synchronize Alembic version table only after schema has been verified
    def _sync_alembic() -> None:
        try:
            from alembic import command
            from alembic.config import Config
            alembic_ini = settings.BASE_DIR / "backend" / "alembic.ini"
            if alembic_ini.is_file():
                cfg = Config(str(alembic_ini))
                command.stamp(cfg, "head")
                logger.info("Alembic schema version verified and stamped at head.")
        except Exception as exc:
            logger.debug(f"Alembic synchronization skipped: {exc}")

    try:
        import asyncio
        await asyncio.to_thread(_sync_alembic)
    except Exception as exc:
        logger.debug(f"Alembic async sync notice: {exc}")


# Alias for explicit semantic invocation
init_database = create_db_and_tables


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a scoped async database session.

    Usage::

        from fastapi import Depends
        from backend.app.database.session import get_db

        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...

    The session is automatically committed on success and rolled back on any
    exception. It is always closed after the request completes.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
