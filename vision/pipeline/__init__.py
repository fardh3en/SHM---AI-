"""Pipeline package."""
from vision.pipeline.base import IInferencePipeline
from vision.pipeline.cv_pipeline import CVInferencePipeline

__all__ = ["IInferencePipeline", "CVInferencePipeline"]
