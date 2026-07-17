"""
Abstract interface for end-to-end computer vision inference pipelines.
"""
from abc import ABC, abstractmethod
from pathlib import Path

from vision.schemas import DetectionResult


class IInferencePipeline(ABC):
    """
    Interface for a full image-to-detections inference pipeline.

    Implementations orchestrate preprocessing, model inference, postprocessing,
    and measurement into a single call, returning standardised DetectionResult
    objects ready for persistence.
    """

    @abstractmethod
    def run(self, image_path: str | Path) -> list[DetectionResult]:
        """
        Run the full inference pipeline on a single image file.

        Args:
            image_path: Path to the source image on disk.

        Returns:
            List of standardised DetectionResult objects, one per detected defect.

        Raises:
            backend.app.core.exceptions.InferenceError: If any stage of the
                pipeline fails (missing file, corrupt image, model load failure,
                inference failure, etc.).
        """
        pass
