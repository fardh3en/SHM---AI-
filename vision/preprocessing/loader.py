"""
Image loading and standardisation service.
"""
import logging
from pathlib import Path
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ImageLoader:
    """
    Standardises image loading operations across the platform.
    
    Verifies existence, loads file safely, and ensures conversion to RGB.
    """

    @staticmethod
    def load_image(file_path: str | Path) -> np.ndarray:
        """
        Load an image from disk and standardise it to an RGB numpy array.

        Args:
            file_path: Absolute or relative path to the image file.

        Returns:
            RGB image represented as a numpy array [H, W, 3] with dtype uint8.

        Raises:
            FileNotFoundError: If the target path does not exist.
            ValueError: If the file exists but cannot be parsed as an image.
        """
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Image file does not exist: {path}")

        # Read the image using OpenCV (returns BGR format)
        img_bgr = cv2.imread(str(path))
        
        if img_bgr is None:
            raise ValueError(
                f"File at {path} could not be decoded as an image. "
                "Verify that the file is not corrupted and is in a supported format (PNG, JPG, BMP)."
            )

        # Standardise from BGR (OpenCV default) to RGB (deep learning default)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        
        logger.info(f"Loaded image {path.name} | Dimensions: {img_rgb.shape[1]}x{img_rgb.shape[0]} px")
        return img_rgb
