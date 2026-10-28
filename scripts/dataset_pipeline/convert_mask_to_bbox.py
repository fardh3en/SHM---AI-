"""
Converts binary pixel-level segmentation masks (.png) to standard YOLO detection bounding boxes.
Applicable to Crack500 and DeepCrack datasets.
Uses OpenCV contour extraction with min-area noise filtering.
"""
from pathlib import Path
from typing import Any
import cv2
import numpy as np


def mask_to_bboxes(
    mask: np.ndarray,
    min_area_px: int = 15,
) -> list[tuple[float, float, float, float]]:
    """
    Extract normalized YOLO bounding boxes [xc, yc, w, h] from a binary mask array.
    
    Args:
        mask: 2D numpy array (grayscale/binary, where crack pixels > 0).
        min_area_px: Minimum contour pixel area threshold to filter sensor noise.
    
    Returns:
        List of (x_center, y_center, width, height) normalized to [0.0, 1.0].
    """
    h_img, w_img = mask.shape[:2]
    if h_img == 0 or w_img == 0:
        return []

    # Threshold to binary 0 and 255
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes: list[tuple[float, float, float, float]] = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area_px:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        if w <= 1 or h <= 1:
            continue

        x_center = (x + (w / 2.0)) / w_img
        y_center = (y + (h / 2.0)) / h_img
        norm_w = w / w_img
        norm_h = h / h_img

        # Clamp to [0.0, 1.0]
        xc = max(0.0, min(1.0, x_center))
        yc = max(0.0, min(1.0, y_center))
        nw = max(0.0, min(1.0, norm_w))
        nh = max(0.0, min(1.0, norm_h))

        if nw > 1e-4 and nh > 1e-4:
            boxes.append((round(xc, 6), round(yc, 6), round(nw, 6), round(nh, 6)))

    return boxes


def convert_mask_file(
    mask_path: Path,
    dst_txt_path: Path,
    min_area_px: int = 15,
) -> dict[str, Any]:
    """
    Load a binary mask image and write a standard YOLO detection label file.
    Outputs an empty (0-byte) file if the mask has no crack pixels (negative sample).
    """
    stats = {"valid_boxes": 0, "is_negative": False}
    dst_txt_path.parent.mkdir(parents=True, exist_ok=True)

    if not mask_path.is_file():
        dst_txt_path.write_text("", encoding="utf-8")
        stats["is_negative"] = True
        return stats

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None or np.sum(mask) == 0:
        dst_txt_path.write_text("", encoding="utf-8")
        stats["is_negative"] = True
        return stats

    boxes = mask_to_bboxes(mask, min_area_px=min_area_px)
    if not boxes:
        dst_txt_path.write_text("", encoding="utf-8")
        stats["is_negative"] = True
        return stats

    lines = [f"0 {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}" for xc, yc, w, h in boxes]
    dst_txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    stats["valid_boxes"] = len(boxes)
    return stats
