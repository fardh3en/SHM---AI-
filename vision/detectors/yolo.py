"""
Ultralytics YOLO11 implementation of the IDetector interface.
"""
import logging
from pathlib import Path
import time
from typing import Any, cast

import numpy as np

_ULTRALYTICS_AVAILABLE: bool = False
_ULTRALYTICS_IMPORT_ERROR: Exception | None = None

try:
    import torch
    from ultralytics import YOLO  # type: ignore[attr-defined]
    _ULTRALYTICS_AVAILABLE = True
except Exception as _import_exc:
    _ULTRALYTICS_AVAILABLE = False
    _ULTRALYTICS_IMPORT_ERROR = _import_exc

from backend.app.core.exceptions import ModelNotFoundError
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
            detail = f" (Original error: {_ULTRALYTICS_IMPORT_ERROR})" if _ULTRALYTICS_IMPORT_ERROR else ""
            raise ImportError(
                f"Ultralytics and PyTorch are required for YOLO11Detector{detail}. "
                "Install them using pip install -e '.[vision]'"
            ) from _ULTRALYTICS_IMPORT_ERROR

        self._model_path = Path(model_path)
        self._default_conf = default_conf
        self._default_iou = default_iou

        # ── Verify weights exist locally (prevent unconsented large auto-downloads) ──
        if not self._model_path.is_file():
            # If the missing weights are the default lightweight nano model (~6MB),
            # attempt automatic download as a self-healing fallback before failing
            if self._model_path.name == "yolo11n-seg.pt":
                logger.info(
                    f"Default weights '{self._model_path.name}' missing at '{self._model_path}'. "
                    "Attempting automatic download of base model weights (~6 MB)..."
                )
                try:
                    from scripts.download_weights import download_weights
                    download_weights(model_name=self._model_path.name, assume_yes=True)
                except Exception as dl_err:
                    logger.warning(f"Auto-provisioning default weights failed: {dl_err}")

            if not self._model_path.is_file():
                parent_dir = self._model_path.parent
                instruction_msg = (
                    f"Configured YOLO segmentation weights '{self._model_path.name}' "
                    f"were not found at '{self._model_path}'. "
                    "Automatic download is disabled to prevent unconsented large file transfers. "
                    f"To provision the model, run 'python scripts/download_weights.py' "
                    f"or download '{self._model_path.name}' and place it in '{parent_dir}/'."
                )
                raise ModelNotFoundError(
                    str(self._model_path),
                    instruction=instruction_msg,
                )

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

        # Optimize CPU thread allocation to prevent thread contention on throttled cloud containers
        if self._device == "cpu" and torch.get_num_threads() > 2:
            torch.set_num_threads(2)
            logger.info("Bound PyTorch CPU threads to 2 to prevent thread contention on cloud containers.")

        logger.info(f"YOLO11 model loaded successfully. Name: {self.model_name}")

    @property
    def model_name(self) -> str:
        return self._model_path.name

    @property
    def device(self) -> str:
        return self._device

    def predict(
        self, image: np.ndarray, confidence_threshold: float | None = None
    ) -> list[RawDetection]:
        """
        Run YOLO11 instance segmentation on an RGB image.
        """
        conf = confidence_threshold if confidence_threshold is not None else self._default_conf
        
        # YOLO expects RGB images. Let's make sure shape matches [H, W, 3]
        if len(image.shape) != 3 or image.shape[2] != 3:
            raise ValueError(f"Input image must be RGB with shape [H, W, 3], got {image.shape}")

        t0 = time.perf_counter()
        threads = torch.get_num_threads() if _ULTRALYTICS_AVAILABLE else "N/A"
        logger.info(
            f"YOLO inference starting: shape={image.shape}, conf={conf}, "
            f"iou={self._default_iou}, device={self._device}, threads={threads}"
        )

        # Run inference in strict evaluation mode without autograd gradient tracking
        inference_ctx = torch.inference_mode if hasattr(torch, "inference_mode") else torch.no_grad
        with inference_ctx():
            raw_results = self._model.predict(
                source=image,
                conf=conf,
                iou=self._default_iou,
                device=self._device,
                imgsz=640,
                verbose=False,
            )

        infer_ms = (time.perf_counter() - t0) * 1000

        if not raw_results:
            logger.info(f"YOLO inference completed in {infer_ms:.1f}ms: 0 raw results returned")
            return []

        results_list = cast("list[Any]", raw_results)
        result = results_list[0]  # Single image inference
        detections: list[RawDetection] = []

        box_count = len(result.boxes) if result and result.boxes is not None else 0
        mask_count = len(result.masks) if result and result.masks is not None else 0
        logger.info(
            f"YOLO forward pass finished in {infer_ms:.1f}ms: "
            f"{box_count} box(es), {mask_count} mask(s) found"
        )

        # Ensure bounding boxes are present
        if result.boxes is None:
            return []

        # Get class names dictionary from model config
        names_dict = self._model.names

        import cv2

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
                mask_tensor = result.masks.data[idx]
                mask_np = (mask_tensor > 0.5).cpu().numpy().astype(np.uint8)
                h_img, w_img = image.shape[:2]
                h_mask, w_mask = mask_np.shape
                
                if h_mask != h_img or w_mask != w_img:
                    mask_array = cv2.resize(mask_np, (w_img, h_img), interpolation=cv2.INTER_NEAREST)
                else:
                    mask_array = mask_np

            detections.append(
                RawDetection(
                    defect_type=defect_type,
                    confidence=confidence,
                    bbox=xyxy,
                    mask=mask_array,
                )
            )

        return detections
