import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.asset import AssetType
from backend.app.models.asset_evidence import EvidenceClassification
from backend.app.schemas.asset import AssetCreate
from backend.app.schemas.asset_evidence import AssetEvidenceCreate
from backend.app.services.asset_service import AssetService
from backend.app.services.evidence_service import EvidenceService


@pytest.mark.asyncio
async def test_create_and_list_evidence(db_session: AsyncSession) -> None:
    asset_service = AssetService(db_session)
    evidence_service = EvidenceService(db_session)

    asset = await asset_service.create_asset(
        AssetCreate(name="Evidence Test Bridge", asset_type=AssetType.BRIDGE)
    )

    ev_create = AssetEvidenceCreate(
        asset_id=asset.id,
        filename="test_pier_photo.jpg",
        file_path="/uploads/evidence/test_pier_photo.jpg",
        caption="North Pier Tidal Waterline",
        component_description="Reinforced concrete waterline splash zone inspection.",
        classification=EvidenceClassification.VERIFIED_STRUCTURE,
        creator="Test Photographer",
        license="CC BY-SA 4.0",
        source_url="https://example.com/photo",
        is_sample=True,
    )

    created = await evidence_service.create_evidence(ev_create)
    assert created is not None
    assert created.id is not None
    assert created.asset_id == asset.id
    assert created.classification == EvidenceClassification.VERIFIED_STRUCTURE

    # Retrieve list for asset
    items = await evidence_service.list_for_asset(asset.id)
    assert len(items) == 1
    assert items[0].filename == "test_pier_photo.jpg"

    # Idempotency test — re-creating with same filename should return existing record
    duplicate = await evidence_service.create_evidence(ev_create)
    assert duplicate is not None
    assert duplicate.id == created.id

    # Verify list count is still 1
    items_after = await evidence_service.list_for_asset(asset.id)
    assert len(items_after) == 1
