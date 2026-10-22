"""
Asset evidence API endpoints.
"""
from fastapi import APIRouter, HTTPException, status

from backend.app.dependencies import EvidenceServiceDep
from backend.app.schemas.asset_evidence import (
    AssetEvidenceCreate,
    AssetEvidenceResponse,
)

router = APIRouter(tags=["Evidence"])


@router.get(
    "/assets/{asset_id}/evidence",
    response_model=list[AssetEvidenceResponse],
    summary="List evidence photos for an asset",
    description="Returns all visual evidence photographs and inspections media for a given asset.",
)
async def list_asset_evidence(
    asset_id: str,
    service: EvidenceServiceDep,
) -> list[AssetEvidenceResponse]:
    """Retrieve all evidence files for an asset."""
    items = await service.list_for_asset(asset_id)
    return [AssetEvidenceResponse.model_validate(e) for e in items]


@router.post(
    "/assets/{asset_id}/evidence",
    response_model=AssetEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new evidence for an asset",
    description="Associates a new evidence photograph with an asset.",
    responses={
        404: {"description": "Asset not found"},
        422: {"description": "Asset ID in path and request body mismatch"},
    },
)
async def create_asset_evidence(
    asset_id: str,
    data: AssetEvidenceCreate,
    service: EvidenceServiceDep,
) -> AssetEvidenceResponse:
    """Register visual evidence."""
    if data.asset_id and data.asset_id != asset_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Asset ID in path ('{asset_id}') and body ('{data.asset_id}') must match.",
        )
    if not data.asset_id:
        data = data.model_copy(update={"asset_id": asset_id})
    evidence = await service.create_evidence(data)
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{asset_id}' not found.",
        )
    return AssetEvidenceResponse.model_validate(evidence)


@router.get(
    "/evidence/{evidence_id}",
    response_model=AssetEvidenceResponse,
    summary="Get single evidence record",
    description="Retrieve visual evidence metadata by UUID.",
    responses={404: {"description": "Evidence not found"}},
)
async def get_evidence(
    evidence_id: str,
    service: EvidenceServiceDep,
) -> AssetEvidenceResponse:
    """Fetch single evidence item."""
    evidence = await service.get_evidence(evidence_id)
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence '{evidence_id}' not found.",
        )
    return AssetEvidenceResponse.model_validate(evidence)
