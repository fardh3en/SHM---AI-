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
        # aiosqlite requires StaticPool for correct async behaviour.
        # check_same_thread must be False when sharing across coroutines.
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    else:
        # PostgreSQL / production — use connection pool with health checks.
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_recycle"] = 3600  # recycle connections every hour

    return kwargs


# ── Engine (module-level singleton) ───────────────────────────────────────────
engine = create_async_engine(settings.DATABASE_URL, **_build_engine_kwargs())

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
    Create all ORM-defined tables in the database.

    Called once at application startup via the FastAPI lifespan handler.
    In production, Alembic migrations should be used instead.
    """
    # Local imports prevent circular dependency issues at module load time
    from backend.app.models.base import Base  # noqa: PLC0415

    # Importing each model registers it with Base.metadata
    import backend.app.models.asset  # noqa: F401, PLC0415
    import backend.app.models.detection  # noqa: F401, PLC0415
    import backend.app.models.degradation_record  # noqa: F401, PLC0415
    import backend.app.models.health_record  # noqa: F401, PLC0415
    import backend.app.models.inspection  # noqa: F401, PLC0415

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created / verified successfully.")


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
