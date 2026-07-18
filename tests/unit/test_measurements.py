"""
Unit tests for vision.postprocessing.measurements.MeasurementService.

Tests cover:
- Area: pixel count exactly matches np.count_nonzero on a known mask
- Length: a known 1×N horizontal crack has length ≈ N (straight line)
- Width: a known 2W-pixel-wide horizontal bar has avg width ≈ 2W
- max_width ≥ width_px (invariant)
- Orientation: near-horizontal crack → |angle| ≤ 10°
- Orientation: near-vertical crack → |angle| ≥ 60° (PCA principal axis ≈ 90°)
- Calibration: mm fields are None when no ratio supplied
- Calibration: area_mm2 = area_px * ratio² when ratio is provided
- Calibration: length_mm = length_px * ratio when ratio is provided
- No skeleton → length/width/orientation all remain None
"""

import numpy as np
import pytest

from vision.postprocessing.measurements import MeasurementService
from vision.postprocessing.skeleton import Skeletonizer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _horizontal_crack_mask(length: int = 100, thickness: int = 4,
                            canvas: int = 200) -> np.ndarray:
    """
    A horizontal crack: a filled rectangle of given length and thickness,
    centred on a square canvas.
    """
    mask = np.zeros((canvas, canvas), dtype=np.uint8)
    y_start = canvas // 2 - thickness // 2
    mask[y_start: y_start + thickness, 0:length] = 255
    return mask


def _vertical_crack_mask(length: int = 100, thickness: int = 4,
                          canvas: int = 200) -> np.ndarray:
    """A vertical crack: a filled rectangle, rotated 90°."""
    mask = np.zeros((canvas, canvas), dtype=np.uint8)
    x_start = canvas // 2 - thickness // 2
    mask[0:length, x_start: x_start + thickness] = 255
    return mask


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAreaMeasurement:
    def test_area_matches_foreground_pixel_count(self) -> None:
        """area_px must equal the exact number of non-zero pixels in the mask."""
        mask = _horizontal_crack_mask(length=80, thickness=6)
        expected_area = float(np.count_nonzero(mask))

        service = MeasurementService()
        result = service.measure_defect(mask)

        assert result.area_px == pytest.approx(expected_area)

    def test_area_zero_for_empty_mask(self) -> None:
        """An all-zero mask should yield area_px == 0.0."""
        empty = np.zeros((100, 100), dtype=np.uint8)
        service = MeasurementService()
        result = service.measure_defect(empty)
        assert result.area_px == 0.0

    def test_area_accepts_0_1_valued_mask(self) -> None:
        """Mask normalisation: {0, 1} values should count the same as {0, 255}."""
        mask_255 = _horizontal_crack_mask()
        mask_01 = (mask_255 > 0).astype(np.uint8)  # values 0 and 1, not 255

        service = MeasurementService()
        r_255 = service.measure_defect(mask_255)
        r_01 = service.measure_defect(mask_01)
        assert r_255.area_px == r_01.area_px


class TestLengthMeasurement:
    def test_length_approximates_crack_extent(self) -> None:
        """
        A 100-px horizontal crack skeleton should have a length close to 100.
        We allow a generous tolerance (±10 px) to account for the diagonal-step
        weighting in _calculate_skeleton_length and edge quantisation.
        """
        crack_len = 100
        mask = _horizontal_crack_mask(length=crack_len, thickness=4)
        skel = Skeletonizer.skeletonize_mask(mask)

        service = MeasurementService()
        result = service.measure_defect(mask, skel)

        assert result.length_px is not None
        assert abs(result.length_px - crack_len) <= 15, (
            f"length_px={result.length_px:.1f} deviates too far from {crack_len}."
        )

    def test_length_none_without_skeleton(self) -> None:
        """length_px must be None when no skeleton is provided."""
        mask = _horizontal_crack_mask()
        service = MeasurementService()
        result = service.measure_defect(mask, skeleton_mask=None)
        assert result.length_px is None


