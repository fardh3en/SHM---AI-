"""
Unit tests for vision.postprocessing.fusion.MaskFusionService.

Tests cover:
- Empty input → black canvas of the requested shape
- Single mask pass-through (values preserved correctly)
- OR fusion: two non-overlapping masks → union is both regions
- OR fusion: two overlapping masks → overlapping region is still foreground
- Shape mismatch: a mask smaller than the canvas is adapted without raising
"""
import numpy as np

from vision.postprocessing.fusion import MaskFusionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _binary_mask(height: int, width: int, *, foreground: bool = True) -> np.ndarray:
    """Return a fully-foreground or fully-background uint8 mask."""
    value = 1 if foreground else 0
    return np.full((height, width), value, dtype=np.uint8)


def _rect_mask(canvas_h: int, canvas_w: int, y1: int, x1: int,
               y2: int, x2: int) -> np.ndarray:
    """Return a mask with a single foreground rectangle [y1:y2, x1:x2]."""
    mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    mask[y1:y2, x1:x2] = 1
    return mask


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMaskFusionEmpty:
    def test_empty_list_returns_black_canvas(self) -> None:
        """fuse_masks([]) must return a zero canvas of the requested shape."""
        result = MaskFusionService.fuse_masks([], canvas_shape=(100, 200))
        assert result.shape == (100, 200)
        assert result.dtype == np.uint8
        assert np.count_nonzero(result) == 0


class TestMaskFusionSingleMask:
    def test_single_foreground_mask_preserved(self) -> None:
        """A single all-foreground mask should pass through as all-255."""
        mask = _binary_mask(50, 60, foreground=True)
        result = MaskFusionService.fuse_masks([mask], canvas_shape=(50, 60))
        assert np.all(result == 255)

    def test_single_background_mask_preserved(self) -> None:
        """A single all-background mask should yield an all-zero output."""
        mask = _binary_mask(50, 60, foreground=False)
        result = MaskFusionService.fuse_masks([mask], canvas_shape=(50, 60))
        assert np.count_nonzero(result) == 0

    def test_output_dtype_is_uint8(self) -> None:
        mask = _binary_mask(10, 10, foreground=True)
        result = MaskFusionService.fuse_masks([mask], canvas_shape=(10, 10))
        assert result.dtype == np.uint8


class TestMaskFusionMultipleMasks:
    def test_non_overlapping_masks_union(self) -> None:
        """Two non-overlapping rectangles should both appear in the fused output."""
        canvas_shape = (100, 100)
        mask_a = _rect_mask(100, 100, 10, 10, 30, 30)  # top-left region
        mask_b = _rect_mask(100, 100, 60, 60, 80, 80)  # bottom-right region

        result = MaskFusionService.fuse_masks([mask_a, mask_b], canvas_shape=canvas_shape)

        # Both rectangles must be foreground
        assert np.all(result[10:30, 10:30] == 255)
        assert np.all(result[60:80, 60:80] == 255)
        # Area between them must be background
        assert result[50, 50] == 0

    def test_overlapping_masks_or_semantics(self) -> None:
        """OR fusion: the overlapping region must remain foreground."""
        canvas_shape = (50, 50)
        mask_a = _rect_mask(50, 50, 0, 0, 30, 30)
        mask_b = _rect_mask(50, 50, 20, 20, 50, 50)

        result = MaskFusionService.fuse_masks([mask_a, mask_b], canvas_shape=canvas_shape)

        # Overlap region [20:30, 20:30] should be foreground
        assert np.all(result[20:30, 20:30] == 255)
        # Mask A exclusive region
        assert np.all(result[0:20, 0:20] == 255)
        # Mask B exclusive region
        assert np.all(result[30:50, 30:50] == 255)

    def test_three_masks_fused(self) -> None:
        """Three masks should all contribute to the union."""
        canvas_shape = (100, 100)
        masks = [
            _rect_mask(100, 100, 0, 0, 20, 20),
            _rect_mask(100, 100, 40, 40, 60, 60),
            _rect_mask(100, 100, 80, 80, 100, 100),
        ]
        result = MaskFusionService.fuse_masks(masks, canvas_shape=canvas_shape)
        assert np.all(result[0:20, 0:20] == 255)
        assert np.all(result[40:60, 40:60] == 255)
        assert np.all(result[80:100, 80:100] == 255)
        assert result[30, 30] == 0


class TestMaskFusionShapeMismatch:
    def test_smaller_mask_adapted_without_error(self) -> None:
        """
        A mask smaller than the canvas must be placed at the top-left without
        raising and without modifying pixels outside its bounds.
        """
        small_mask = _binary_mask(30, 40, foreground=True)
        result = MaskFusionService.fuse_masks([small_mask], canvas_shape=(100, 100))

        assert result.shape == (100, 100)
        # Top-left 30×40 should be foreground
        assert np.all(result[0:30, 0:40] == 255)
        # Everything below/to the right of the mask should be background
        assert result[30, 0] == 0
        assert result[0, 40] == 0
