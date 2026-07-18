"""
Unit tests for vision.preprocessing.slicing — ImageSlicer and ImageTile.

Tests cover:
- Single-tile output when image fits within one tile
- Full spatial coverage: union of all tiles covers every pixel of the source image
- project_bbox: correct normalisation into [0, 1] space with offset
- project_bbox: tile at offset (0, 0) — regression for the tile_x=0 edge case
- project_mask: correct placement of a tile mask on the full-image canvas
- project_mask: boundary clipping when mask extends past canvas edge
- Overlap ratio is honoured (step size = tile_size * (1 - overlap))
"""
import numpy as np
import pytest

from vision.preprocessing.slicing import ImageSlicer, ImageTile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_image(height: int, width: int) -> np.ndarray:
    """Create a solid-colour test image [H, W, 3] uint8."""
    return np.ones((height, width, 3), dtype=np.uint8) * 200


def _all_pixel_positions(height: int, width: int) -> set[tuple[int, int]]:
    """Return every (y, x) pixel coordinate in an image of the given size."""
    return {(y, x) for y in range(height) for x in range(width)}


def _covered_pixels(tiles: list[ImageTile]) -> set[tuple[int, int]]:
    """
    Collect every (y, x) coordinate that falls inside at least one tile's
    bounding box in full-image space.
    """
    covered: set[tuple[int, int]] = set()
    for tile in tiles:
        for y in range(tile.y_offset, tile.y_offset + tile.height):
            for x in range(tile.x_offset, tile.x_offset + tile.width):
                covered.add((y, x))
    return covered


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestImageSlicerTileGeneration:
    def test_small_image_produces_single_tile(self) -> None:
        """An image that fits in one tile should yield exactly one tile."""
        slicer = ImageSlicer(slice_height=640, slice_width=640)
        image = _make_image(300, 400)

        tiles = list(slicer.slice_image(image))
        assert len(tiles) == 1
        assert tiles[0].x_offset == 0
        assert tiles[0].y_offset == 0

    def test_large_image_produces_multiple_tiles(self) -> None:
        """An image larger than the tile in both dimensions must produce > 1 tile."""
        slicer = ImageSlicer(slice_height=100, slice_width=100, overlap_ratio=0.0)
        image = _make_image(200, 200)

        tiles = list(slicer.slice_image(image))
        assert len(tiles) > 1

    def test_full_spatial_coverage(self) -> None:
        """
        The union of all tile bounding boxes must cover every pixel of the source
        image. This is the fundamental correctness property of tiled inference.
        """
        h, w = 250, 300
        slicer = ImageSlicer(slice_height=100, slice_width=100, overlap_ratio=0.2)
        image = _make_image(h, w)

        tiles = list(slicer.slice_image(image))
        covered = _covered_pixels(tiles)
        expected = _all_pixel_positions(h, w)

        assert covered == expected, (
            f"Uncovered pixels: {expected - covered}"
        )

    def test_tile_image_shape_matches_declared_dimensions(self) -> None:
        """Each tile's .image array dimensions must match its declared width/height."""
        slicer = ImageSlicer(slice_height=80, slice_width=80, overlap_ratio=0.0)
        image = _make_image(160, 160)

        for tile in slicer.slice_image(image):
            assert tile.image.shape[0] == tile.height
            assert tile.image.shape[1] == tile.width

    def test_overlap_ratio_honoured(self) -> None:
        """
        With a non-zero overlap, adjacent tiles must share pixels.
        We verify by checking that the second tile starts before
        the first tile ends.
        """
        slicer = ImageSlicer(slice_height=100, slice_width=100, overlap_ratio=0.4)
        image = _make_image(200, 100)  # only tall — forces multiple row tiles

        tiles = list(slicer.slice_image(image))
        assert len(tiles) >= 2
        # Second tile y_offset should be less than first tile y_offset + height
        assert tiles[1].y_offset < tiles[0].y_offset + tiles[0].height


class TestProjectBbox:
    def test_no_offset_full_image_bbox(self) -> None:
        """A bbox covering the whole tile at offset (0,0) → normalised [0,0,1,1]."""
        bbox = [0.0, 0.0, 200.0, 150.0]
        result = ImageSlicer.project_bbox(bbox, x_offset=0, y_offset=0,
                                          img_width=200, img_height=150)
        assert result == pytest.approx([0.0, 0.0, 1.0, 1.0])

    def test_offset_adds_correctly(self) -> None:
        """A bbox at (10,10)→(90,90) in a tile at offset (100,50) on a 200×200 image."""
        bbox = [10.0, 10.0, 90.0, 90.0]
        result = ImageSlicer.project_bbox(bbox, x_offset=100, y_offset=50,
                                          img_width=200, img_height=200)
        # x1 = (10+100)/200 = 0.55, y1 = (10+50)/200 = 0.30
        # x2 = (90+100)/200 = 0.95, y2 = (90+50)/200 = 0.70
        assert result == pytest.approx([0.55, 0.30, 0.95, 0.70])

    def test_tile_at_zero_offset_regression(self) -> None:
        """
        Regression for the tile_x=0 edge case.
        tile_x=0 is falsy in Python; the old 'tile_x or 0' code worked by
        coincidence — this test verifies the fix (explicit None check) is stable.
        """
        bbox = [20.0, 30.0, 80.0, 70.0]
        result = ImageSlicer.project_bbox(bbox, x_offset=0, y_offset=0,
                                          img_width=100, img_height=100)
        assert result == pytest.approx([0.20, 0.30, 0.80, 0.70])

    def test_coords_clipped_to_unit_range(self) -> None:
        """A bbox that exceeds the image dimensions must be clipped to [0, 1]."""
        bbox = [-10.0, -5.0, 210.0, 155.0]
        result = ImageSlicer.project_bbox(bbox, x_offset=0, y_offset=0,
                                          img_width=200, img_height=150)
        for coord in result:
            assert 0.0 <= coord <= 1.0


class TestProjectMask:
    def test_mask_placed_at_correct_offset(self) -> None:
        """
        A small foreground mask placed via project_mask should appear at
        exactly the right (y_offset, x_offset) position in the full canvas.
        """
        tile_mask = np.ones((20, 30), dtype=np.uint8)  # fully foreground tile mask
        full = ImageSlicer.project_mask(tile_mask,
                                        x_offset=50, y_offset=40,
                                        img_width=200, img_height=200)

        assert full.shape == (200, 200)
        # Pixels inside the tile region should be 1
        assert np.all(full[40:60, 50:80] == 1)
        # Pixels outside should be 0
        assert full[39, 50] == 0
        assert full[60, 50] == 0

    def test_zero_offset_tile_placement(self) -> None:
        """A tile at (0, 0) should map directly to the top-left of the canvas."""
        tile_mask = np.ones((10, 10), dtype=np.uint8)
        full = ImageSlicer.project_mask(tile_mask,
                                        x_offset=0, y_offset=0,
                                        img_width=100, img_height=100)
        assert np.all(full[0:10, 0:10] == 1)
        assert full[10, 0] == 0

    def test_canvas_stays_within_bounds(self) -> None:
        """project_mask must not raise even if a tile extends past the canvas edge."""
        tile_mask = np.ones((80, 80), dtype=np.uint8)
        # Offset such that tile extends 30 px past the right/bottom edge
        full = ImageSlicer.project_mask(tile_mask,
                                        x_offset=70, y_offset=70,
                                        img_width=100, img_height=100)
        assert full.shape == (100, 100)
        # Only the in-bounds portion should be filled
        assert np.all(full[70:100, 70:100] == 1)
