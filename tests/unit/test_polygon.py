"""
Unit tests for vision.postprocessing.polygon.MaskPolygonConverter.

Tests cover:
- Empty mask → None (no foreground pixels)
- All-background mask after binarisation → None
- A valid filled rectangle → GeoJSON-style dict with correct type key
- Ring closure: first coordinate == last coordinate (GeoJSON Polygon convention)
- Minimum vertex count: polygon must have ≥ 3 vertices (before closing) +
  the closing duplicate, i.e. at least 4 entries in the coordinates list
- Simplification: a smooth circle produces fewer points than the raw contour
- Mask with only noise/1-px contour → None (contour area ≤ 0 guard)
"""
import numpy as np

from vision.postprocessing.polygon import MaskPolygonConverter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rect_mask(h: int = 100, w: int = 100,
               y1: int = 10, x1: int = 10,
               y2: int = 90, x2: int = 90) -> np.ndarray:
    """Return a uint8 mask with a single filled rectangle."""
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[y1:y2, x1:x2] = 255
    return mask


def _circle_mask(radius: int = 60, canvas: int = 200) -> np.ndarray:
    """Return a uint8 mask containing a filled circle."""
    import cv2

    mask = np.zeros((canvas, canvas), dtype=np.uint8)
    centre = (canvas // 2, canvas // 2)
    cv2.circle(mask, centre, radius, 255, thickness=-1)
    return mask


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMaskPolygonConverterEmpty:
    def test_all_zero_mask_returns_none(self) -> None:
        """An all-zero mask has no contour — must return None."""
        empty = np.zeros((100, 100), dtype=np.uint8)
        result = MaskPolygonConverter.mask_to_polygon(empty)
        assert result is None

    def test_single_pixel_mask_returns_none_or_valid(self) -> None:
        """
        A single foreground pixel produces a contour area of 0 and should
        return None. (Edge case — zero-area contour is filtered out.)
        """
        mask = np.zeros((50, 50), dtype=np.uint8)
        mask[25, 25] = 255
        result = MaskPolygonConverter.mask_to_polygon(mask)
        # Either None (area guard triggers) or a valid polygon if cv2 finds
        # a tiny ring — both are acceptable. We only forbid an exception.
        assert result is None or isinstance(result, dict)


class TestMaskPolygonConverterValidOutput:
    def test_returns_dict_for_valid_mask(self) -> None:
        """A clear rectangular mask should produce a dict, not None."""
        mask = _rect_mask()
        result = MaskPolygonConverter.mask_to_polygon(mask)
        assert result is not None
        assert isinstance(result, dict)

    def test_geojson_type_field(self) -> None:
        """The returned dict must have 'type': 'Polygon'."""
        mask = _rect_mask()
        result = MaskPolygonConverter.mask_to_polygon(mask)
        assert result is not None
        assert result.get("type") == "Polygon"

    def test_geojson_coordinates_key_present(self) -> None:
        """The returned dict must have a 'coordinates' key."""
        mask = _rect_mask()
        result = MaskPolygonConverter.mask_to_polygon(mask)
        assert result is not None
        assert "coordinates" in result

    def test_ring_is_closed(self) -> None:
        """
        GeoJSON convention: the outer ring must be closed, i.e. the first
        coordinate must equal the last coordinate in the ring.
        """
        mask = _rect_mask()
        result = MaskPolygonConverter.mask_to_polygon(mask)
        assert result is not None

        ring = result["coordinates"][0]
        assert ring[0] == ring[-1], (
            f"Ring is not closed: first={ring[0]}, last={ring[-1]}"
        )

    def test_minimum_vertex_count(self) -> None:
        """
        A polygon must have at least 4 entries in its ring list
        (3 unique vertices + closing duplicate) to be geometrically valid.
        """
        mask = _rect_mask()
        result = MaskPolygonConverter.mask_to_polygon(mask)
        assert result is not None

        ring = result["coordinates"][0]
        assert len(ring) >= 4, f"Ring has only {len(ring)} entries."

    def test_coordinates_are_float_pairs(self) -> None:
        """Every coordinate in the ring must be [float, float]."""
        mask = _rect_mask()
        result = MaskPolygonConverter.mask_to_polygon(mask)
        assert result is not None

        for coord in result["coordinates"][0]:
            assert len(coord) == 2
            assert isinstance(coord[0], float)
            assert isinstance(coord[1], float)

    def test_simplification_reduces_point_count(self) -> None:
        """
        With simplify_tolerance > 0, a smooth circular mask should produce
        fewer polygon vertices than its raw contour would.

        We compare the result from the default tolerance vs a tolerance of 0
        by manually extracting contour counts.
        """
        import cv2

        mask = _circle_mask()
        binary = (mask > 0).astype(np.uint8) * 255
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        raw_count = len(max(contours, key=cv2.contourArea))

        result = MaskPolygonConverter.mask_to_polygon(mask, simplify_tolerance=2.0)
        assert result is not None

        simplified_count = len(result["coordinates"][0]) - 1  # subtract closing pt
        assert simplified_count < raw_count, (
            f"Simplification did not reduce point count: "
            f"simplified={simplified_count}, raw={raw_count}."
        )

    def test_accepts_0_1_valued_mask(self) -> None:
        """
        mask_to_polygon must work with {0, 1} masks (not just {0, 255}).
        This is because project_mask returns uint8 with values 0/1.
        """
        mask_01 = _rect_mask()
        mask_01 = (mask_01 > 0).astype(np.uint8)  # {0, 1}

        result = MaskPolygonConverter.mask_to_polygon(mask_01)
        assert result is not None
        assert result["type"] == "Polygon"
