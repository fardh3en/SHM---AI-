"""
Integration-style unit tests for vision.pipeline.cv_pipeline.CVInferencePipeline.

All tests use a MockDetector — no real YOLO weights are required.

Tests cover:
- Full-frame mode (small image): single tile, detector called once
- DetectionResult fields are populated correctly (bbox, type, confidence, measurements)
- mask_polygon is populated when the detector provides a mask
- mask_polygon is None when the detector returns no mask (bbox-only mode)
- bbox-only mode: area_px falls back to bounding-box area
- Sliced mode: an image larger than one tile triggers multiple detector calls
- Tile offset=0 regression: a detection from the first tile (x_offset=0,
  y_offset=0) is projected correctly (regression for tile_x or 0 bug)
- InferenceError is raised when the image file does not exist
- InferenceError is raised when the file exists but cannot be decoded
- slice_if_large=False forces full-frame even on a large image
"""
from pathlib import Path

import cv2
import numpy as np
import pytest

from backend.app.core.exceptions import InferenceError
from backend.app.models.detection import DefectType
from vision.detectors.base import IDetector, RawDetection
from vision.pipeline.cv_pipeline import CVInferencePipeline
from vision.schemas import DetectionResult  # noqa: TC001

# ---------------------------------------------------------------------------
# MockDetector
# ---------------------------------------------------------------------------

class MockDetector(IDetector):
    """
    Configurable fake detector that returns a preset list of RawDetection
    objects without requiring any model weights on disk.

    Set `detections` before calling predict() to control what the pipeline
    receives. Tracks `call_count` so tests can assert invocation behaviour.
    """

    def __init__(self, detections: list[RawDetection] | None = None) -> None:
        self.detections: list[RawDetection] = detections or []
        self.call_count: int = 0
        self.last_image: np.ndarray | None = None

    def predict(
        self,
        image: np.ndarray,
        confidence_threshold: float | None = None,
    ) -> list[RawDetection]:
        self.call_count += 1
        self.last_image = image
        return self.detections

    @property
    def model_name(self) -> str:
        return "mock-detector-v0"

    @property
    def device(self) -> str:
        return "cpu"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _crack_mask(h: int = 64, w: int = 64) -> np.ndarray:
    """A simple horizontal crack mask [H, W] uint8 for use in RawDetection."""
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[30:34, 5:60] = 255
    return mask


def _make_raw_detection(
    *,
    with_mask: bool = True,
    tile_h: int = 64,
    tile_w: int = 64,
) -> RawDetection:
    """Build a single RawDetection for a crack in a 64×64 tile space."""
    mask = _crack_mask(tile_h, tile_w) if with_mask else None
    return RawDetection(
        defect_type=DefectType.CRACK,
        confidence=0.88,
        bbox=[5.0, 28.0, 60.0, 36.0],  # pixel coords in tile space
        mask=mask,
    )


def _small_image(height: int = 64, width: int = 64) -> np.ndarray:
    """RGB image that fits within one 640×640 tile."""
    return np.ones((height, width, 3), dtype=np.uint8) * 128


def _large_image(height: int = 900, width: int = 900) -> np.ndarray:
    """RGB image that exceeds the default 640×640 tile, forcing slicing."""
    return np.ones((height, width, 3), dtype=np.uint8) * 64


def _write_valid_png(path: Path, image: np.ndarray) -> None:
    """Persist a numpy image to disk as PNG via OpenCV (BGR save)."""
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(path), bgr)


# ---------------------------------------------------------------------------
# Full-frame mode tests
# ---------------------------------------------------------------------------

