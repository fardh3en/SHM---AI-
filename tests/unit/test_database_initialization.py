"""
Unit tests reproducing and verifying the production database schema initialization fix.

Addresses:
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: inspections

Verifies:
1. Reproduction: A fresh database without schema initialization fails on inspections query.
2. Fix: create_db_and_tables / init_database creates all required tables even when APP_ENV=production.
3. Non-destructive: Schema initialization on a database with existing records preserves all rows.
4. Alembic: Baseline migration executes upgrade head and creates the inspections table.
5. Lifespan: FastAPI lifespan initializes database in production mode so endpoints succeed.
"""
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from starlette.testclient import TestClient

from backend.app.config import get_settings
from backend.app.database.session import create_db_and_tables


def test_reproduce_missing_table_error_on_uninitialized_database(tmp_path: Path) -> None:
    """Reproduces: querying inspections on an uninitialized SQLite file raises no such table: inspections."""
    empty_db = tmp_path / "uninitialized.db"
    # Create empty SQLite file
    conn = sqlite3.connect(str(empty_db))
    conn.close()

    conn = sqlite3.connect(str(empty_db))
    cursor = conn.cursor()
    with pytest.raises(sqlite3.OperationalError) as exc_info:
        cursor.execute("SELECT * FROM inspections;")
    assert "no such table: inspections" in str(exc_info.value)
    conn.close()


@pytest.mark.asyncio
async def test_create_db_and_tables_creates_schema_in_production(tmp_path: Path) -> None:
    """Verifies that create_db_and_tables initializes all tables even in production mode."""
    test_db_path = tmp_path / "prod_test.db"
    db_url = f"sqlite+aiosqlite:///{test_db_path.as_posix()}"

    test_engine = create_async_engine(db_url)
    with patch("backend.app.database.session.engine", test_engine):
        # Run schema initialization
        await create_db_and_tables()

    await test_engine.dispose()

    # Verify tables exist via raw sqlite
    conn = sqlite3.connect(str(test_db_path))
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()

    assert "assets" in tables
    assert "inspections" in tables
    assert "asset_evidence" in tables
    assert "detections" in tables
    assert "health_records" in tables
    assert "degradation_records" in tables


@pytest.mark.asyncio
async def test_create_db_and_tables_preserves_existing_data(tmp_path: Path) -> None:
    """Verifies that running create_db_and_tables on existing tables is non-destructive."""
    test_db_path = tmp_path / "preserve_test.db"
    db_url = f"sqlite+aiosqlite:///{test_db_path.as_posix()}"

    test_engine = create_async_engine(db_url)
    with patch("backend.app.database.session.engine", test_engine):
        # 1. First initialization
        await create_db_and_tables()

        # 2. Insert dummy asset and inspection record
        SessionMaker = async_sessionmaker(bind=test_engine, class_=AsyncSession)
        async with SessionMaker() as session:
            await session.execute(
                text(
                    "INSERT INTO assets (id, name, asset_type, status) "
                    "VALUES ('asset-123', 'Historic Bridge', 'BRIDGE', 'ACTIVE')"
                )
            )
            await session.execute(
                text(
                    "INSERT INTO inspections (id, asset_id, status, source, defect_count) "
                    "VALUES ('insp-456', 'asset-123', 'PENDING', 'IMAGE', 0)"
                )
            )
            await session.commit()

        # 3. Second initialization (simulate container reboot/restart)
        await create_db_and_tables()

        # 4. Verify existing records were not deleted or truncated
        async with SessionMaker() as session:
            asset_res = await session.execute(text("SELECT name FROM assets WHERE id='asset-123'"))
            asset_row = asset_res.scalar()
            assert asset_row == "Historic Bridge"

            insp_res = await session.execute(text("SELECT status FROM inspections WHERE id='insp-456'"))
            insp_row = insp_res.scalar()
            assert insp_row == "PENDING"

    await test_engine.dispose()


def test_alembic_upgrade_head_creates_inspections_table(tmp_path: Path) -> None:
    """Verifies that the project's Alembic migration successfully creates the inspections table."""
    alembic_db = tmp_path / "alembic_test.db"
    alembic_db_url = f"sqlite+aiosqlite:///{alembic_db.as_posix()}"

    from alembic.config import Config
    from alembic import command

    ini_path = Path(__file__).resolve().parent.parent.parent / "backend" / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", alembic_db_url)

    # Run Alembic upgrade head
    command.upgrade(cfg, "head")

    conn = sqlite3.connect(str(alembic_db))
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()

    assert "inspections" in tables
    assert "assets" in tables
    assert "alembic_version" in tables


def test_fastapi_lifespan_initializes_database_in_production(tmp_path: Path) -> None:
    """Verifies that FastAPI lifespan initializes the database in production so API calls succeed."""
    prod_db = tmp_path / "prod_lifespan.db"
    prod_db_url = f"sqlite+aiosqlite:///{prod_db.as_posix()}"

    with patch.dict("os.environ", {"APP_ENV": "production", "DATABASE_URL": prod_db_url}):
        # Clear settings cache so new env takes effect
        from backend.app.config import get_settings
        get_settings.cache_clear()

        from backend.app.main import app

        # TestClient invokes lifespan context manager on enter
        with TestClient(app) as client:
            # Query inspections endpoint — should succeed with 200 and empty list instead of 500 no such table
            response = client.get("/api/v1/inspections/")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert isinstance(data["items"], list)

        get_settings.cache_clear()


def test_alembic_schema_matches_models_zero_diff(tmp_path: Path) -> None:
    """Verifies that the Alembic baseline migration produces a schema identical to Base.metadata."""
    from alembic.migration import MigrationContext
    from alembic.autogenerate import compare_metadata
    from sqlalchemy import create_engine
    from alembic.config import Config
    from alembic import command
    from backend.app.models.base import Base

    alembic_db = tmp_path / "diff_test.db"
    alembic_db_url = f"sqlite+aiosqlite:///{alembic_db.as_posix()}"

    ini_path = Path(__file__).resolve().parent.parent.parent / "backend" / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", alembic_db_url)
    command.upgrade(cfg, "head")

    sync_engine = create_engine(f"sqlite:///{alembic_db.as_posix()}")
    with sync_engine.connect() as conn:
        mc = MigrationContext.configure(conn)
        diff = compare_metadata(mc, Base.metadata)
        assert len(diff) == 0, f"Schema discrepancies detected between Alembic migration and models: {diff}"
    sync_engine.dispose()


@pytest.mark.asyncio
async def test_schema_validation_rejects_incomplete_tables(tmp_path: Path) -> None:
    """Verifies that create_db_and_tables refuses to mark schema as valid or stamp head if columns are missing."""
    test_db = tmp_path / "corrupt_schema.db"
    db_url = f"sqlite+aiosqlite:///{test_db.as_posix()}"

    # Manually create a partial table missing required columns
    conn = sqlite3.connect(str(test_db))
    conn.execute("CREATE TABLE assets (id VARCHAR(36) PRIMARY KEY, name VARCHAR(255))")
    conn.commit()
    conn.close()

    test_engine = create_async_engine(db_url)
    with patch("backend.app.database.session.engine", test_engine):
        with pytest.raises(RuntimeError) as exc_info:
            await create_db_and_tables()
        assert "Database schema validation failed" in str(exc_info.value)
        assert "missing columns" in str(exc_info.value)

    # Check that alembic_version was NOT stamped
    conn = sqlite3.connect(str(test_db))
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    assert "alembic_version" not in tables

    await test_engine.dispose()
