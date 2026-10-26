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
    def load_image(file_path: str | Path, max_dimension: int | None = None) -> np.ndarray:
        """
        Load an image from disk and standardise it to an RGB numpy array.

        Args:
            file_path: Absolute or relative path to the image file.
            max_dimension: Optional maximum width or height to preserve memory stability
                on memory-constrained cloud environments (e.g. Render Free 512MB RAM).
                Defaults to 640 (matching YOLO11 model input resolution).

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
                "Verify that the file is not corrupted and is in a supported format "
                "(PNG, JPG, BMP)."
            )

        # Standardise from BGR (OpenCV default) to RGB (deep learning default)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # Rescale if dimensions exceed memory-safe threshold
        h_orig, w_orig = img_rgb.shape[:2]
        if max_dimension is not None and max(h_orig, w_orig) > max_dimension:
            scale = max_dimension / max(h_orig, w_orig)
            new_w = max(1, int(round(w_orig * scale)))
            new_h = max(1, int(round(h_orig * scale)))
            img_rgb = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
            logger.info(
                f"Rescaled image {path.name} from {w_orig}x{h_orig} px to {new_w}x{new_h} px "
                f"(scale={scale:.3f}) for memory safety under 512MB RAM."
            )
        else:
            logger.info(
                f"Loaded image {path.name} | "
                f"Dimensions: {img_rgb.shape[1]}x{img_rgb.shape[0]} px"
            )
        return img_rgb
