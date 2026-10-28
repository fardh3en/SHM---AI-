"""
Modular Defect Measurement Engine.

Consumes detector outputs, binary masks, and calibration/depth metadata to compute
strictly valid geometric metrics without fabricating real-world dimensions or depths.
"""
from pathlib import Path
from typing import Any
import cv2
import numpy as np

from backend.app.models.detection import DefectType
from vision.calibration.depth_interface import DepthMeasurementService
from vision.calibration.image_quality import ImageQualityAnalyzer
from vision.calibration.schemas import (
    CalibrationInfo,
    CalibrationStatus,
    CrackDepthRecord,
    CrackMeasurement,
    DepthStatus,
    ImageQualityAssessment,
    MeasurementStatus,
)
from vision.postprocessing.measurements import MeasurementService
from vision.postprocessing.polygon import MaskPolygonConverter
from vision.postprocessing.skeleton import Skeletonizer


class DefectMeasurementEngine:
    """
    Independent measurement service for defect geometry, calibration, and depth.
    Decoupled from detector forward passes.
    """

    def __init__(
        self,
        calibration: CalibrationInfo | None = None,
        depth_service: DepthMeasurementService | None = None,
    ) -> None:
        self._calibration = calibration or CalibrationInfo.uncalibrated()
        self._depth_service = depth_service or DepthMeasurementService()
        self._measurement_service = MeasurementService(
            pixel_to_mm_ratio=(
                self._calibration.pixel_to_mm_ratio
                if self._calibration.status == CalibrationStatus.CALIBRATED
                else None
            )
        )

    @property
    def calibration(self) -> CalibrationInfo:
        return self._calibration

    def measure_instance(
        self,
        crack_id: str,
        defect_type: DefectType,
        confidence: float,
        bbox_px: list[float],
        mask: np.ndarray | None,
        image_shape: tuple[int, int],
        depth_record: CrackDepthRecord | None = None,
    ) -> CrackMeasurement:
        """
        Quantify a single defect instance from its bounding box and instance mask.

        Args:
            crack_id: Reference string (e.g. 'crack_1').
            defect_type: Domain defect classification.
            confidence: Inference confidence score [0.0, 1.0].
            bbox_px: Pixel bounding box [x1, y1, x2, y2].
            mask: Full-image or cropped binary mask uint8 {0, 1} or {0, 255}.
            image_shape: (height, width) of the full source image.
            depth_record: Optional sensor-derived depth record.
        """
        img_h, img_w = image_shape
        x1, y1, x2, y2 = [float(v) for v in bbox_px]

        # Vertical extent in pixels is strictly the vertical span (y2 - y1) in image coordinates
        vertical_extent_px = max(0.0, y2 - y1)
        depth = depth_record or self._depth_service.get_default_optical_depth()

        reasons: list[str] = []

        # ── 1. Mask Validation & Extraction ───────────────────────────────────
        if mask is None or np.count_nonzero(mask) < 3:
            # Handle empty or sub-pixel masks
            if mask is None:
                reasons.append("Bounding box detection only; segmentation mask is not available for this defect.")
            else:
                reasons.append(
                    f"Segmentation mask has only {np.count_nonzero(mask)} active pixels (< 3 px threshold). "
                    "Dimensions withheld to prevent false geometric reporting."
                )

            # Box fallback for area only
            box_area = max(0.0, (x2 - x1) * (y2 - y1))
            return CrackMeasurement(
                crack_id=crack_id,
                defect_type=defect_type,
                confidence=confidence,
                bbox_px=[x1, y1, x2, y2],
                vertical_extent_px=vertical_extent_px,
                length_px=None,
                width_px=None,
                max_width_px=None,
                orientation_deg=None,
                area_px=box_area,
                length_mm=None,
                width_mm=None,
                max_width_mm=None,
                area_mm2=None,
                depth=depth,
                measurement_status=(
                    MeasurementStatus.ESTIMATED if mask is None else MeasurementStatus.INSUFFICIENT_IMAGE_QUALITY
                ),
                measurement_method="Bounding Box Envelope (Mask Unavailable)",
                uncertainty_px=round(max(x2 - x1, y2 - y1) * 0.1, 1),
                unavailability_reasons=reasons,
                mask_polygon=None,
            )

        # ── 2. Active Region Cropping for Memory & Performance ─────────────────
        # Ensure mask is in uint8 {0, 255}
        binary_full = (mask > 0).astype(np.uint8) * 255
        y_indices, x_indices = np.where(binary_full > 0)
        pad = 4
        crop_y1 = max(0, int(y_indices.min()) - pad)
        crop_y2 = min(img_h, int(y_indices.max()) + pad + 1)
        crop_x1 = max(0, int(x_indices.min()) - pad)
        crop_x2 = min(img_w, int(x_indices.max()) + pad + 1)

        crop_mask = binary_full[crop_y1:crop_y2, crop_x1:crop_x2]
        crop_skel = Skeletonizer.skeletonize_mask(crop_mask)

        # ── 3. Centerline & Morphological Metrics ─────────────────────────────
        meas = self._measurement_service.measure_defect(crop_mask, crop_skel)
        area_px = meas.area_px
        length_px = meas.length_px
        width_px = meas.width_px
        max_width_px = meas.max_width_px
        orientation_deg = meas.orientation_deg

        # Polygon Extraction with offset re-projection
        crop_poly = MaskPolygonConverter.mask_to_polygon(crop_mask)
        if crop_poly and "coordinates" in crop_poly:
            mask_polygon = {
                "type": "Polygon",
                "coordinates": [
                    [[pt[0] + crop_x1, pt[1] + crop_y1] for pt in ring]
                    for ring in crop_poly["coordinates"]
                ],
            }
        else:
            mask_polygon = crop_poly

        # ── 4. Metric Calibration Conversion ──────────────────────────────────
        is_calibrated = (
            self._calibration.status == CalibrationStatus.CALIBRATED
            and self._calibration.pixel_to_mm_ratio is not None
            and self._calibration.pixel_to_mm_ratio > 0
        )

        length_mm = None
        width_mm = None
        max_width_mm = None
        area_mm2 = None

        if is_calibrated:
            ratio = self._calibration.pixel_to_mm_ratio
            if length_px is not None:
                length_mm = round(length_px * ratio, 2)
            if width_px is not None:
                width_mm = round(width_px * ratio, 2)
            if max_width_px is not None:
                max_width_mm = round(max_width_px * ratio, 2)
            area_mm2 = round(area_px * (ratio ** 2), 1)
            meas_status = MeasurementStatus.MEASURED
        else:
            meas_status = MeasurementStatus.REQUIRES_CALIBRATION
            reasons.append(
                "Image is uncalibrated. Physical measurements in millimeters are withheld until a valid reference scale "
                "or Ground Sampling Distance (GSD) is provided."
            )

        # Disclose depth limitation
        if depth.depth_status == DepthStatus.NOT_MEASURED:
            reasons.append("Subsurface crack depth not measured; 2D photography records surface visual damage only.")

        return CrackMeasurement(
            crack_id=crack_id,
            defect_type=defect_type,
            confidence=confidence,
            bbox_px=[x1, y1, x2, y2],
            vertical_extent_px=round(vertical_extent_px, 1),
            length_px=round(length_px, 1) if length_px is not None else None,
            width_px=round(width_px, 2) if width_px is not None else None,
            max_width_px=round(max_width_px, 2) if max_width_px is not None else None,
            orientation_deg=round(orientation_deg, 1) if orientation_deg is not None else None,
            area_px=round(area_px, 1),
            length_mm=length_mm,
            width_mm=width_mm,
            max_width_mm=max_width_mm,
            area_mm2=area_mm2,
            depth=depth,
            measurement_status=meas_status,
            measurement_method="Centerline Skeletonization & L2 Distance Transform",
            uncertainty_px=1.5,
            unavailability_reasons=reasons,
            mask_polygon=mask_polygon,
        )
