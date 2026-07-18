"""
Unit tests for vision.preprocessing.loader.ImageLoader.

Tests cover:
- Successful load of a valid image → RGB ndarray [H, W, 3], dtype=uint8
- FileNotFoundError raised for a path that does not exist
- ValueError raised for a file that exists but cannot be decoded as an image
- Output channel order is RGB, not BGR (regression guard)
"""
from pathlib import Path

import numpy as np
import pytest

from vision.preprocessing.loader import ImageLoader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_valid_png(path: Path | str, height: int = 64, width: int = 64) -> None:
    """Write a small solid-colour PNG to *path* using only numpy + cv2."""
    import cv2

    # Green in BGR for cv2.imwrite (so the RGB loader should see (0, 128, 0))
    bgr = np.full((height, width, 3), (0, 128, 0), dtype=np.uint8)
    cv2.imwrite(str(path), bgr)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestImageLoaderHappyPath:
    def test_returns_ndarray(self, tmp_path: Path) -> None:
        """load_image should return a numpy array."""
        img_path = tmp_path / "sample.png"
        _write_valid_png(img_path)

        result = ImageLoader.load_image(img_path)
        assert isinstance(result, np.ndarray)

    def test_shape_is_hwc_3channel(self, tmp_path: Path) -> None:
        """Output must be [H, W, 3] with dtype uint8."""
        img_path = tmp_path / "sample.png"
        _write_valid_png(img_path, height=32, width=48)

        result = ImageLoader.load_image(img_path)
        assert result.ndim == 3
        assert result.shape == (32, 48, 3)
        assert result.dtype == np.uint8

    def test_output_is_rgb_not_bgr(self, tmp_path: Path) -> None:
        """
        OpenCV loads images as BGR. ImageLoader must convert to RGB.

        We write a pure-red pixel (R=255, G=0, B=0).
        In BGR that is written as (0, 0, 255).
        After correct BGR→RGB conversion, channel 0 should be 255 and
        channel 2 should be 0.
        """
        import cv2

        img_path = tmp_path / "red.png"
        bgr = np.full((4, 4, 3), (0, 0, 255), dtype=np.uint8)  # BGR red
        cv2.imwrite(str(img_path), bgr)

        result = ImageLoader.load_image(img_path)
        # In RGB: R=255 is channel 0, B=0 is channel 2
        assert result[0, 0, 0] == 255, "Channel 0 should be Red (255)"
        assert result[0, 0, 2] == 0, "Channel 2 should be Blue (0)"

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """load_image should accept a plain string in addition to Path objects."""
        img_path = tmp_path / "str_path.png"
        _write_valid_png(img_path)

        result = ImageLoader.load_image(str(img_path))
        assert result.shape[2] == 3


class TestImageLoaderErrors:
    def test_raises_file_not_found_for_missing_path(self, tmp_path: Path) -> None:
        """A path that does not exist must raise FileNotFoundError."""
        missing = tmp_path / "does_not_exist.png"
        with pytest.raises(FileNotFoundError, match="does not exist"):
            ImageLoader.load_image(missing)

    def test_raises_value_error_for_non_image_file(self, tmp_path: Path) -> None:
        """A file that exists but cannot be decoded must raise ValueError."""
        bad_file = tmp_path / "not_an_image.png"
        bad_file.write_bytes(b"this is definitely not image data \x00\x01\x02")

        with pytest.raises(ValueError, match="could not be decoded"):
            ImageLoader.load_image(bad_file)

    def test_raises_file_not_found_for_directory(self, tmp_path: Path) -> None:
        """Passing a directory path (not a file) should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ImageLoader.load_image(tmp_path)