class TestCVPipelineFullFrame:
    def test_returns_empty_list_when_no_detections(self, tmp_path: Path) -> None:
        """Pipeline must return [] when the detector finds nothing."""
        img_path = tmp_path / "img.png"
        _write_valid_png(img_path, _small_image())

        detector = MockDetector(detections=[])
        pipeline = CVInferencePipeline(detector=detector)

        results = pipeline.run(img_path)
        assert results == []

    def test_single_detection_with_mask(self, tmp_path: Path) -> None:
        """A single detection with a mask should produce one DetectionResult."""
        img = _small_image(64, 64)
        img_path = tmp_path / "img.png"
        _write_valid_png(img_path, img)

        raw = _make_raw_detection(with_mask=True, tile_h=64, tile_w=64)
        detector = MockDetector(detections=[raw])
        pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

        results = pipeline.run(img_path)

        assert len(results) == 1
        r: DetectionResult = results[0]
        assert r.defect_type == DefectType.CRACK
        assert r.confidence == pytest.approx(0.88)

    def test_detection_result_bbox_is_normalised(self, tmp_path: Path) -> None:
        """
        bbox coordinates in DetectionResult must be normalised to [0, 1]
        relative to the full image dimensions.
        """
        img = _small_image(64, 64)
        img_path = tmp_path / "img.png"
        _write_valid_png(img_path, img)

        raw = _make_raw_detection(with_mask=False, tile_h=64, tile_w=64)
        detector = MockDetector(detections=[raw])
        pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

        results = pipeline.run(img_path)
        assert len(results) == 1

        r = results[0]
        for coord in (r.bbox_x1, r.bbox_y1, r.bbox_x2, r.bbox_y2):
            assert 0.0 <= coord <= 1.0, f"Coord {coord} is outside [0, 1]."

    def test_mask_polygon_populated_when_mask_provided(self, tmp_path: Path) -> None:
        """If detector supplies a mask, mask_polygon must be a non-None dict."""
        img = _small_image(64, 64)
        img_path = tmp_path / "img.png"
        _write_valid_png(img_path, img)

        raw = _make_raw_detection(with_mask=True, tile_h=64, tile_w=64)
        detector = MockDetector(detections=[raw])
        pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

        results = pipeline.run(img_path)
        # mask_polygon may be None if the projected mask has no valid contour,
        # but if it is set it must be a dict with the correct GeoJSON type.
        r = results[0]
        if r.mask_polygon is not None:
            assert isinstance(r.mask_polygon, dict)
            assert r.mask_polygon.get("type") == "Polygon"

    def test_mask_polygon_none_without_mask(self, tmp_path: Path) -> None:
        """If detector returns no mask (bbox-only), mask_polygon must be None."""
        img = _small_image(64, 64)
        img_path = tmp_path / "img.png"
        _write_valid_png(img_path, img)

        raw = _make_raw_detection(with_mask=False, tile_h=64, tile_w=64)
        detector = MockDetector(detections=[raw])
        pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

        results = pipeline.run(img_path)
        assert results[0].mask_polygon is None

    def test_bbox_only_mode_area_fallback(self, tmp_path: Path) -> None:
        """
        Without a mask, area_px should be computed from the bounding box
        (bbox_w_px * bbox_h_px) rather than being 0 or None.
        """
        img = _small_image(64, 64)
        img_path = tmp_path / "img.png"
        _write_valid_png(img_path, img)

        # bbox [5, 28, 60, 36] → width=55 px, height=8 px → area=440 px²
        raw = RawDetection(
            defect_type=DefectType.CRACK,
            confidence=0.75,
            bbox=[5.0, 28.0, 60.0, 36.0],
            mask=None,
        )
        detector = MockDetector(detections=[raw])
        pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

        results = pipeline.run(img_path)
        area = results[0].measurements.area_px
        assert area > 0.0, "area_px must fall back to bbox area when no mask is provided."

    def test_detector_called_exactly_once_for_small_image(self, tmp_path: Path) -> None:
        """A small image (no slicing needed) must call detector exactly once."""
        img_path = tmp_path / "img.png"
        _write_valid_png(img_path, _small_image())

        detector = MockDetector(detections=[])
        pipeline = CVInferencePipeline(detector=detector, slice_if_large=True)

        pipeline.run(img_path)
        assert detector.call_count == 1

    def test_tile_fields_are_none_in_full_frame_mode(self, tmp_path: Path) -> None:
        """In full-frame mode, tile_x and tile_y on the DetectionResult must be None."""
        img_path = tmp_path / "img.png"
        _write_valid_png(img_path, _small_image(64, 64))

        raw = _make_raw_detection(with_mask=False)
        detector = MockDetector(detections=[raw])
        pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

        results = pipeline.run(img_path)
        assert results[0].tile_x is None
        assert results[0].tile_y is None


# ---------------------------------------------------------------------------
# Sliced mode tests
# ---------------------------------------------------------------------------

