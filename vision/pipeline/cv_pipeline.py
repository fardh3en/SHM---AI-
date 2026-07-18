"""
Computer Vision Inference Pipeline.

Orchestrates the full defect-detection flow for a single image:

    ImageLoader -> ImageSlicer -> IDetector -> coordinate projection
        -> Skeletonizer -> MeasurementService -> MaskPolygonConverter
        -> DetectionResult objects

Design notes:
- Runs synchronously (per Phase 2 scope decision — no background workers yet).
- Cross-tile deduplication is intentionally NOT performed here. Sliced inference
  can yield the same physical defect detected in multiple overlapping tiles.
  True deduplication (IoU-based merge across tiles) is deferred; for now each
  tile detection is projected and measured independently. This is a known,
  documented limitation — see class docstring below.
- Mask fusion (MaskFusionService) is exposed for callers who want to merge a
  known set of overlapping masks for a single physical defect (e.g. Phase 3
  aggregation), but is not automatically applied across arbitrary tile
  detections here, since that requires defect-identity matching first.
"""
import logging
import time
from pathlib import Path

import numpy as np

from backend.app.core.exceptions import InferenceError
from vision.detectors.base import IDetector, RawDetection
from vision.pipeline.base import IInferencePipeline
from vision.postprocessing.measurements import MeasurementService
from vision.postprocessing.polygon import MaskPolygonConverter
from vision.postprocessing.skeleton import Skeletonizer
from vision.preprocessing.loader import ImageLoader
from vision.preprocessing.slicing import ImageSlicer
from vision.schemas import DetectionResult, MeasurementResult

logger = logging.getLogger(__name__)


