"""
Standardised Pydantic schemas for the Computer Vision Engine.
"""
from typing import Any

from pydantic import BaseModel, Field

from backend.app.models.detection import DefectType


class MeasurementResult(BaseModel):
    """
    Standardised measurement metrics for a single detected defect.
    
    Supports calibration from pixel space to real-world physical units (mm/mm²).
    If no calibration ratio is provided, real-world fields default to None.
    """
    # ── Pixel space measurements ──────────────────────────────────────────────
    area_px: float = Field(..., description="Total defect area in square pixels.")
    length_px: float | None = Field(default=None, description="Centerline length in pixels.")
    width_px: float | None = Field(default=None, description="Average thickness/width in pixels.")
    max_width_px: float | None = Field(default=None, description="Maximum local width in pixels.")
    vertical_extent_px: float | None = Field(default=None, description="Vertical span in pixels (y2 - y1).")
    orientation_deg: float | None = Field(
        default=None, 
        description="Dominant angle in degrees (-90 to 90, 0 = horizontal)."
    )

    # ── Calibration metadata ──────────────────────────────────────────────────
    pixel_to_mm_ratio: float | None = Field(
        default=None, 
        description="Scaling factor: physical dimension of one pixel in mm (mm/px)."
    )
    calibration_status: str = Field(
        default="uncalibrated",
        description="Calibration status: 'calibrated', 'uncalibrated', 'requires_review', 'invalid'."
    )
    measurement_status: str = Field(
        default="requires_calibration",
        description="Measurement status: 'measured', 'estimated', 'requires_calibration', etc."
    )
    unavailability_reasons: list[str] = Field(
        default_factory=list,
        description="Explanations when physical measurements or depth are unavailable."
    )

    # ── Physical space measurements (calculated if ratio is present) ──────────
    area_mm2: float | None = Field(default=None, description="Physical area in mm².")
    length_mm: float | None = Field(default=None, description="Physical length in mm.")
    width_mm: float | None = Field(default=None, description="Average physical width in mm.")
    max_width_mm: float | None = Field(default=None, description="Maximum physical width in mm.")

    @classmethod
    def create_calibrated(
        cls,
        area_px: float,
        length_px: float | None = None,
        width_px: float | None = None,
        max_width_px: float | None = None,
        vertical_extent_px: float | None = None,
        orientation_deg: float | None = None,
        pixel_to_mm_ratio: float | None = None,
        calibration_status: str | None = None,
        measurement_status: str | None = None,
        unavailability_reasons: list[str] | None = None,
    ) -> "MeasurementResult":
        """
        Factory method to instantiate measurements, automatically calculating
        physical units if a calibration ratio (mm/px) is supplied.
        """
        area_mm2 = None
        length_mm = None
        width_mm = None
        max_width_mm = None
        reasons = list(unavailability_reasons or [])

        if pixel_to_mm_ratio is not None and pixel_to_mm_ratio > 0:
            cal_status = calibration_status or "calibrated"
            meas_status = measurement_status or "measured"
            # Area scales quadratically: mm² = px² * (mm/px)²
            area_mm2 = area_px * (pixel_to_mm_ratio ** 2)
            if length_px is not None:
                length_mm = length_px * pixel_to_mm_ratio
            if width_px is not None:
                width_mm = width_px * pixel_to_mm_ratio
            if max_width_px is not None:
                max_width_mm = max_width_px * pixel_to_mm_ratio
        else:
            cal_status = calibration_status or "uncalibrated"
            meas_status = measurement_status or "requires_calibration"
            if not reasons:
                reasons.append("Uncalibrated photographic evidence. Known reference scale or GSD required for physical millimeters.")

        return cls(
            area_px=area_px,
            length_px=length_px,
            width_px=width_px,
            max_width_px=max_width_px,
            vertical_extent_px=vertical_extent_px,
            orientation_deg=orientation_deg,
            pixel_to_mm_ratio=pixel_to_mm_ratio,
            calibration_status=cal_status,
            measurement_status=meas_status,
            unavailability_reasons=reasons,
            area_mm2=area_mm2,
            length_mm=length_mm,
            width_mm=width_mm,
            max_width_mm=max_width_mm,
        )


class DetectionResult(BaseModel):
    """
    Standardised vision output representing a single detected defect instance.
    Parsed from raw model results and post-processed by the measurement engine.
    """
    defect_type: DefectType = Field(..., description="Category of the defect.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Inference confidence score.")
    
    # Bounding box coordinates normalized [0, 1] relative to the source image
    bbox_x1: float
    bbox_y1: float
    bbox_x2: float
    bbox_y2: float

    # Sliced inference metadata
    tile_x: int | None = Field(default=None, description="X offset of crop window if sliced.")
    tile_y: int | None = Field(default=None, description="Y offset of crop window if sliced.")

    # Measurements
    measurements: MeasurementResult = Field(..., description="Dimensional metrics of the defect.")

    # Segmentation mask stored as a polygon (list of [x, y] coordinates)
    mask_polygon: dict[str, Any] | None = Field(
        default=None, 
        description=(
            "GeoJSON-style polygon format: "
            "{'type': 'Polygon', 'coordinates': [[x, y], ...]}."
        )
    )

    # Image dimensions and model metadata
    image_width: int | None = Field(default=None, description="Source image width in pixels.")
    image_height: int | None = Field(default=None, description="Source image height in pixels.")
    model_name: str | None = Field(default=None, description="Model identifier used for inference.")
    class_id: int | None = Field(default=None, description="Raw model class ID index.")

    # Extended calibration and depth provenance
    crack_id: str | None = Field(default=None, description="Per-crack reference identifier.")
    vertical_extent_px: float | None = Field(default=None, description="Vertical span in pixels (y2 - y1).")
    depth_status: str = Field(default="not_measured", description="Subsurface depth measurement status.")
    depth_mm: float | None = Field(default=None, description="Calibrated sensor depth in mm, if available.")
    quality_assessment: dict[str, Any] | None = Field(default=None, description="Image quality metrics.")
    calibration_info: dict[str, Any] | None = Field(default=None, description="Calibration parameters.")
