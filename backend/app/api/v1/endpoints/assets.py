"""
Asset CRUD API endpoints.

All business logic is delegated to AssetService via DI.
Endpoints only handle: request parsing, service invocation, and response mapping.
"""
from fastapi import APIRouter, HTTPException, Query, status

from backend.app.dependencies import AssetServiceDep
from backend.app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from backend.app.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.post(
    "/",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new structural asset",
    description=(
        "Creates a new monitored structural asset. "
        "The asset will have ACTIVE status by default. "
        "Inspections and health records can be created for it immediately."
    ),
)
async def create_asset(
    data: AssetCreate,
    service: AssetServiceDep,
) -> AssetResponse:
    """Create a new asset and return its full representation."""
    asset = await service.create_asset(data)
    return AssetResponse.model_validate(asset)


@router.get(
    "/",
    response_model=PaginatedResponse[AssetResponse],
    summary="List all assets",
    description="Returns a paginated list of all registered structural assets.",
)
async def list_assets(
    service: AssetServiceDep,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page."),
) -> PaginatedResponse[AssetResponse]:
    """Paginated asset list."""
    items, total = await service.list_assets(page=page, page_size=page_size)
    return PaginatedResponse[AssetResponse].build(
        items=[AssetResponse.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Get a single asset",
    description="Retrieve a structural asset by its UUID.",
    responses={404: {"description": "Asset not found"}},
)
async def get_asset(
    asset_id: str,
    service: AssetServiceDep,
) -> AssetResponse:
    """Fetch a single asset by ID."""
    asset = await service.get_asset(asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{asset_id}' not found.",
        )
    return AssetResponse.model_validate(asset)


@router.patch(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Update an asset",
    description=(
        "Partially update an asset's fields. "
        "Only the fields provided in the request body will be modified. "
        "Omitted fields retain their existing values."
    ),
    responses={404: {"description": "Asset not found"}},
)
async def update_asset(
    asset_id: str,
    data: AssetUpdate,
    service: AssetServiceDep,
) -> AssetResponse:
    """Partial update of an asset."""
    asset = await service.update_asset(asset_id, data)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{asset_id}' not found.",
        )
    return AssetResponse.model_validate(asset)


@router.delete(
    "/{asset_id}",
    response_model=MessageResponse,
    summary="Delete an asset",
    description=(
        "Permanently delete an asset and all associated records "
        "(inspections, detections, health records, degradation records). "
        "This action cannot be undone."
    ),
    responses={404: {"description": "Asset not found"}},
)
async def delete_asset(
    asset_id: str,
    service: AssetServiceDep,
) -> MessageResponse:
    """Delete an asset by ID (cascades to all linked records)."""
    deleted = await service.delete_asset(asset_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{asset_id}' not found.",
        )
    return MessageResponse(message=f"Asset '{asset_id}' deleted successfully.")
