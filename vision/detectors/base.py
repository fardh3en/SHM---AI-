"""
Abstract interface and data classes for AI model detection engines.
"""
from abc import ABC, abstractmethod
from typing import Any
import numpy as np
from pydantic import BaseModel, Field

from backend.app.models.detection import DefectType


class RawDetection(BaseModel):
    """
    Model-agnostic raw detection output from an AI model forward pass.
    
    Contains raw coordinates and confidence before any coordinate projection,
    slicing offsets, or mathematical measurements are applied.
    """
    defect_type: DefectType = Field(..., description="Detected class label.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score.")
    
    # Bounding box in pixel coordinates [x1, y1, x2, y2]
    bbox: list[float] = Field(..., min_length=4, max_length=4)
    
    # Binary mask of the target instance (same width and height as input image/tile)
    # Stored as numpy array for efficiency during post-processing
    mask: np.ndarray | None = Field(default=None, description="Binary instance mask.")

    model_config = {
        "arbitrary_types_allowed": True
    }


class IDetector(ABC):
    """
    Abstract Interface for AI Defect Detectors.
    
    Implementations must load weights, detect hardware device, and perform
    inference returning a list of RawDetection objects.
    """

    @abstractmethod
    def predict(self, image: np.ndarray, confidence_threshold: float | None = None) -> list[RawDetection]:
        """
        Perform model forward pass on the input image.

        Args:
            image: RGB image represented as a numpy array [H, W, 3].
            confidence_threshold: Optional override for default confidence threshold.

        Returns:
            A list of RawDetection instances.
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the active model configuration."""
        pass

    @property
    @abstractmethod
    def device(self) -> str:
        """Inference device name (e.g., 'cuda' or 'cpu')."""
        pass