class CVInferencePipeline(IInferencePipeline):
    """
    Default computer vision inference pipeline implementation.

    KNOWN LIMITATION (documented, not a bug): when slicing is enabled and a
    physical defect spans multiple overlapping tiles, it may be reported as
    multiple separate DetectionResult entries rather than one deduplicated
    detection. Proper cross-tile deduplication requires IoU-based instance
    matching and is planned for a later iteration once real-world detection
    density is understood. Disable slicing (slice_if_large=False) or keep
    images at or below one tile's size to avoid this in the meantime.
    """

    def __init__(
        self,
        detector: IDetector,
        slice_height: int = 640,
        slice_width: int = 640,
        slice_overlap_ratio: float = 0.4,
        pixel_to_mm_ratio: float | None = None,
        slice_if_large: bool = True,
    ) -> None:
        """
        Args:
            detector: Concrete IDetector implementation (e.g. YOLO11Detector).
            slice_height: Tile height for sliced inference.
            slice_width: Tile width for sliced inference.
            slice_overlap_ratio: Overlap ratio between adjacent tiles.
            pixel_to_mm_ratio: Optional calibration ratio (mm per pixel) applied
                to all measurements produced by this pipeline run.
            slice_if_large: If True, images larger than one tile are sliced.
                If False, the full image is always run as a single frame
                (simpler, but may miss small defects in very large images).
        """
        self._detector = detector
        self._slicer = ImageSlicer(
            slice_height=slice_height,
            slice_width=slice_width,
            overlap_ratio=slice_overlap_ratio,
        )
        self._measurement_service = MeasurementService(pixel_to_mm_ratio=pixel_to_mm_ratio)
        self._slice_height = slice_height
        self._slice_width = slice_width
        self._slice_if_large = slice_if_large

    def run(self, image_path: str | Path) -> list[DetectionResult]:
        """
        Run the full inference pipeline on a single image file.

        See class docstring for the cross-tile deduplication limitation.
        """
        start_time = time.perf_counter()
        path = Path(image_path)

        try:
            image = ImageLoader.load_image(path)
        except FileNotFoundError as exc:
            raise InferenceError(f"Image file not found: {path}") from exc
        except ValueError as exc:
            raise InferenceError(f"Image file could not be decoded: {path}") from exc

        h_img, w_img = image.shape[:2]
        needs_slicing = self._slice_if_large and (
            h_img > self._slice_height or w_img > self._slice_width
        )

        try:
            if needs_slicing:
                results = self._run_sliced(image, w_img, h_img)
            else:
                results = self._run_full_frame(image, w_img, h_img)
        except InferenceError:
            raise
        except Exception as exc:  # noqa: BLE001 — convert any unexpected failure
            raise InferenceError(
                f"Vision pipeline failed while processing '{path.name}': {exc}"
            ) from exc

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Pipeline completed for {path.name}: "
            f"{len(results)} detection(s) in {elapsed_ms:.1f}ms "
            f"(sliced={needs_slicing})"
        )
        return results

    def _run_full_frame(
        self, image: np.ndarray, img_width: int, img_height: int
    ) -> list[DetectionResult]:
        """Run inference on the whole image as a single frame (no tiling)."""
        raw_detections = self._detector.predict(image)
        return [
            self._build_detection_result(
                raw, tile_x=None, tile_y=None, img_width=img_width, img_height=img_height
            )
            for raw in raw_detections
        ]

    def _run_sliced(
        self, image: np.ndarray, img_width: int, img_height: int
    ) -> list[DetectionResult]:
        """Run inference tile-by-tile and project results back to full-image space."""
        results: list[DetectionResult] = []

        for tile in self._slicer.slice_image(image):
            raw_detections = self._detector.predict(tile.image)

            for raw in raw_detections:
                results.append(
                    self._build_detection_result(
                        raw,
                        tile_x=tile.x_offset,
                        tile_y=tile.y_offset,
                        img_width=img_width,
                        img_height=img_height,
                    )
                )

        return results

    def _build_detection_result(
        self,
        raw: RawDetection,
        tile_x: int | None,
        tile_y: int | None,
        img_width: int,
        img_height: int,
    ) -> DetectionResult:
        """
        Convert a single RawDetection (tile or full-frame space) into a fully
        measured, normalised DetectionResult in full-image coordinate space.
        """
        x_off = tile_x if tile_x is not None else 0
        y_off = tile_y if tile_y is not None else 0

        # ── Project bounding box to normalised full-image coordinates ────────
        bbox_norm = ImageSlicer.project_bbox(
            raw.bbox, x_off, y_off, img_width, img_height
        )

        # ── Project mask to full-image space and measure ─────────────────────
        length_px = width_px = max_width_px = orientation_deg = None
        mask_polygon = None

        if raw.mask is not None:
            full_mask = ImageSlicer.project_mask(
                raw.mask, x_off, y_off, img_width, img_height
            )
            skeleton = Skeletonizer.skeletonize_mask(full_mask)
            measurement = self._measurement_service.measure_defect(full_mask, skeleton)

            area_px = measurement.area_px
            length_px = measurement.length_px
            width_px = measurement.width_px
            max_width_px = measurement.max_width_px
            orientation_deg = measurement.orientation_deg
            mask_polygon = MaskPolygonConverter.mask_to_polygon(full_mask)
        else:
            # No mask available (detector ran in bbox-only mode) — fall back
            # to bounding-box area in pixel space so area_px is never lost.
            bbox_w_px = (bbox_norm[2] - bbox_norm[0]) * img_width
            bbox_h_px = (bbox_norm[3] - bbox_norm[1]) * img_height
            area_px = max(0.0, bbox_w_px) * max(0.0, bbox_h_px)

        final_measurement = MeasurementResult.create_calibrated(
            area_px=area_px,
            length_px=length_px,
            width_px=width_px,
            max_width_px=max_width_px,
            orientation_deg=orientation_deg,
            pixel_to_mm_ratio=self._measurement_service.pixel_to_mm_ratio,
        )

        return DetectionResult(
            defect_type=raw.defect_type,
            confidence=raw.confidence,
            bbox_x1=bbox_norm[0],
            bbox_y1=bbox_norm[1],
            bbox_x2=bbox_norm[2],
            bbox_y2=bbox_norm[3],
            tile_x=tile_x,
            tile_y=tile_y,
            measurements=final_measurement,
            mask_polygon=mask_polygon,
        )
