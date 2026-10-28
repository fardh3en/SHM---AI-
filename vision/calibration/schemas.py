"""
Explicit domain schemas for image quality, calibration, crack measurements, and depth.
"""
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from backend.app.models.detection import DefectType


class ImageSuitabilityStatus(StrEnum):
    """Overall suitability of an image for reliable metric evaluation."""
    SUITABLE = "suitable"
    MARGINAL = "marginal"
    UNSUITABLE = "unsuitable"


class CalibrationStatus(StrEnum):
    """Explicit calibration status for optical inspection imagery."""
    CALIBRATED = "calibrated"
    UNCALIBRATED = "uncalibrated"
    REQUIRES_REVIEW = "requires_review"
    INVALID = "invalid"


class CalibrationMethod(StrEnum):
    """Method used to derive physical metric scale."""
    GROUND_SAMPLING_DISTANCE = "ground_sampling_distance"
    KNOWN_REFERENCE_MARKER = "known_reference_marker"
    MANUAL_SCALE = "manual_scale"
    NONE = "none"


class CalibrationValidationStatus(StrEnum):
    """Verification state of the calibration scale factor."""
    VERIFIED = "verified"
    PROVISIONAL = "provisional"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"


class DepthStatus(StrEnum):
    """Subsurface depth measurement status."""
    NOT_MEASURED = "not_measured"
    SENSOR_MEASURED = "sensor_measured"
    REQUIRES_SENSOR = "requires_sensor"


class MeasurementStatus(StrEnum):
    """Status of defect metric quantification."""
    MEASURED = "measured"
    ESTIMATED = "estimated"
    REQUIRES_CALIBRATION = "requires_calibration"
    NOT_MEASURED = "not_measured"
    INSUFFICIENT_IMAGE_QUALITY = "insufficient_image_quality"
    REQUIRES_REVIEW = "requires_review"


class ImageQualityAssessment(BaseModel):
    """
    Detailed image quality and measurement suitability indicators.
    Avoids presenting heuristics as calibrated probabilities.
    """
    width_px: int = Field(..., ge=1, description="Image width in pixels.")
    height_px: int = Field(..., ge=1, description="Image height in pixels.")
    format: str | None = Field(default=None, description="Image file format (e.g. JPEG, PNG).")
    image_id: str | None = Field(default=None, description="Filename or unique identifier of the image.")
    suitability_status: ImageSuitabilityStatus = Field(
        default=ImageSuitabilityStatus.SUITABLE,
        description="Overall measurement suitability."
    )
    blur_score: float | None = Field(
        default=None,
        description="Laplacian variance focus score (higher is sharper; < 100 suggests blur)."
    )
    exposure_status: str | None = Field(
        default=None,
        description="Exposure indicator ('underexposed', 'normal', 'overexposed')."
    )
    resolution_status: str | None = Field(
        default=None,
        description="Resolution assessment ('low' < 640px, 'adequate' 640-1920px, 'high' > 1920px)."
    )
    perspective_limitation: str | None = Field(
        default=None,
        description="Perspective assessment ('planar', 'oblique', 'severe_tilt')."
    )
    unsuitable_reasons: list[str] = Field(
        default_factory=list,
        description="Human-readable explanations when image is marginal or unsuitable."
    )


class CalibrationInfo(BaseModel):
    """
    Explicit calibration parameters.
    Platform never infers physical scale from arbitrary image dimensions.
    """
    status: CalibrationStatus = Field(
        default=CalibrationStatus.UNCALIBRATED,
        description="Explicit calibration status."
    )
    method: CalibrationMethod = Field(
        default=CalibrationMethod.NONE,
        description="Source methodology for metric scaling."
    )
    pixel_to_mm_ratio: float | None = Field(
        default=None,
        gt=0.0,
        description="Scale factor in millimeters per pixel (mm/px)."
    )
    reference_object: str | None = Field(
        default=None,
        description="Name or description of calibration fiducial/marker (e.g. 'standard 50mm disc', 'ruler')."
    )
    uncertainty_pct: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Estimated scaling uncertainty percentage (±%)."
    )
    source: str | None = Field(
        default=None,
        description="Source of calibration data (e.g. 'EXIF metadata', 'user_input', 'optical_target')."
    )
    timestamp_utc: str | None = Field(
        default=None,
        description="ISO 8601 UTC timestamp of calibration record."
    )
    validation_status: CalibrationValidationStatus = Field(
        default=CalibrationValidationStatus.UNVERIFIED,
        description="Validation review status of calibration data."
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Documented geometric or environmental limitations (e.g. 'Perspective distortion uncorrected')."
    )

    @classmethod
    def uncalibrated(cls, reasons: list[str] | None = None) -> "CalibrationInfo":
        """Factory for uncalibrated image context."""
        lims = reasons or [
            "No metric scale, fiducial marker, or Ground Sampling Distance (GSD) provided.",
            "Pixel dimensions cannot be converted to physical millimeters without calibration."
        ]
        return cls(
            status=CalibrationStatus.UNCALIBRATED,
            method=CalibrationMethod.NONE,
            pixel_to_mm_ratio=None,
            validation_status=CalibrationValidationStatus.UNVERIFIED,
            limitations=lims,
        )

    @classmethod
    def calibrated(
        cls,
        pixel_to_mm_ratio: float,
        method: CalibrationMethod = CalibrationMethod.MANUAL_SCALE,
        reference_object: str | None = None,
        uncertainty_pct: float | None = None,
        source: str | None = None,
    ) -> "CalibrationInfo":
        """Factory for validated metric calibration."""
        if pixel_to_mm_ratio <= 0.0:
            return cls(
                status=CalibrationStatus.INVALID,
                method=method,
                pixel_to_mm_ratio=None,
                validation_status=CalibrationValidationStatus.REJECTED,
                limitations=["Supplied pixel-to-millimeter ratio is non-positive or invalid."],
            )
        return cls(
            status=CalibrationStatus.CALIBRATED,
            method=method,
            pixel_to_mm_ratio=pixel_to_mm_ratio,
            reference_object=reference_object,
            uncertainty_pct=uncertainty_pct,
            source=source,
            validation_status=CalibrationValidationStatus.VERIFIED,
            limitations=[],
        )


