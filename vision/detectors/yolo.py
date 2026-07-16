"""
Ultralytics YOLO11 implementation of the IDetector interface.
"""
import logging
from pathlib import Path
import numpy as np

try:
    import torch
    from ultralytics import YOLO
    _ULTRALYTICS_AVAILABLE = True
except ImportError:
    _ULTRALYTICS_AVAILABLE = False

from backend.app.models.detection import DefectType
from vision.detectors.base import IDetector, RawDetection

logger = logging.getLogger(__name__)


class YOLO11Detector(IDetector):
    """
    YOLO11 defect detector with instance segmentation support.
    
    Loads fine-tuned weights and executes inference on CPU or GPU dynamically.
    """

    # Map YOLO class index names to our domain DefectType enums.
    # Replace/override this dictionary depending on the classes the model is trained on.
    CLASS_MAPPING = {
        "crack": DefectType.CRACK,
        "spalling": DefectType.SPALLING,
        "corrosion": DefectType.CORROSION,
        "exposed_reinforcement": DefectType.EXPOSED_REINFORCEMENT,
        "delamination": DefectType.DELAMINATION,
        "pothole": DefectType.POTHOLE,
        "surface_damage": DefectType.SURFACE_DAMAGE,
    }

    def __init__(
        self,
        model_path: str | Path,
        device: str = "auto",
        default_conf: float = 0.25,
        default_iou: float = 0.45,
    ) -> None:
        """
        Initialize the YOLO11 model detector.

        Args:
            model_path: Path to the weight file (.pt).
            device: Compute target ('auto', 'cuda', 'cpu').
            default_conf: Default confidence threshold.
            default_iou: Default IOU threshold for NMS.
        """
        if not _ULTRALYTICS_AVAILABLE:
            raise ImportError(
                "Ultralytics and PyTorch are required for YOLO11Detector. "
                "Install them using pip install -e '.[vision]'"
            )

        self._model_path = Path(model_path)
        self._default_conf = default_conf
        self._default_iou = default_iou

        # ── Hardware Auto-Detection ───────────────────────────────────────────
        if device == "auto":
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = device

        logger.info(f"Loading YOLO11 model from {self._model_path} onto {self._device}...")
        
        # Load the model weights.
        # If the file does not exist, Ultralytics might fall back to auto-download.
        # Ensure directory structure exists.
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        self._model = YOLO(str(self._model_path))
        
        # Move model to target device
        self._model.to(self._device)
        logger.info(f"YOLO11 model loaded successfully. Name: {self.model_name}")

    @property
    def model_name(self) -> str:
        return self._model_path.name

    @property
    def device(self) -> str:
        return self._device

    def predict(self, image: np.ndarray, confidence_threshold: float | None = None) -> list[RawDetection]:
        """
        Run YOLO11 instance segmentation on an RGB image.
        """
        conf = confidence_threshold if confidence_threshold is not None else self._default_conf
        
        # YOLO expects RGB images. Let's make sure shape matches [H, W, 3]
        if len(image.shape) != 3 or image.shape[2] != 3:
            raise ValueError(f"Input image must be RGB with shape [H, W, 3], got {image.shape}")

        results = self._model.predict(
            source=image,
            conf=conf,
            iou=self._default_iou,
            device=self._device,
            verbose=False,
        )

        if not results:
            return []

        result = results[0]  # Single image inference
        detections: list[RawDetection] = []

        # Ensure bounding boxes are present
        if result.boxes is None:
            return []

        # Get class names dictionary from model config
        names_dict = self._model.names

        for idx, box in enumerate(result.boxes):
            # Extract box coordinates (pixel coordinates [x1, y1, x2, y2])
            xyxy = box.xyxy[0].cpu().numpy().tolist()
            confidence = float(box.conf[0].cpu().item())
            class_idx = int(box.cls[0].cpu().item())
            
            # Map index to string label, then to domain enum
            class_name = names_dict.get(class_idx, "unknown").lower()
            defect_type = self.CLASS_MAPPING.get(class_name, DefectType.UNKNOWN)

            # Extract segment mask if available
            mask_array = None
            if result.masks is not None:
                # Mask matches image shape in xy coordinates
                # Stored as float/binary [H, W] mask
                mask_tensor = result.masks.data[idx]
                
                # Resize mask tensor to original image shape if necessary
                h_img, w_img = image.shape[:2]
                h_mask, w_mask = mask_tensor.shape
                
                if h_mask != h_img or w_mask != w_img:
                    # Resize mask to original size using PyTorch interpolate
                    import torch.nn.functional as F
                    # Reshape to [1, 1, H, W] for interpolation
                    mask_resized = F.interpolate(
                        mask_tensor.unsqueeze(0).unsqueeze(0),
                        size=(h_img, w_img),
                        mode="bilinear",
                        align_corners=False
                    )
                    mask_array = (mask_resized[0, 0] > 0.5).cpu().numpy().astype(np.uint8)
                else:
                    mask_array = (mask_tensor > 0.5).cpu().numpy().astype(np.uint8)

            detections.append(
                RawDetection(
                    defect_type=defect_type,
                    confidence=confidence,
                    bbox=xyxy,
                    mask=mask_array,
                )
            )

        return detections
