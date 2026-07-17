"""
Inspection API endpoints.

Manage the inspection lifecycle for structural assets, including triggering
the Phase 2 computer vision pipeline via POST /{id}/run.
"""
from fastapi import APIRouter, HTTPException, Query, status

from backend.app.core.exceptions import SHMBaseException
from backend.app.dependencies import CVPipelineDep, InspectionServiceDep
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
        "Call POST /{id}/run afterwards to trigger the vision engine."
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
    items, total = await service.list_inspections(page=page, page_size=page_size)
    return PaginatedResponse[InspectionResponse].build(
        items=[InspectionResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
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


@router.post(
    "/{inspection_id}/run",
    response_model=InspectionResponse,
    summary="Run the vision pipeline for an inspection",
    description=(
        "Synchronously executes the computer vision pipeline (detection, "
        "measurement, and defect persistence) against the inspection's "
        "input_path. The request blocks until processing completes — "
        "there is no background job queue in this phase, so this may take "
        "several seconds depending on image size and model. On success, "
        "the inspection is marked COMPLETED with defect_count and "
        "processing_time_ms populated, and Detection records are created. "
        "On a vision pipeline failure, the inspection is marked FAILED with "
        "error_message populated and this endpoint still returns 200 "
        "(check the response body's status field, not just the HTTP code)."
    ),
    responses={
        404: {"description": "Inspection not found"},
        422: {"description": "Inspection has no input_path, or is already processing/completed"},
    },
)
async def run_inspection(
    inspection_id: str,
    service: InspectionServiceDep,
    pipeline: CVPipelineDep,
) -> InspectionResponse:
    """Trigger synchronous vision pipeline execution for an inspection."""
    try:
        inspection = await service.run_inspection(inspection_id, pipeline)
    except SHMBaseException as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc

    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found.",
        )
    return InspectionResponse.model_validate(inspection)