class CrackDepthRecord(BaseModel):
    """
    Subsurface crack depth measurement interface.
    Ordinary 2D photographs cannot assess subsurface crack depth.
    """
    depth_status: DepthStatus = Field(
        default=DepthStatus.NOT_MEASURED,
        description="Status of depth measurement."
    )
    depth_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="Validated subsurface crack depth in millimeters (from sensor testing)."
    )
    uncertainty_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="Measurement uncertainty in millimeters (± mm)."
    )
    method: str | None = Field(
        default=None,
        description="Testing method (e.g. 'ultrasonic_pulse_velocity', 'impact_echo', 'core_drilling')."
    )
    provenance: str | None = Field(
        default=None,
        description="Sensor model, calibration record, or certified inspection reference."
    )
    notes: str = Field(
        default=(
            "Subsurface crack depth cannot be measured from 2D optical surface photography. "
            "Non-destructive testing (ultrasonic pulse velocity or impact-echo) is required to quantify depth."
        ),
        description="Engineering explanatory disclosure."
    )


class CrackMeasurement(BaseModel):
    """
    Comprehensive measurement record for an individual detected defect instance.
    Includes pixel geometry, physical dimensions (when calibrated), depth status, and provenance.
    """
    crack_id: str = Field(..., description="Unique reference identifier for this defect instance.")
    defect_type: DefectType = Field(..., description="Defect classification category.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score [0.0, 1.0].")
    bbox_px: list[float] = Field(..., min_length=4, max_length=4, description="Bounding box [x1, y1, x2, y2] in pixels.")
    vertical_extent_px: float = Field(..., ge=0.0, description="Vertical span in pixel space (y2 - y1).")

    # Centerline and morphological geometry in pixel units
    length_px: float | None = Field(default=None, description="Centerline path length in pixels.")
    width_px: float | None = Field(default=None, description="Average crack width in pixels along skeleton.")
    max_width_px: float | None = Field(default=None, description="Maximum local crack opening width in pixels.")
    orientation_deg: float | None = Field(default=None, description="Dominant angle (-90 to 90, 0 = horizontal).")
    area_px: float = Field(default=0.0, ge=0.0, description="Total defect area in square pixels.")

    # Calibrated physical dimensions (mm) — None if uncalibrated
    length_mm: float | None = Field(default=None, description="Physical centerline length in millimeters.")
    width_mm: float | None = Field(default=None, description="Average physical crack width in millimeters.")
    max_width_mm: float | None = Field(default=None, description="Maximum physical crack width in millimeters.")
    area_mm2: float | None = Field(default=None, description="Physical defect area in square millimeters.")

    # Depth & calibration provenance
    depth: CrackDepthRecord = Field(default_factory=CrackDepthRecord)
    measurement_status: MeasurementStatus = Field(
        default=MeasurementStatus.REQUIRES_CALIBRATION,
        description="Status of this measurement record."
    )
    measurement_method: str = Field(
        default="Morphological Skeletonization & L2 Distance Transform",
        description="Algorithm used to compute geometric dimensions."
    )
    uncertainty_px: float | None = Field(
        default=None,
        description="Estimated spatial discretization uncertainty in pixels (± px)."
    )
    unavailability_reasons: list[str] = Field(
        default_factory=list,
        description="Explicit explanations when physical metrics or depth are unavailable."
    )
    mask_polygon: dict[str, Any] | None = Field(
        default=None,
        description="GeoJSON-style polygon boundary."
    )
