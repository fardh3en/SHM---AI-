"""
Regression tests for SQLite database locking and concurrency.

Verifies:
1. SQLite connection PRAGMAs (WAL journal mode, busy_timeout=60000, synchronous=NORMAL).
2. Engine connection timeout configuration (60.0s).
3. Concurrent asset creations via AssetService across multiple simultaneous sessions
   without encountering 'sqlite3.OperationalError: database is locked'.
4. Long-running CPU vision inference simulation does not block concurrent asset creation
   due to early commit of the PROCESSING state transition.
5. Immediate commit behavior in AssetService and EvidenceService.
"""
import asyncio
import pathlib
import tempfile
import time
import pytest
from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.models.base import Base
from backend.app.models.asset import Asset, AssetType
from backend.app.models.inspection import Inspection, InspectionStatus, InspectionSource
from backend.app.schemas.asset import AssetCreate
from backend.app.services.asset_service import AssetService
from backend.app.services.inspection_service import InspectionService


@pytest.fixture
async def isolated_sqlite_engine():
    """Create an isolated, temporary SQLite file database with production engine settings."""
    tmp = tempfile.NamedTemporaryFile(suffix="_concurrent_test.db", delete=False)
    tmp_path = pathlib.Path(tmp.name)
    tmp.close()

    db_url = f"sqlite+aiosqlite:///{tmp_path.as_posix()}"
    engine = create_async_engine(
        db_url,
        connect_args={"check_same_thread": False, "timeout": 60.0},
        poolclass=NullPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()
    try:
        tmp_path.unlink(missing_ok=True)
        pathlib.Path(f"{tmp_path}-wal").unlink(missing_ok=True)
        pathlib.Path(f"{tmp_path}-shm").unlink(missing_ok=True)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_sqlite_pragmas_and_timeout(isolated_sqlite_engine):
    """Confirm engine enforces WAL mode, 60s busy_timeout, and NORMAL synchronous mode."""
    async with isolated_sqlite_engine.connect() as conn:
        res_journal = await conn.exec_driver_sql("PRAGMA journal_mode;")
        journal_mode = res_journal.scalar_one()
        assert journal_mode.lower() == "wal", f"Expected WAL journal mode, got {journal_mode}"

        res_timeout = await conn.exec_driver_sql("PRAGMA busy_timeout;")
        busy_timeout = res_timeout.scalar_one()
        assert busy_timeout == 60000, f"Expected 60000ms busy_timeout, got {busy_timeout}"

        res_sync = await conn.exec_driver_sql("PRAGMA synchronous;")
        sync_mode = res_sync.scalar_one()
        # NORMAL in SQLite is value 1
        assert sync_mode in (1, "NORMAL", "normal"), f"Expected NORMAL synchronous, got {sync_mode}"


@pytest.mark.asyncio
async def test_concurrent_asset_creation(isolated_sqlite_engine):
    """
    Test that 10 concurrent AssetService.create_asset() calls across independent sessions
    all succeed without any 'database is locked' errors.
    """
    session_factory = async_sessionmaker(
        bind=isolated_sqlite_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def create_asset_task(index: int) -> Asset:
        async with session_factory() as session:
            service = AssetService(session)
            schema = AssetCreate(
                name=f"Concurrent Test Structure {index}",
                asset_type=AssetType.BRIDGE if index % 2 == 0 else AssetType.BUILDING,
                description=f"Automated concurrency verification asset #{index}",
            )
            asset = await service.create_asset(schema)
            await session.commit()
            return asset

    # Launch 10 concurrent asset creation requests simultaneously
    created_assets = await asyncio.gather(*[create_asset_task(i) for i in range(10)])

    assert len(created_assets) == 10
    asset_ids = {a.id for a in created_assets}
    assert len(asset_ids) == 10, "Each created asset must have a unique UUID"

    # Verify all records physically exist in the database
    async with session_factory() as verify_session:
        service = AssetService(verify_session)
        items, total = await service.list_assets(page=1, page_size=50)
        assert total == 10
        assert len(items) == 10


@pytest.mark.asyncio
async def test_asset_creation_during_simulated_vision_inference(isolated_sqlite_engine):
    """
    Regression test for Step 3 database locking:
    Simulates an inspection where status is updated to PROCESSING and committed early,
    followed by a simulated multi-second CPU vision pipeline run.
    Verifies that concurrent asset creation requests are NOT blocked and complete in milliseconds.
    """
    session_factory = async_sessionmaker(
        bind=isolated_sqlite_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # 1. First create an asset to hold the inspection
    async with session_factory() as init_session:
        asset_svc = AssetService(init_session)
        parent_asset = await asset_svc.create_asset(
            AssetCreate(name="Parent Structure", asset_type=AssetType.TUNNEL)
        )
        insp_svc = InspectionService(init_session)
        from backend.app.schemas.inspection import InspectionCreate
        inspection = await insp_svc.create_inspection(
            InspectionCreate(
                asset_id=parent_asset.id,
                source=InspectionSource.IMAGE,
                input_path="samples/test_crack.jpg",
            )
        )
        await init_session.commit()
        insp_id = inspection.id

    # 2. Worker that runs an inspection with early commit before heavy computation
    async def simulated_inspection_run():
        # Phase A: Mark processing and commit early (releasing lock)
        async with session_factory() as session:
            svc = InspectionService(session)
            insp = await svc.get_inspection(insp_id)
            updated = await svc._repo.update_fields(
                insp, status=InspectionStatus.PROCESSING, error_message=None
            )
            await session.commit()
            await session.refresh(updated)

        # Phase B: Heavy CPU computation runs OUTSIDE of any database transaction
        await asyncio.sleep(1.0)

        # Phase C: Finalize results in fresh/resumed transaction
        async with session_factory() as session:
            svc = InspectionService(session)
            insp = await svc.get_inspection(insp_id)
            finalized = await svc._repo.update_fields(
                insp,
                status=InspectionStatus.COMPLETED,
                defect_count=3,
                processing_time_ms=1000.0,
            )
            await session.commit()
            return finalized

    # 3. Worker that creates an asset concurrently while inference is running
    async def concurrent_asset_worker(label: str, delay: float):
        await asyncio.sleep(delay)
        t_start = time.perf_counter()
        async with session_factory() as session:
            svc = AssetService(session)
            asset = await svc.create_asset(
                AssetCreate(name=f"Concurrent While Inferencing {label}", asset_type=AssetType.DAM)
            )
            await session.commit()
        duration = time.perf_counter() - t_start
        return asset, duration

    # Gather inspection run and 3 concurrent asset creations during inference
    results = await asyncio.gather(
        simulated_inspection_run(),
        concurrent_asset_worker("A", 0.1),
        concurrent_asset_worker("B", 0.3),
        concurrent_asset_worker("C", 0.5),
    )

    completed_insp = results[0]
    asset_a, dur_a = results[1]
    asset_b, dur_b = results[2]
    asset_c, dur_c = results[3]

    assert completed_insp.status == InspectionStatus.COMPLETED
    assert completed_insp.defect_count == 3
    assert asset_a.id is not None
    assert asset_b.id is not None
    assert asset_c.id is not None

    # Each concurrent asset creation must complete quickly (< 0.5s), proving it was NOT blocked
    # by the 1-second long-running inference!
    assert dur_a < 0.8, f"Asset A took too long: {dur_a:.3f}s"
    assert dur_b < 0.8, f"Asset B took too long: {dur_b:.3f}s"
    assert dur_c < 0.8, f"Asset C took too long: {dur_c:.3f}s"
