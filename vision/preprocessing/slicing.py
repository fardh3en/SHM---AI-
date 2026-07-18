"""
Image slicing (sliding window tiling) and coordinate projection service.
"""
from collections.abc import Generator
from dataclasses import dataclass

import numpy as np


@dataclass
class ImageTile:
    """
    Represent a cropped tile of a larger image.
    
    Contains the cropped sub-image and its original spatial offsets.
    """
    image: np.ndarray  # Cropped RGB sub-image [H_tile, W_tile, 3]
    x_offset: int      # X offset of the top-left corner in the original image
    y_offset: int      # Y offset of the top-left corner in the original image
    width: int         # Width of this tile
    height: int        # Height of this tile


class ImageSlicer:
    """
    Handles dividing large orthophotos into overlapping sub-image tiles,
    and projecting sub-image detection coordinates back to full image space.
    """

    def __init__(
        self,
        slice_height: int = 640,
        slice_width: int = 640,
        overlap_ratio: float = 0.4,
    ) -> None:
        """
        Configure the slicer settings.

        Args:
            slice_height: Target height of each cropped window in pixels.
            slice_width: Target width of each cropped window in pixels.
            overlap_ratio: Overlap percentage between adjacent windows [0.0, 1.0).
        """
        self.slice_height = slice_height
        self.slice_width = slice_width
        self.overlap_ratio = overlap_ratio

    def slice_image(self, image: np.ndarray) -> Generator[ImageTile, None, None]:
        """
        Slice a large image into overlapping tiles using a sliding window.

        Args:
            image: Original full-sized RGB image [H, W, 3].

        Yields:
            ImageTile objects containing the sub-image crops and offsets.
        """
        h_img, w_img = image.shape[:2]

        # Calculate step sizes based on overlap ratio
        step_y = int(self.slice_height * (1.0 - self.overlap_ratio))
        step_x = int(self.slice_width * (1.0 - self.overlap_ratio))

        # Ensure step sizes are at least 1 pixel to prevent infinite loops
        step_y = max(1, step_y)
        step_x = max(1, step_x)

        y = 0
        while y < h_img:
            # Handle boundary overlap for the last row
            y_start = y
            y_end = min(h_img, y_start + self.slice_height)
            if y_end == h_img and y_start > 0:
                # Align window to the bottom edge
                y_start = max(0, h_img - self.slice_height)

            x = 0
            while x < w_img:
                # Handle boundary overlap for the last column
                x_start = x
                x_end = min(w_img, x_start + self.slice_width)
                if x_end == w_img and x_start > 0:
                    # Align window to the right edge
                    x_start = max(0, w_img - self.slice_width)

                # Crop tile sub-image
                crop = image[y_start:y_end, x_start:x_end]

                yield ImageTile(
                    image=crop,
                    x_offset=x_start,
                    y_offset=y_start,
                    width=x_end - x_start,
                    height=y_end - y_start,
                )

                # If we've reached the right edge, break the x loop
                if x_end == w_img:
                    break
                x += step_x

            # If we've reached the bottom edge, break the y loop
            if y_end == h_img:
                break
            y += step_y

    @staticmethod
    def project_bbox(
        bbox: list[float],
        x_offset: int,
        y_offset: int,
        img_width: int,
        img_height: int,
    ) -> list[float]:
        """
        Project relative or absolute tile bounding box coordinates back to
        normalized full-image coordinates [0.0, 1.0].

        Args:
            bbox: Bounding box in tile pixel coordinates [x1, y1, x2, y2].
            x_offset: X offset of the tile.
            y_offset: Y offset of the tile.
            img_width: Width of the original full image.
            img_height: Height of the original full image.

        Returns:
            Normalized coordinates [x1, y1, x2, y2] relative to the full image.
        """
        # Add spatial offset to get coordinate in full image space
        x1_full = bbox[0] + x_offset
        y1_full = bbox[1] + y_offset
        x2_full = bbox[2] + x_offset
        y2_full = bbox[3] + y_offset

        # Normalize relative to full image dimensions
        # Clip coordinates to [0.0, 1.0] boundary to be safe
        x1_norm = max(0.0, min(1.0, x1_full / img_width))
        y1_norm = max(0.0, min(1.0, y1_full / img_height))
        x2_norm = max(0.0, min(1.0, x2_full / img_width))
        y2_norm = max(0.0, min(1.0, y2_full / img_height))

        return [x1_norm, y1_norm, x2_norm, y2_norm]

    @staticmethod
    def project_mask(
        mask: np.ndarray,
        x_offset: int,
        y_offset: int,
        img_width: int,
        img_height: int,
    ) -> np.ndarray:
        """
        Project a binary sub-tile mask onto a full-sized black canvas.

        Args:
            mask: Binary mask in tile space [H_tile, W_tile] (values 0 or 1).
            x_offset: X offset of the tile.
            y_offset: Y offset of the tile.
            img_width: Width of the original full image.
            img_height: Height of the original full image.

        Returns:
            Full-sized binary mask [img_height, img_width] with tile mask drawn.
        """
        h_tile, w_tile = mask.shape
        full_mask = np.zeros((img_height, img_width), dtype=np.uint8)

        # Calculate coordinate bounds ensuring we stay within canvas boundaries
        y_end = min(img_height, y_offset + h_tile)
        x_end = min(img_width, x_offset + w_tile)

        # Slice the mask if it extends past original bounds
        mask_h_slice = y_end - y_offset
        mask_w_slice = x_end - x_offset

        full_mask[y_offset:y_end, x_offset:x_end] = mask[0:mask_h_slice, 0:mask_w_slice]
        return full_mask
