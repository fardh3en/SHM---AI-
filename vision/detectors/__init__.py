"""Detectors package."""
from vision.detectors.base import IDetector, RawDetection
from vision.detectors.yolo import YOLO11Detector, YOLOv8CrackDetector

__all__ = ["IDetector", "RawDetection", "YOLO11Detector", "YOLOv8CrackDetector"]
