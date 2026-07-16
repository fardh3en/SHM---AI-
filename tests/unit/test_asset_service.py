import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.asset import AssetStatus, AssetType
from backend.app.schemas.asset import AssetCreate, AssetUpdate
from backend.app.services.asset_service import AssetService


@pytest.mark.asyncio
async def test_create_and_get_asset(db_session: AsyncSession) -> None:
    """Verify that an asset can be created and retrieved from the service."""
    service = AssetService(db_session)
    
    # 1. Create asset
    create_schema = AssetCreate(
        name="Test Bridge Pier 4",
        asset_type=AssetType.BRIDGE,
        location="50.0 N, 20.0 W",
        description="A bridge pier for testing",
        construction_year=1995,
        material="reinforced concrete",
        design_life_years=50.0
    )
    
    asset = await service.create_asset(create_schema)
    assert asset.id is not None
    assert asset.name == "Test Bridge Pier 4"
    assert asset.asset_type == AssetType.BRIDGE
    assert asset.status == AssetStatus.ACTIVE
    
    # 2. Retrieve asset
    retrieved = await service.get_asset(asset.id)
    assert retrieved is not None
    assert retrieved.id == asset.id
    assert retrieved.name == "Test Bridge Pier 4"


@pytest.mark.asyncio
async def test_update_asset(db_session: AsyncSession) -> None:
    """Verify partial asset field updates work correctly."""
    service = AssetService(db_session)
    
    asset = await service.create_asset(
        AssetCreate(name="Original Name", asset_type=AssetType.TUNNEL)
    )
    
    # Update status and description
    update_schema = AssetUpdate(
        name="Updated Name",
        status=AssetStatus.UNDER_MAINTENANCE,
        description="Performing crack sealing"
    )
    
    updated = await service.update_asset(asset.id, update_schema)
    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.status == AssetStatus.UNDER_MAINTENANCE
    assert updated.description == "Performing crack sealing"
    # Verify type wasn't overwritten
    assert updated.asset_type == AssetType.TUNNEL


@pytest.mark.asyncio
async def test_delete_asset(db_session: AsyncSession) -> None:
    """Verify that deleting an asset removes it from database."""
    service = AssetService(db_session)
    
    asset = await service.create_asset(
        AssetCreate(name="To Delete", asset_type=AssetType.ROAD)
    )
    
    # Delete
    success = await service.delete_asset(asset.id)
    assert success is True
    
    # Confirm it's gone
    retrieved = await service.get_asset(asset.id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_list_assets(db_session: AsyncSession) -> None:
    """Verify paginated listing of assets."""
    service = AssetService(db_session)
    
    # Seed 3 test assets
    await service.create_asset(AssetCreate(name="Asset A", asset_type=AssetType.DAM))
    await service.create_asset(AssetCreate(name="Asset B", asset_type=AssetType.DAM))
    await service.create_asset(AssetCreate(name="Asset C", asset_type=AssetType.DAM))
    
    paginated = await service.list_assets(page=1, page_size=2)
    assert paginated.total == 3
    assert len(paginated.items) == 2
    assert paginated.pages == 2
