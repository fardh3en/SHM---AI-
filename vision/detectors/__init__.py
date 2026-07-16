"""Detectors package."""
from vision.detectors.base import IDetector, RawDetection
from vision.detectors.yolo import YOLO11Detector

__all__ = ["IDetector", "RawDetection", "YOLO11Detector"]
