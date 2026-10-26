import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Core app imports to configure logging and metadata
from backend.app.config import get_settings
from backend.app.models.base import Base

# Ensure all models are registered on Base metadata
import backend.app.models.asset  # noqa: F401
import backend.app.models.asset_evidence  # noqa: F401
import backend.app.models.inspection  # noqa: F401
import backend.app.models.detection  # noqa: F401
import backend.app.models.health_record  # noqa: F401
import backend.app.models.degradation_record  # noqa: F401

# Alembic Config object
config = context.config

# Interpret the config file for Python standard logging if present and configured
if config.config_file_name is not None and config.get_section("formatters"):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Retrieve dynamic DB URL from Settings instead of alembic.ini hardcoding
settings = get_settings()
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' (async connection) mode."""
    configuration = config.get_section(config.config_ini_section, {})
    # Use config URL if set, otherwise fallback to settings
    url = config.get_main_option("sqlalchemy.url") or settings.DATABASE_URL
    configuration["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
