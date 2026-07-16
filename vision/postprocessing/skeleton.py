"""
Morphological skeletonization service for centerline extraction.
"""
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
        # Ensure mask is boolean for skimage skeletonization
        bool_mask = (binary_mask > 127)

        if not np.any(bool_mask):
            return np.zeros(binary_mask.shape, dtype=np.uint8)

        # Apply Zhang-Suen or Lee skeletonization algorithm via scikit-image
        skeleton = skeletonize(bool_mask)

        # Map back to standard uint8 binary image format {0, 255}
        return (skeleton * 255).astype(np.uint8)
