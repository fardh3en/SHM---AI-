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
        logger.info(f"[Vision Pipeline] Starting pipeline for image: {path.name} ({path})")

        try:
            # In full-frame mode, constrain image dimensions to 1280px to prevent
            # out-of-memory crashes on constrained containers (Render Free 512MB RAM).
            # In slicing mode, keep native resolution for tile generation.
            max_dim = 1280 if not self._slice_if_large else None
            image = ImageLoader.load_image(path, max_dimension=max_dim)
        except FileNotFoundError as exc:
            raise InferenceError(f"Image file not found: {path}") from exc
        except ValueError as exc:
            raise InferenceError(f"Image file could not be decoded: {path}") from exc

        load_ms = (time.perf_counter() - start_time) * 1000
        h_img, w_img = image.shape[:2]
        needs_slicing = self._slice_if_large and (
            h_img > self._slice_height or w_img > self._slice_width
        )
        logger.info(
            f"[Vision Pipeline] Image ready: {path.name} ({w_img}x{h_img} px, loaded in {load_ms:.1f}ms). "
            f"Slicing policy: needs_slicing={needs_slicing} (slice_if_large={self._slice_if_large}, "
            f"tile_bounds={self._slice_width}x{self._slice_height})"
        )

        try:
            if needs_slicing:
                results = self._run_sliced(image, w_img, h_img)
            else:
                results = self._run_full_frame(image, w_img, h_img)
        except InferenceError:
            raise
        except Exception as exc:  # noqa: BLE001 — convert any unexpected failure
            logger.exception(f"[Vision Pipeline] Unhandled exception processing '{path.name}': {exc}")
            raise InferenceError(
                f"Vision pipeline failed while processing '{path.name}': {exc}"
            ) from exc

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"[Vision Pipeline] Completed for {path.name}: "
            f"{len(results)} detection(s) extracted in {elapsed_ms:.1f}ms "
            f"(sliced={needs_slicing})"
        )
        return results

    def _run_full_frame(
        self, image: np.ndarray, img_width: int, img_height: int
    ) -> list[DetectionResult]:
        """Run inference on the whole image as a single frame (no tiling)."""
        t0 = time.perf_counter()
        logger.info(f"[Vision Pipeline: Full-Frame] Invoking detector on full {img_width}x{img_height} frame...")
        raw_detections = self._detector.predict(image)
        predict_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            f"[Vision Pipeline: Full-Frame] Detector returned {len(raw_detections)} raw detection(s) in {predict_ms:.1f}ms. "
            "Extracting morphological measurements and polygons..."
        )
        t_measure = time.perf_counter()
        built = [
            self._build_detection_result(
                raw, tile_x=None, tile_y=None, img_width=img_width, img_height=img_height
            )
            for raw in raw_detections
        ]
        measure_ms = (time.perf_counter() - t_measure) * 1000
        logger.info(f"[Vision Pipeline: Full-Frame] Measurements extracted in {measure_ms:.1f}ms")
        return built

    def _run_sliced(
        self, image: np.ndarray, img_width: int, img_height: int
    ) -> list[DetectionResult]:
        """Run inference tile-by-tile and project results back to full-image space."""
        tiles = list(self._slicer.slice_image(image))
        total_tiles = len(tiles)
        logger.info(
            f"[Vision Pipeline: Sliced] Slicing generated {total_tiles} tile(s) "
            f"({self._slice_width}x{self._slice_height}, overlap={self._slicer.overlap_ratio}). "
            "Processing sequentially..."
        )
        results: list[DetectionResult] = []

        for idx, tile in enumerate(tiles):
            t_tile = time.perf_counter()
            logger.info(
                f"[Vision Pipeline: Sliced] [Tile {idx + 1}/{total_tiles}] "
                f"offset=({tile.x_offset}, {tile.y_offset}), shape={tile.image.shape} starting predict..."
            )
            raw_detections = self._detector.predict(tile.image)
            tile_predict_ms = (time.perf_counter() - t_tile) * 1000
            logger.info(
                f"[Vision Pipeline: Sliced] [Tile {idx + 1}/{total_tiles}] "
                f"predicted in {tile_predict_ms:.1f}ms: found {len(raw_detections)} detection(s)"
            )

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

        logger.info(
            f"[Vision Pipeline: Sliced] Completed all {total_tiles} tile(s). "
            f"Total raw detections accumulated: {len(results)}"
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
            y_idx, x_idx = np.where(full_mask > 0)
            if len(y_idx) > 0:
                # Crop to active bounding box with padding to minimize memory consumption during morphology
                pad = 4
                y1 = max(0, int(y_idx.min()) - pad)
                y2 = min(img_height, int(y_idx.max()) + pad + 1)
                x1 = max(0, int(x_idx.min()) - pad)
                x2 = min(img_width, int(x_idx.max()) + pad + 1)

                crop_mask = full_mask[y1:y2, x1:x2]
                crop_skel = Skeletonizer.skeletonize_mask(crop_mask)
                measurement = self._measurement_service.measure_defect(crop_mask, crop_skel)

                area_px = measurement.area_px
                length_px = measurement.length_px
                width_px = measurement.width_px
                max_width_px = measurement.max_width_px
                orientation_deg = measurement.orientation_deg

                crop_poly = MaskPolygonConverter.mask_to_polygon(crop_mask)
                if crop_poly and "coordinates" in crop_poly:
                    mask_polygon = {
                        "type": "Polygon",
                        "coordinates": [
                            [[pt[0] + x1, pt[1] + y1] for pt in ring]
                            for ring in crop_poly["coordinates"]
                        ],
                    }
                else:
                    mask_polygon = crop_poly
            else:
                area_px = 0.0
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