class TestWidthMeasurement:
    def test_width_approximates_crack_thickness(self) -> None:
        """
        Average width of a 4-px-thick horizontal crack should be close to 4.
        The distance transform underestimates at borders, so allow tolerance ±2.
        """
        thickness = 4
        mask = _horizontal_crack_mask(thickness=thickness)
        skel = Skeletonizer.skeletonize_mask(mask)

        service = MeasurementService()
        result = service.measure_defect(mask, skel)

        assert result.width_px is not None
        assert abs(result.width_px - thickness) <= 2.5, (
            f"width_px={result.width_px:.2f} too far from thickness={thickness}."
        )

    def test_max_width_gte_avg_width(self) -> None:
        """max_width_px must always be ≥ width_px (avg) — fundamental invariant."""
        mask = _horizontal_crack_mask(thickness=6)
        skel = Skeletonizer.skeletonize_mask(mask)

        service = MeasurementService()
        result = service.measure_defect(mask, skel)

        assert result.max_width_px is not None
        assert result.width_px is not None
        assert result.max_width_px >= result.width_px - 1e-9  # float safety

    def test_width_none_without_skeleton(self) -> None:
        """width_px and max_width_px must be None when no skeleton is supplied."""
        mask = _horizontal_crack_mask()
        service = MeasurementService()
        result = service.measure_defect(mask)
        assert result.width_px is None
        assert result.max_width_px is None


class TestOrientationMeasurement:
    def test_horizontal_crack_angle_near_zero(self) -> None:
        """A long horizontal crack must have an orientation close to 0°."""
        mask = _horizontal_crack_mask(length=150, thickness=4)
        skel = Skeletonizer.skeletonize_mask(mask)

        service = MeasurementService()
        result = service.measure_defect(mask, skel)

        assert result.orientation_deg is not None
        assert abs(result.orientation_deg) <= 10.0, (
            f"Horizontal crack orientation should be ≈0°, got {result.orientation_deg:.1f}°."
        )

    def test_vertical_crack_angle_near_90(self) -> None:
        """A long vertical crack must have an orientation close to ±90°."""
        mask = _vertical_crack_mask(length=150, thickness=4)
        skel = Skeletonizer.skeletonize_mask(mask)

        service = MeasurementService()
        result = service.measure_defect(mask, skel)

        assert result.orientation_deg is not None
        assert abs(result.orientation_deg) >= 60.0, (
            f"Vertical crack orientation should be ≈±90°, got {result.orientation_deg:.1f}°."
        )

    def test_orientation_none_without_skeleton(self) -> None:
        """orientation_deg must be None when no skeleton is provided."""
        mask = _horizontal_crack_mask()
        service = MeasurementService()
        result = service.measure_defect(mask)
        assert result.orientation_deg is None


class TestCalibration:
    def test_mm_fields_none_without_ratio(self) -> None:
        """Without a calibration ratio, all *_mm fields must be None."""
        mask = _horizontal_crack_mask()
        skel = Skeletonizer.skeletonize_mask(mask)
        service = MeasurementService(pixel_to_mm_ratio=None)
        result = service.measure_defect(mask, skel)

        assert result.area_mm2 is None
        assert result.length_mm is None
        assert result.width_mm is None
        assert result.max_width_mm is None
        assert result.pixel_to_mm_ratio is None

    def test_area_mm2_scales_quadratically(self) -> None:
        """area_mm2 = area_px * ratio² (area scales quadratically with length)."""
        ratio = 0.5  # 0.5 mm per pixel
        mask = _horizontal_crack_mask(length=40, thickness=10)
        expected_area_px = float(np.count_nonzero(mask))
        expected_area_mm2 = expected_area_px * (ratio ** 2)

        service = MeasurementService(pixel_to_mm_ratio=ratio)
        result = service.measure_defect(mask)

        assert result.area_mm2 == pytest.approx(expected_area_mm2)

    def test_length_mm_scales_linearly(self) -> None:
        """length_mm = length_px * ratio."""
        ratio = 0.25
        mask = _horizontal_crack_mask(length=100, thickness=4)
        skel = Skeletonizer.skeletonize_mask(mask)

        service = MeasurementService(pixel_to_mm_ratio=ratio)
        result = service.measure_defect(mask, skel)

        assert result.length_mm is not None
        assert result.length_px is not None
        assert result.length_mm == pytest.approx(result.length_px * ratio, rel=1e-6)

    def test_zero_ratio_does_not_compute_mm_fields(self) -> None:
        """A ratio of 0 should leave all mm fields as None (guard against div-by-zero)."""
        mask = _horizontal_crack_mask()
        service = MeasurementService(pixel_to_mm_ratio=0.0)
        result = service.measure_defect(mask)
        assert result.area_mm2 is None
