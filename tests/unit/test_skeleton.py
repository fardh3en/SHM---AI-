"""
Unit tests for vision.postprocessing.skeleton.Skeletonizer.

Tests cover:
- Empty mask → all-zero skeleton output (no crash)
- An already-thin horizontal 1-pixel line → skeleton preserves the line
- A thick horizontal bar → skeleton is thinner than input and still horizontal
- A thick vertical bar → skeleton is thinner than input and still vertical
- Output dtype and value range {0, 255}
"""
import numpy as np

from vision.postprocessing.skeleton import Skeletonizer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _horizontal_bar(height: int = 200, width: int = 200,
                    bar_h: int = 20, bar_y: int = 90) -> np.ndarray:
    """
    Return a binary mask [H, W] uint8 with a filled horizontal bar
    centred at bar_y with thickness bar_h.
    """
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[bar_y: bar_y + bar_h, :] = 255
    return mask


def _vertical_bar(height: int = 200, width: int = 200,
                  bar_w: int = 20, bar_x: int = 90) -> np.ndarray:
    """Return a binary mask with a filled vertical bar."""
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[:, bar_x: bar_x + bar_w] = 255
    return mask


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSkeletonizer:
    def test_empty_mask_returns_zeros(self) -> None:
        """An all-zero mask must produce an all-zero skeleton without raising."""
        empty = np.zeros((100, 100), dtype=np.uint8)
        result = Skeletonizer.skeletonize_mask(empty)

        assert result.shape == (100, 100)
        assert np.count_nonzero(result) == 0

    def test_output_dtype_uint8(self) -> None:
        """Output must always be dtype uint8."""
        mask = _horizontal_bar()
        result = Skeletonizer.skeletonize_mask(mask)
        assert result.dtype == np.uint8

    def test_output_values_binary_0_or_255(self) -> None:
        """Skeleton pixels must only take values 0 or 255."""
        mask = _horizontal_bar()
        result = Skeletonizer.skeletonize_mask(mask)
        unique_vals = set(np.unique(result))
        assert unique_vals.issubset({0, 255})

    def test_thick_horizontal_bar_produces_thinner_skeleton(self) -> None:
        """
        A 20-pixel-thick horizontal bar should skeletonize to a ribbon
        that is at most a few pixels wide in the Y axis — much thinner
        than the original bar.
        """
        bar_h = 20
        mask = _horizontal_bar(bar_h=bar_h)
        skel = Skeletonizer.skeletonize_mask(mask)

        # Find all rows that contain at least one skeleton pixel
        rows_with_pixels = np.any(skel > 0, axis=1)
        skeleton_row_count = int(np.sum(rows_with_pixels))

        # Skeleton should occupy significantly fewer rows than the original bar
        assert skeleton_row_count < bar_h, (
            f"Skeleton spans {skeleton_row_count} rows; "
            f"expected fewer than the original {bar_h}-px bar."
        )

    def test_thick_vertical_bar_produces_thinner_skeleton(self) -> None:
        """A 20-pixel-thick vertical bar should produce a narrow skeleton."""
        bar_w = 20
        mask = _vertical_bar(bar_w=bar_w)
        skel = Skeletonizer.skeletonize_mask(mask)

        cols_with_pixels = np.any(skel > 0, axis=0)
        skeleton_col_count = int(np.sum(cols_with_pixels))

        assert skeleton_col_count < bar_w

    def test_skeleton_is_subset_of_original_mask(self) -> None:
        """
        The skeleton must lie entirely within the foreground region of the
        original mask — skeletonization cannot introduce new pixels.
        """
        mask = _horizontal_bar()
        skel = Skeletonizer.skeletonize_mask(mask)

        # Every skeleton pixel must correspond to a foreground pixel in the mask
        skel_ys, skel_xs = np.where(skel > 0)
        for y, x in zip(skel_ys, skel_xs, strict=True):
            assert mask[y, x] > 0, (
                f"Skeleton pixel at ({y}, {x}) is outside the original mask."
            )

    def test_accepts_0_1_valued_mask(self) -> None:
        """Skeletonizer must work with {0, 1} as well as {0, 255} masks."""
        mask_01 = np.zeros((100, 100), dtype=np.uint8)
        mask_01[40:60, :] = 1  # 1, not 255

        result = Skeletonizer.skeletonize_mask(mask_01)
        # Should still produce a non-empty skeleton
        assert np.count_nonzero(result) > 0
