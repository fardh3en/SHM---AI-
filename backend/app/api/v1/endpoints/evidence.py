"""
Asset evidence API endpoints.
"""
import logging
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.app.config import get_settings
from backend.app.core.exceptions import SHMBaseException
from backend.app.dependencies import EvidenceServiceDep
from backend.app.models.asset_evidence import EvidenceClassification
from backend.app.schemas.asset_evidence import (
    AssetEvidenceCreate,
    AssetEvidenceResponse,
    EvidenceUploadResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Evidence"])


@router.post(
    "/evidence/upload",
    response_model=EvidenceUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload inspection evidence image",
    description=(
        "Accepts multipart/form-data image bytes, validates file integrity, "
        "persists to the server uploads repository, and optionally links to an asset."
    ),
    responses={
        400: {"description": "Invalid file format, empty file, or path traversal"},
        413: {"description": "File exceeds 25 MB limit"},
    },
)
async def upload_evidence(
    file: UploadFile = File(..., description="Inspection image file (JPEG, PNG, WebP, TIFF)."),
    asset_id: str | None = Form(default=None, description="Optional associated asset UUID."),
    caption: str | None = Form(default=None, description="Optional caption or note."),
    classification: EvidenceClassification = Form(
        default=EvidenceClassification.VERIFIED_STRUCTURE,
        description="Evidence classification.",
    ),
    service: EvidenceServiceDep = None,
) -> EvidenceUploadResponse:
    """Upload an inspection evidence image file directly."""
    try:
        file_path, filename, size_bytes, record = await service.upload_evidence_file(
            file=file,
            asset_id=asset_id,
            caption=caption,
            classification=classification,
        )
    except SHMBaseException as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc
    except Exception as exc:
        logger.exception(f"Unexpected error in evidence upload: {exc}")
        detail_msg = f"Evidence upload failed: {str(exc)}" if settings.DEBUG else "Failed to persist evidence image."
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail_msg) from exc

    return EvidenceUploadResponse(
        id=record.id if record else None,
        asset_id=asset_id if record else None,
        filename=filename,
        original_filename=file.filename or filename,
        file_path=file_path,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
    )


@router.post(
    "/assets/{asset_id}/evidence/upload",
    response_model=EvidenceUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload evidence photo directly for a specific asset",
    description="Uploads visual media and links it to the specified structural asset.",
    responses={
        400: {"description": "Invalid file format or empty file"},
        404: {"description": "Asset not found"},
    },
)
async def upload_asset_evidence(
    asset_id: str,
    file: UploadFile = File(..., description="Inspection image file (JPEG, PNG, WebP, TIFF)."),
    caption: str | None = Form(default=None, description="Optional caption."),
    classification: EvidenceClassification = Form(
        default=EvidenceClassification.VERIFIED_STRUCTURE,
    ),
    service: EvidenceServiceDep = None,
) -> EvidenceUploadResponse:
    """Upload and attach an evidence image to a specific asset."""
    asset = await service.get_asset(asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{asset_id}' not found.",
        )

    try:
        file_path, filename, size_bytes, record = await service.upload_evidence_file(
            file=file,
            asset_id=asset_id,
            caption=caption,
            classification=classification,
        )
    except SHMBaseException as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc
    except Exception as exc:
        logger.exception(f"Unexpected error in evidence upload: {exc}")
        detail_msg = f"Evidence upload failed: {str(exc)}" if settings.DEBUG else "Failed to persist evidence image."
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail_msg) from exc

    return EvidenceUploadResponse(
        id=record.id if record else None,
        asset_id=asset_id,
        filename=filename,
        original_filename=file.filename or filename,
        file_path=file_path,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
    )


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