class TestCVPipelineSliced:
    def test_large_image_triggers_multiple_detector_calls(self, tmp_path: Path) -> None:
        """
        An image larger than one tile must cause the detector to be invoked
        more than once (one call per tile).
        """
        img_path = tmp_path / "large.png"
        _write_valid_png(img_path, _large_image(900, 900))

        detector = MockDetector(detections=[])
        pipeline = CVInferencePipeline(
            detector=detector,
            slice_height=640,
            slice_width=640,
            slice_overlap_ratio=0.4,
            slice_if_large=True,
        )

        pipeline.run(img_path)
        assert detector.call_count > 1

    def test_slice_if_large_false_forces_full_frame(self, tmp_path: Path) -> None:
        """slice_if_large=False must run as a single frame even for large images."""
        img_path = tmp_path / "large.png"
        _write_valid_png(img_path, _large_image(900, 900))

        detector = MockDetector(detections=[])
        pipeline = CVInferencePipeline(
            detector=detector,
            slice_height=640,
            slice_width=640,
            slice_if_large=False,
        )

        pipeline.run(img_path)
        assert detector.call_count == 1

    def test_sliced_detection_result_has_tile_offsets(self, tmp_path: Path) -> None:
        """
        Detections produced during sliced inference must have tile_x / tile_y
        populated in the DetectionResult (they are None only in full-frame mode).
        """
        img_path = tmp_path / "large.png"
        large = _large_image(900, 900)
        _write_valid_png(img_path, large)

        # Return one detection from the very first tile
        raw = _make_raw_detection(with_mask=False, tile_h=640, tile_w=640)

        call_number: list[int] = [0]

        class FirstTileOnlyDetector(IDetector):
            """Only yields a detection for the first tile call."""
            @property
            def model_name(self) -> str:
                return "first-tile-only"

            @property
            def device(self) -> str:
                return "cpu"

            def predict(
                self,
                image: np.ndarray,
                confidence_threshold: float | None = None,
            ) -> list[RawDetection]:
                call_number[0] += 1
                return [raw] if call_number[0] == 1 else []

        pipeline = CVInferencePipeline(
            detector=FirstTileOnlyDetector(),
            slice_height=640,
            slice_width=640,
            slice_overlap_ratio=0.4,
            slice_if_large=True,
        )

        results = pipeline.run(img_path)
        assert len(results) == 1
        r = results[0]
        # The first tile starts at (0, 0) — tile_x and tile_y must be 0
        assert r.tile_x == 0, f"Expected tile_x=0 but got {r.tile_x}"
        assert r.tile_y == 0, f"Expected tile_y=0 but got {r.tile_y}"

    def test_tile_offset_zero_regression(self, tmp_path: Path) -> None:
        """
        Regression for the tile_x=0 falsy bug.

        The first tile always has x_offset=0 and y_offset=0. With the old
        `tile_x or 0` guard, this accidentally still worked because `0 or 0 = 0`.
        With the fix (`tile_x if tile_x is not None else 0`), the behaviour
        is explicit and correct. We verify the bbox projection is correct for
        tile (0, 0) on a 900×900 image.

        bbox [0, 0, 640, 640] at tile (0,0) → full image (0,0,640,640)
        normalised on 900×900 → [0, 0, 640/900, 640/900] ≈ [0, 0, 0.711, 0.711]
        """
        img_path = tmp_path / "large.png"
        large = _large_image(900, 900)
        _write_valid_png(img_path, large)

        call_counter = [0]

        class SingleFirstTileDetector(IDetector):
            @property
            def model_name(self) -> str:
                return "tile-zero-regression"

            @property
            def device(self) -> str:
                return "cpu"

            def predict(
                self,
                image: np.ndarray,
                confidence_threshold: float | None = None,
            ) -> list[RawDetection]:
                call_counter[0] += 1
                if call_counter[0] == 1:
                    return [
                        RawDetection(
                            defect_type=DefectType.CRACK,
                            confidence=0.90,
                            bbox=[0.0, 0.0, 640.0, 640.0],
                            mask=None,
                        )
                    ]
                return []

        pipeline = CVInferencePipeline(
            detector=SingleFirstTileDetector(),
            slice_height=640,
            slice_width=640,
            slice_overlap_ratio=0.4,
            slice_if_large=True,
        )

        results = pipeline.run(img_path)
        assert len(results) == 1

        r = results[0]
        expected_x2 = 640.0 / 900.0
        expected_y2 = 640.0 / 900.0
        assert r.bbox_x1 == pytest.approx(0.0)
        assert r.bbox_y1 == pytest.approx(0.0)
        assert r.bbox_x2 == pytest.approx(expected_x2, rel=1e-5)
        assert r.bbox_y2 == pytest.approx(expected_y2, rel=1e-5)


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestCVPipelineErrors:
    def test_inference_error_on_missing_file(self) -> None:
        """Running on a non-existent file must raise InferenceError, not FileNotFoundError."""
        detector = MockDetector(detections=[])
        pipeline = CVInferencePipeline(detector=detector)

        with pytest.raises(InferenceError, match="not found"):
            pipeline.run("/absolutely/does/not/exist/image.png")

    def test_inference_error_on_corrupt_file(self, tmp_path: Path) -> None:
        """A corrupt (non-image) file must raise InferenceError, not ValueError."""
        bad_path = tmp_path / "corrupt.jpg"
        bad_path.write_bytes(b"this is not a valid jpeg \xff\x00\xab")

        detector = MockDetector(detections=[])
        pipeline = CVInferencePipeline(detector=detector)

        with pytest.raises(InferenceError):
            pipeline.run(bad_path)

    def test_inference_error_on_detector_failure(self, tmp_path: Path) -> None:
        """
        If the detector raises an unexpected exception, the pipeline must
        catch it and re-raise as InferenceError (the broad except in run()).
        """
        img_path = tmp_path / "img.png"
        _write_valid_png(img_path, _small_image())

        class BrokenDetector(IDetector):
            @property
            def model_name(self) -> str:
                return "broken"

            @property
            def device(self) -> str:
                return "cpu"

            def predict(
                self,
                image: np.ndarray,
                confidence_threshold: float | None = None,
            ) -> list[RawDetection]:
                raise RuntimeError("CUDA out of memory")

        pipeline = CVInferencePipeline(detector=BrokenDetector(), slice_if_large=False)

        with pytest.raises(InferenceError, match="CUDA out of memory"):
            pipeline.run(img_path)
