"""
Pydantic v2 schemas for Detection API endpoints.
"""
from datetime import datetime
from typing import Any

from pydantic import Field

from backend.app.models.detection import DefectType
from backend.app.schemas.common import SHMBaseSchema


class DetectionResponse(SHMBaseSchema):
    """Full representation of a single defect detection instance."""

    id: str
    inspection_id: str
    defect_type: DefectType
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score [0.0, 1.0].")
    bbox_x1: float = Field(..., description="Normalized bounding box x1 [0.0, 1.0].")
    bbox_y1: float = Field(..., description="Normalized bounding box y1 [0.0, 1.0].")
    bbox_x2: float = Field(..., description="Normalized bounding box x2 [0.0, 1.0].")
    bbox_y2: float = Field(..., description="Normalized bounding box y2 [0.0, 1.0].")

    # Pixel-space metrics
    area_px: float | None = Field(default=None, description="Defect area in pixels².")
    length_px: float | None = Field(default=None, description="Crack skeleton length in pixels.")
    width_px: float | None = Field(default=None, description="Average crack width in pixels.")
    max_width_px: float | None = Field(default=None, description="Maximum crack opening width in pixels.")
    vertical_extent_px: float | None = Field(default=None, description="Vertical span in pixels (y2 - y1).")
    orientation_deg: float | None = Field(default=None, description="Dominant crack orientation in degrees.")

    # Calibrated physical metrics (mm) — None if uncalibrated
    length_mm: float | None = Field(default=None, description="Calibrated centerline length in mm.")
    width_mm: float | None = Field(default=None, description="Calibrated average crack width in mm.")
    max_width_mm: float | None = Field(default=None, description="Calibrated maximum crack width in mm.")
    area_mm2: float | None = Field(default=None, description="Calibrated defect area in mm².")

    # Calibration & Depth provenance
    calibration_status: str = Field(default="uncalibrated", description="Calibration state ('calibrated', 'uncalibrated').")
    measurement_status: str = Field(default="requires_calibration", description="Measurement qualification state.")
    depth_status: str = Field(default="not_measured", description="Subsurface depth status ('not_measured', 'sensor_measured').")
    depth_mm: float | None = Field(default=None, description="Subsurface depth in mm from validated sensor testing.")
    unavailability_reasons: list[str] = Field(default_factory=list, description="Reasons when physical metrics or depth are unavailable.")

    # Provenance & polygon
    tile_x: int | None = Field(default=None, description="X offset of source tile in sliced inference.")
    tile_y: int | None = Field(default=None, description="Y offset of source tile in sliced inference.")
    source_image: str | None = Field(default=None, description="Path to source image tile.")
    mask_polygon: dict[str, Any] | None = Field(default=None, description="GeoJSON-style segmentation polygon.")
    created_at: datetime
    updated_at: datetime
