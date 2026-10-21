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
    area_px: float | None = Field(default=None, description="Defect area in pixels².")
    length_px: float | None = Field(default=None, description="Crack skeleton length in pixels.")
    width_px: float | None = Field(default=None, description="Average crack width in pixels.")
    orientation_deg: float | None = Field(default=None, description="Dominant crack orientation in degrees.")
    tile_x: int | None = Field(default=None, description="X offset of source tile in sliced inference.")
    tile_y: int | None = Field(default=None, description="Y offset of source tile in sliced inference.")
    source_image: str | None = Field(default=None, description="Path to source image tile.")
    mask_polygon: dict[str, Any] | None = Field(default=None, description="GeoJSON-style segmentation polygon.")
    created_at: datetime
    updated_at: datetime
