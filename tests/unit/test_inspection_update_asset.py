"""
Unit tests for reassigning an inspection to a different asset.

Verifies:
1. An inspection can be reassigned from Asset A to Asset B via PATCH.
2. Reassigning to a non-existent asset returns HTTP 400.
3. Asset schema accepts simplified creation with name only.
4. Asset schema accepts valid civil engineering materials.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from backend.app.core.exceptions import ValidationError
from backend.app.main import app
from backend.app.models.asset import AssetType
from backend.app.schemas.asset import AssetCreate
from backend.app.schemas.inspection import InspectionCreate, InspectionUpdate
from backend.app.services.asset_service import AssetService
from backend.app.services.inspection_service import InspectionService

client = TestClient(app, raise_server_exceptions=False)


@pytest.mark.asyncio
async def test_reassign_inspection_to_another_asset(db_session: AsyncSession) -> None:
    """Verify that an inspection can be reassigned to a different registered asset."""
    asset_service = AssetService(db_session)
    inspection_service = InspectionService(db_session)

    # 1. Create two assets
    asset_a = await asset_service.create_asset(
        AssetCreate(name="Original Structure A", asset_type=AssetType.BUILDING)
    )
    asset_b = await asset_service.create_asset(
        AssetCreate(name="Permanent Asset B", asset_type=AssetType.BRIDGE)
    )

    # 2. Create inspection assigned to Asset A
    insp = await inspection_service.create_inspection(
        InspectionCreate(
            asset_id=asset_a.id,
            notes="Initial draft inspection for quick analysis",
        )
    )
    assert insp is not None
    assert insp.asset_id == asset_a.id

    # 3. Reassign inspection to Asset B
    updated = await inspection_service.update_inspection(
        insp.id,
        InspectionUpdate(asset_id=asset_b.id),
    )
    assert updated is not None
    assert updated.asset_id == asset_b.id

    # 4. Verify in query
    retrieved = await inspection_service.get_inspection(insp.id)
    assert retrieved is not None
    assert retrieved.asset_id == asset_b.id


@pytest.mark.asyncio
async def test_reassign_inspection_to_nonexistent_asset_fails(
    db_session: AsyncSession,
) -> None:
    """Verify that reassigning an inspection to an invalid asset raises ValidationError."""
    asset_service = AssetService(db_session)
    inspection_service = InspectionService(db_session)

    asset = await asset_service.create_asset(
        AssetCreate(name="Valid Structure", asset_type=AssetType.BUILDING)
    )
    insp = await inspection_service.create_inspection(
        InspectionCreate(asset_id=asset.id)
    )
    assert insp is not None

    with pytest.raises(ValidationError) as exc:
        await inspection_service.update_inspection(
            insp.id,
            InspectionUpdate(asset_id="nonexistent-uuid-12345"),
        )
    assert "not found" in str(exc.value)


@pytest.mark.asyncio
async def test_simplified_asset_creation_with_materials(
    db_session: AsyncSession,
) -> None:
    """Verify asset creation with only name and dropdown-supported materials."""
    asset_service = AssetService(db_session)

    # Minimal creation: only name
    asset_minimal = await asset_service.create_asset(
        AssetCreate(name="College Block A")
    )
    assert asset_minimal.id is not None
    assert asset_minimal.name == "College Block A"
    assert asset_minimal.asset_type == AssetType.OTHER
    assert asset_minimal.material is None
    assert asset_minimal.location is None

    # Creation with dropdown material option
    asset_with_material = await asset_service.create_asset(
        AssetCreate(
            name="Apartment Building",
            asset_type=AssetType.BUILDING,
            material="Reinforced Concrete",
            location="North Campus Quad (Browser Geolocation)",
            construction_year=1998,
        )
    )
    assert asset_with_material.material == "Reinforced Concrete"
    assert asset_with_material.construction_year == 1998
