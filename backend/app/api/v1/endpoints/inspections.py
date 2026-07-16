"""
Inspection API endpoints.

Manage the inspection lifecycle for structural assets.
Phase 2 will add a /run endpoint that triggers the vision engine.
"""
from fastapi import APIRouter, HTTPException, Query, status

from backend.app.dependencies import InspectionServiceDep
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.inspection import InspectionCreate, InspectionResponse, InspectionUpdate

router = APIRouter(prefix="/inspections", tags=["Inspections"])


@router.post(
    "/",
    response_model=InspectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new inspection record",
    description=(
        "Creates an inspection record for an asset in PENDING status. "
        "Phase 2 will extend this to automatically trigger the vision engine."
    ),
    responses={404: {"description": "Asset not found"}},
)
async def create_inspection(
    data: InspectionCreate,
    service: InspectionServiceDep,
) -> InspectionResponse:
    """Create a new inspection (validates asset exists)."""
    inspection = await service.create_inspection(data)
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{data.asset_id}' not found.",
        )
    return InspectionResponse.model_validate(inspection)


@router.get(
    "/",
    response_model=PaginatedResponse[InspectionResponse],
    summary="List all inspections",
    description="Returns a paginated list of all inspection records.",
)
async def list_inspections(
    service: InspectionServiceDep,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page."),
) -> PaginatedResponse[InspectionResponse]:
    """Paginated inspection list."""
    result = await service.list_inspections(page=page, page_size=page_size)
    return PaginatedResponse[InspectionResponse](
        items=[InspectionResponse.model_validate(i) for i in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
    )


@router.get(
    "/asset/{asset_id}",
    response_model=list[InspectionResponse],
    summary="List inspections for an asset",
    description="Returns all inspection records for a specific asset, newest first.",
)
async def list_asset_inspections(
    asset_id: str,
    service: InspectionServiceDep,
) -> list[InspectionResponse]:
    """All inspections for a given asset."""
    inspections = await service.list_inspections_for_asset(asset_id)
    return [InspectionResponse.model_validate(i) for i in inspections]


@router.get(
    "/{inspection_id}",
    response_model=InspectionResponse,
    summary="Get a single inspection",
    description="Retrieve an inspection record by its UUID.",
    responses={404: {"description": "Inspection not found"}},
)
async def get_inspection(
    inspection_id: str,
    service: InspectionServiceDep,
) -> InspectionResponse:
    """Fetch a single inspection by ID."""
    inspection = await service.get_inspection(inspection_id)
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found.",
        )
    return InspectionResponse.model_validate(inspection)


@router.patch(
    "/{inspection_id}",
    response_model=InspectionResponse,
    summary="Update an inspection record",
    description=(
        "Partially update an inspection. "
        "Used by the vision engine (Phase 2) to populate results, "
        "and by operators to add notes or correct status."
    ),
    responses={404: {"description": "Inspection not found"}},
)
async def update_inspection(
    inspection_id: str,
    data: InspectionUpdate,
    service: InspectionServiceDep,
) -> InspectionResponse:
    """Partial update of an inspection."""
    inspection = await service.update_inspection(inspection_id, data)
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found.",
        )
    return InspectionResponse.model_validate(inspection)
