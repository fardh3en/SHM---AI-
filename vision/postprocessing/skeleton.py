"""
Morphological skeletonization service for centerline extraction.
"""
from typing import cast

import numpy as np

try:
    from skimage.morphology import skeletonize
    _SKIMAGE_AVAILABLE = True
except ImportError:
    _SKIMAGE_AVAILABLE = False


class Skeletonizer:
    """
    Computes centerlines of binary masks to enable length measurements and
    graph-based topology modeling.
    """

    def __init__(self) -> None:
        if not _SKIMAGE_AVAILABLE:
            raise ImportError(
                "scikit-image is required for Skeletonizer. "
                "Install it using pip install -e '.[vision]'"
            )

    @staticmethod
    def skeletonize_mask(binary_mask: np.ndarray) -> np.ndarray:
        """
        Reduce a binary mask to its 1-pixel-wide centerline.

        Args:
            binary_mask: Binary image [H, W] with values in {0, 255} or {0, 1}.

        Returns:
            A binary skeleton mask [H, W] with values in {0, 255}.
        """
        # Normalise to boolean. Accept both {0, 1} (from project_mask) and
        # {0, 255} (from cv2 operations) — use > 0 rather than > 127 so that
        # single-valued foreground pixels are not silently discarded.
        bool_mask = (binary_mask > 0)

        if not np.any(bool_mask):
            return np.zeros(binary_mask.shape, dtype=np.uint8)

        # Apply Zhang-Suen or Lee skeletonization algorithm via scikit-image
        skeleton = skeletonize(bool_mask)  # type: ignore[no-untyped-call]

        # Map back to standard uint8 binary image format {0, 255}
        return cast("np.ndarray", (skeleton * 255).astype(np.uint8))
