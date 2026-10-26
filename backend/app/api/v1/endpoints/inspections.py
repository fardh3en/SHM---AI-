"""
Inspection API endpoints.

Manage the inspection lifecycle for structural assets, including triggering
the computer vision pipeline, querying detections, computing explainable
structural health assessments, and executing change-tracking comparisons.
"""
from fastapi import APIRouter, HTTPException, Query, status

from backend.app.core.exceptions import SHMBaseException, ValidationError
from backend.app.dependencies import AssessmentServiceDep, InspectionServiceDep
from backend.app.schemas.assessment import StructuralAssessmentResponse
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.comparison import InspectionComparisonResponse
from backend.app.schemas.detection import DetectionResponse
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
    "/compare",
    response_model=InspectionComparisonResponse,
    summary="Compare two inspections of the same asset",
    description=(
        "Compares base and target inspections belonging to the same asset. "
        "Evaluates common defect categories, newly observed categories, "
        "absent categories, score delta, and discloses engineering comparability limits."
    ),
    responses={
        400: {"description": "Validation error or asset mismatch"},
        404: {"description": "Inspection or asset not found"},
    },
)
async def compare_inspections(
    service: InspectionServiceDep,
    asset_id: str = Query(..., description="UUID of the asset owning both inspections"),
    base_id: str = Query(..., description="UUID of the earlier / reference inspection"),
    target_id: str = Query(..., description="UUID of the later / comparison inspection"),
) -> InspectionComparisonResponse:
    """Compare two inspections of an asset."""
    try:
        return await service.compare_inspections(
            asset_id=asset_id, base_id=base_id, target_id=target_id
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message if hasattr(exc, "message") else str(exc),
        ) from exc


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
        "Used by operators to attach evidence, add notes, or correct status."
    ),
    responses={
        400: {"description": "Validation error"},
        404: {"description": "Inspection not found"},
    },
)
async def update_inspection(
    inspection_id: str,
    data: InspectionUpdate,
    service: InspectionServiceDep,
) -> InspectionResponse:
    """Partial update of an inspection."""
    try:
        inspection = await service.update_inspection(inspection_id, data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message if hasattr(exc, "message") else str(exc),
        ) from exc
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
        "input_path, followed by automated structural health assessment. "
        "On completion, status is COMPLETED with defect_count and health_score populated."
    ),
    responses={
        404: {"description": "Inspection not found"},
        422: {"description": "Inspection has no input_path, or is already processing/completed"},
    },
)
async def run_inspection(
    inspection_id: str,
    service: InspectionServiceDep,
) -> InspectionResponse:
    """Trigger synchronous vision pipeline execution for an inspection."""
    try:
        inspection = await service.run_inspection(inspection_id)
    except SHMBaseException as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc

    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found.",
        )
    return InspectionResponse.model_validate(inspection)


@router.get(
    "/{inspection_id}/detections",
    response_model=list[DetectionResponse],
    summary="List defect detections for an inspection",
    description="Retrieve all defect detection instances recorded for this inspection.",
    responses={404: {"description": "Inspection not found"}},
)
async def get_inspection_detections(
    inspection_id: str,
    service: InspectionServiceDep,
) -> list[DetectionResponse]:
    """Retrieve all detections belonging to a given inspection."""
    detections = await service.get_detections(inspection_id)
    if detections is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found.",
        )
    return [DetectionResponse.model_validate(d) for d in detections]


@router.get(
    "/{inspection_id}/assessment",
    response_model=StructuralAssessmentResponse,
    summary="Get explainable structural health assessment",
    description=(
        "Returns the complete engineering assessment for an inspection, "
        "including deterministic health score, risk classification, "
        "failure mode inferences, data sources, assumptions, and limitations."
    ),
    responses={404: {"description": "Inspection not found"}},
)
async def get_inspection_assessment(
    inspection_id: str,
    assessment_service: AssessmentServiceDep,
) -> StructuralAssessmentResponse:
    """Retrieve or compute the explainable structural assessment."""
    result = await assessment_service.assess_inspection(inspection_id, force_reassess=False)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found.",
        )
    return result


@router.post(
    "/{inspection_id}/assess",
    response_model=StructuralAssessmentResponse,
    summary="Force re-evaluation of structural health assessment",
    description="Re-runs the deterministic intelligence engines against stored detections.",
    responses={404: {"description": "Inspection not found"}},
)
async def recalculate_inspection_assessment(
    inspection_id: str,
    assessment_service: AssessmentServiceDep,
) -> StructuralAssessmentResponse:
    """Re-run and update the structural assessment for an inspection."""
    result = await assessment_service.assess_inspection(inspection_id, force_reassess=True)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found.",
        )
    return result
