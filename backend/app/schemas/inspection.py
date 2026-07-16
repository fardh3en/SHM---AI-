"""
Pydantic v2 schemas for Inspection API endpoints.
"""
from datetime import datetime

from pydantic import Field

from backend.app.models.inspection import InspectionSource, InspectionStatus
from backend.app.schemas.common import SHMBaseSchema


class InspectionCreate(SHMBaseSchema):
    """Request body for POST /inspections."""
    asset_id: str = Field(
        ...,
        description="UUID of the asset being inspected.",
    )
    source: InspectionSource = Field(
        default=InspectionSource.IMAGE,
        description="Origin of the input media.",
    )
    notes: str | None = Field(
        default=None,
        description="Optional inspector notes or context.",
    )


class InspectionUpdate(SHMBaseSchema):
    """
    Request body for PATCH /inspections/{id}.
    Typically used by the vision engine to populate results after processing.
    """
    status: InspectionStatus | None = None
    notes: str | None = None
    health_score: float | None = Field(default=None, ge=0.0, le=100.0)
    defect_count: int | None = Field(default=None, ge=0)
    processing_time_ms: float | None = Field(default=None, ge=0.0)
    error_message: str | None = None
    input_path: str | None = None


class InspectionResponse(SHMBaseSchema):
    """Full inspection representation returned by the API."""
    id: str
    asset_id: str
    status: InspectionStatus
    source: InspectionSource
    input_path: str | None
    notes: str | None
    defect_count: int
    health_score: float | None
    processing_time_ms: float | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
