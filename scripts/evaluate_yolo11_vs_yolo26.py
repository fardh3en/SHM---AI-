"""
Reproducible and methodologically reliable evaluation script for YOLO11 vs YOLO26 crack segmentation.

Safeguards:
- Read-only: Does not retrain, overwrite, rename, or delete model checkpoints.
- Does not modify live application database, config, frontend, or production inference.
- Enforces uncalibrated pixel-space metrics unless independently supplied calibration is provided.
- Compares pixel-level segmentation masks and skeleton morphology, not boxes only.
- Validates mask dimensions and handles empty/missing ground-truth labels explicitly.
- Computes post-warmup latency statistics (mean, median, p95).
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any

import cv2
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vision.detectors.yolo import YOLO11Detector
from vision.postprocessing.measurements import MeasurementService
from vision.postprocessing.skeleton import Skeletonizer

logger = logging.getLogger("evaluate_benchmark")


def rasterize_yolo_polygons(
    label_path: Path | str,
    img_width: int,
    img_height: int,
    raise_if_missing: bool = False,
) -> tuple[np.ndarray, int]:
    """
    Rasterize normalized YOLO segmentation polygons into a binary ground-truth mask.

    Args:
        label_path: Path to the .txt label file.
        img_width: Target image width in pixels.
        img_height: Target image height in pixels.
        raise_if_missing: If True, raise FileNotFoundError if label file does not exist.

    Returns:
        tuple of (binary uint8 mask of shape [H, W] with values in {0, 1}, polygon count).
    """
    mask = np.zeros((img_height, img_width), dtype=np.uint8)
    path = Path(label_path)
    if not path.is_file():
        if raise_if_missing:
            raise FileNotFoundError(f"Label file not found: {path}")
        return mask, 0

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return mask, 0

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    polygon_count = 0

    for line in lines:
        parts = line.split()
        if len(parts) < 5:
            # Need at least class_id + 2 vertices (4 coordinates)
            continue
        try:
            coords = [float(x) for x in parts[1:]]
            if len(coords) % 2 != 0:
                coords = coords[:-1]
            pts = np.array(coords, dtype=np.float32).reshape(-1, 2)
            pts_px = (pts * [img_width, img_height]).astype(np.int32)
            if len(pts_px) >= 3:
                cv2.fillPoly(mask, [pts_px], 1)
                polygon_count += 1
        except (ValueError, IndexError):
            continue

    return mask, polygon_count


def check_ground_truth_label(
    label_path: Path | str,
    img_width: int,
    img_height: int,
) -> tuple[np.ndarray, int, str]:
    """
    Load and categorize ground truth label into an explicit status.

    Returns:
        tuple of:
          - mask: binary uint8 mask [H, W]
          - polygon_count: int
          - gt_status: str ("POSITIVE", "VERIFIED_NEGATIVE", "MISSING_LABEL", "UNREADABLE_LABEL")
    """
    path = Path(label_path)
    mask = np.zeros((img_height, img_width), dtype=np.uint8)

    if not path.is_file():
        return mask, 0, "MISSING_LABEL"

    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        logger.warning(f"Error reading label file '{path}': {exc}")
        return mask, 0, "UNREADABLE_LABEL"

    if not text:
        return mask, 0, "VERIFIED_NEGATIVE"

    mask, poly_count = rasterize_yolo_polygons(path, img_width, img_height, raise_if_missing=False)
    if poly_count > 0 and np.count_nonzero(mask) > 0:
        return mask, poly_count, "POSITIVE"
    return mask, 0, "VERIFIED_NEGATIVE"


def compute_mask_iou_dice(
    pred_mask: np.ndarray,
    gt_mask: np.ndarray,
    empty_value: float | None = None,
) -> tuple[float | None, float | None]:
    """
    Compute image-level union-mask Intersection over Union (IoU) and Dice coefficient.

    Methodological rules:
    - Pre-condition: pred_mask and gt_mask MUST have identical [H, W] dimensions.
    - On positive ground truth (gt_pixels > 0):
      - If pred has pixels: standard IoU and Dice.
      - If pred is empty: returns (0.0, 0.0) penalizing false negatives.
    - On negative ground truth (gt_pixels == 0):
      - If pred has pixels: returns (0.0, 0.0) penalizing false positive alarms.
      - If pred is empty: foreground crack IoU/Dice are undefined on background-only surfaces;
        returns (empty_value, empty_value) which defaults to (None, None).

    Note:
    - These are image-level union-mask segmentation metrics.
    - They are NOT instance-level Average Precision (AP50 / mAP50-95).
    """
    if pred_mask.shape != gt_mask.shape:
        raise ValueError(
            f"Shape mismatch: predicted mask has shape {pred_mask.shape}, "
            f"while ground-truth mask has shape {gt_mask.shape}."
        )

    pred_bool = (pred_mask > 0)
    gt_bool = (gt_mask > 0)

    pred_sum = int(np.count_nonzero(pred_bool))
    gt_sum = int(np.count_nonzero(gt_bool))

    if pred_sum == 0 and gt_sum == 0:
        return empty_value, empty_value

    if gt_sum == 0 and pred_sum > 0:
        return 0.0, 0.0

    if gt_sum > 0 and pred_sum == 0:
        return 0.0, 0.0

    intersection = int(np.count_nonzero(np.logical_and(pred_bool, gt_bool)))
    union = int(np.count_nonzero(np.logical_or(pred_bool, gt_bool)))

    iou = float(intersection) / float(union) if union > 0 else 0.0
    dice = (2.0 * float(intersection)) / float(pred_sum + gt_sum) if (pred_sum + gt_sum) > 0 else 0.0

    return round(iou, 4), round(dice, 4)


def measure_mask_morphology(
    mask: np.ndarray,
    measurement_service: MeasurementService | None = None,
) -> dict[str, float]:
    """
    Extract morphological metrics (area, skeleton length, average width, max width) in pixel space.

    Args:
        mask: Binary mask of shape [H, W] with values in {0, 1} or {0, 255}.
        measurement_service: Optional instantiated MeasurementService (uncalibrated).

    Returns:
        dict with area_px, length_px, width_px, max_width_px.
    """
    bool_mask = (mask > 0)
    area_px = float(np.count_nonzero(bool_mask))

    if area_px < 3:
        return {
            "area_px": area_px,
            "length_px": 0.0,
            "width_px": 0.0,
            "max_width_px": 0.0,
        }

    service = measurement_service or MeasurementService(pixel_to_mm_ratio=None)
    y_indices, x_indices = np.where(bool_mask)
    pad = 4
    h, w = mask.shape[:2]
    crop_y1 = max(0, int(y_indices.min()) - pad)
    crop_y2 = min(h, int(y_indices.max()) + pad + 1)
    crop_x1 = max(0, int(x_indices.min()) - pad)
    crop_x2 = min(w, int(x_indices.max()) + pad + 1)

    crop_mask = (bool_mask[crop_y1:crop_y2, crop_x1:crop_x2]).astype(np.uint8) * 255
    crop_skel = Skeletonizer.skeletonize_mask(crop_mask)

    meas = service.measure_defect(crop_mask, crop_skel)

    return {
        "area_px": round(meas.area_px, 1),
        "length_px": round(meas.length_px or 0.0, 1),
        "width_px": round(meas.width_px or 0.0, 2),
        "max_width_px": round(meas.max_width_px or 0.0, 2),
    }


def detect_anomalies(
    det_count: int,
    gt_polygon_count: int,
    gt_area_px: float,
    det_measurements: list[dict[str, float]],
    iou: float | None,
    gt_status: str = "POSITIVE",
) -> dict[str, bool]:
    """
    Identify potential model failure modes using explicit heuristic criteria:

    Criteria:
    - missed_crack_heuristic: gt_status is POSITIVE (gt_area_px > 0) and
      (det_count == 0 or (iou is not None and iou < 0.01)).
    - fragmentation_proxy: Heuristic screening proxy flagging images where ground-truth
      has <= 2 polygons but model produced >= 3 separate detections.
      Note: This is an instance-count heuristic proxy, NOT a topological connected-component proof.
    - broad_mask_heuristic: Screening heuristic flagging any detection with width > 25.0 px,
      max_width > 50.0 px, or area/length > 25.0 px.
      Note: This is a morphological screening heuristic, not a confirmed false-positive diagnosis.
    - false_positive: gt_status is VERIFIED_NEGATIVE (gt_area_px == 0) and det_count > 0.
      Missing label images are never flagged as false positives.
    """
    iou_val = iou if iou is not None else 0.0

    if gt_status == "POSITIVE":
        missed_crack = (gt_area_px > 0) and (det_count == 0 or iou_val < 0.01)
        fragmentation_proxy = (gt_polygon_count <= 2) and (det_count >= 3)
        false_positive = False
    elif gt_status == "VERIFIED_NEGATIVE":
        missed_crack = False
        fragmentation_proxy = False
        false_positive = (det_count > 0)
    else:  # MISSING_LABEL or UNREADABLE_LABEL
        missed_crack = False
        fragmentation_proxy = False
        false_positive = False

    broad_mask = False
    for m in det_measurements:
        w = m.get("width_px", 0.0)
        mw = m.get("max_width_px", 0.0)
        length = m.get("length_px", 0.0)
        area = m.get("area_px", 0.0)
        if w > 25.0 or mw > 50.0:
            broad_mask = True
            break
        if length > 0 and (area / length) > 25.0:
            broad_mask = True
            break

    return {
        "missed_crack_heuristic": missed_crack,
        "fragmentation_proxy": fragmentation_proxy,
        "broad_mask_heuristic": broad_mask,
        "false_positive": false_positive,
        # Backward-compatibility aliases for existing CSV schema:
        "anomaly_missed_crack": missed_crack,
        "anomaly_fragmented": fragmentation_proxy,
        "anomaly_broad_mask": broad_mask,
        "anomaly_false_positive": false_positive,
    }


def compute_latency_statistics(latencies_ms: list[float]) -> dict[str, float]:
    """
    Compute mean, median, and 95th percentile inference latency from post-warmup timings.
    """
    if not latencies_ms:
        return {
            "mean_ms": 0.0,
            "median_ms": 0.0,
            "p95_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
        }
    arr = np.array(latencies_ms, dtype=np.float64)
    return {
        "mean_ms": round(float(np.mean(arr)), 2),
        "median_ms": round(float(np.median(arr)), 2),
        "p95_ms": round(float(np.percentile(arr, 95)), 2),
        "min_ms": round(float(np.min(arr)), 2),
        "max_ms": round(float(np.max(arr)), 2),
    }


def verify_checkpoints(
    model1_path: Path,
    model2_path: Path,
    allow_single_model: bool = False,
) -> tuple[bool, str]:
    """
    Verify presence of model weight checkpoints without modifying them.

    Returns:
        tuple of (can_proceed: bool, diagnostic_message: str).
    """
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("SHM-AI Model Validation Checkpoint Verification")
    lines.append("=" * 70)

    m1_exists = model1_path.is_file()
    m2_exists = model2_path.is_file()

    m1_size_str = f"({model1_path.stat().st_size:,} bytes)" if m1_exists else "(MISSING)"
    lines.append(f"Model 1 (Fine-tuned YOLO11):")
    lines.append(f"  Found:    {m1_exists}")
    lines.append(f"  Path:     {model1_path} {m1_size_str}")

    m2_size_str = f"({model2_path.stat().st_size:,} bytes)" if m2_exists else "(MISSING)"
    lines.append(f"Model 2 (YOLO26-seg):")
    lines.append(f"  Found:    {m2_exists}")
    lines.append(f"  Path:     {model2_path} {m2_size_str}")
    lines.append("-" * 70)

    if not m1_exists:
        lines.append(f"ERROR: Model 1 checkpoint is missing at '{model1_path}'.")
        return False, "\n".join(lines)

    if not m2_exists:
        if allow_single_model:
            lines.append("NOTICE: Model 2 checkpoint is absent. Proceeding with Model 1 baseline")
            lines.append("evaluation only because --allow-single-model was explicitly specified.")
            return True, "\n".join(lines)
        else:
            lines.append("STATUS: Comparative evaluation cannot proceed because Model 2 is absent.")
            lines.append("")
            lines.append("Exact Expected Location for YOLO26 checkpoint:")
            lines.append(f"  --> {model2_path.resolve()}")
            lines.append("")
            lines.append("To proceed:")
            lines.append(f"  1. Place the YOLO26 checkpoint file at:")
            lines.append(f"     {model2_path.resolve()}")
            lines.append(f"     (or specify via --model2 <custom_path>)")
            lines.append(f"  2. Re-run this evaluation command:")
            lines.append(f"     python scripts/evaluate_yolo11_vs_yolo26.py")
            lines.append(f"  3. To evaluate Model 1 alone as a standalone benchmark:")
            lines.append(f"     python scripts/evaluate_yolo11_vs_yolo26.py --allow-single-model")
            lines.append("=" * 70)
            return False, "\n".join(lines)

    lines.append("STATUS: Both checkpoints found and verified. Ready for evaluation.")
    lines.append("=" * 70)
    return True, "\n".join(lines)


def evaluate_model_on_dataset(
    detector: YOLO11Detector,
    model_label: str,
    image_paths: list[Path],
    labels_dir: Path,
    conf_threshold: float = 0.25,
    warmup_passes: int = 3,
) -> list[dict[str, Any]]:
    """
    Evaluate a detector instance across a list of test images with explicit warm-up.

    Args:
        detector: Instantiated detector implementing predict().
        model_label: Display label for the model.
        image_paths: List of image paths to evaluate.
        labels_dir: Directory containing ground-truth polygon labels.
        conf_threshold: Inference confidence threshold.
        warmup_passes: Number of warm-up forward passes to execute before timing.

    Returns:
        list of per-image metric records.
    """
    measurement_service = MeasurementService(pixel_to_mm_ratio=None)
    records: list[dict[str, Any]] = []

    # ── Warm-up Phase (excluded from latency records) ──────────────────────────
    if warmup_passes > 0 and image_paths:
        warmup_count = min(warmup_passes, len(image_paths))
        logger.info(f"[{model_label}] Executing {warmup_count} warm-up pass(es) (excluded from latency stats)...")
        for w_idx in range(warmup_count):
            w_bgr = cv2.imread(str(image_paths[w_idx]))
            if w_bgr is not None:
                w_rgb = cv2.cvtColor(w_bgr, cv2.COLOR_BGR2RGB)
                _ = detector.predict(w_rgb, confidence_threshold=conf_threshold)

    # ── Evaluation Loop ───────────────────────────────────────────────────────
    total_imgs = len(image_paths)
    for idx, img_path in enumerate(image_paths, 1):
        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            logger.warning(f"Could not read image: {img_path}")
            continue

        h_img, w_img = img_bgr.shape[:2]
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # Ground truth loading & verification
        stem = img_path.stem
        label_file = labels_dir / f"{stem}.txt"
        gt_mask, gt_count, gt_status = check_ground_truth_label(label_file, w_img, h_img)
        gt_area_px = float(np.count_nonzero(gt_mask))

        if gt_status == "MISSING_LABEL":
            logger.warning(f"Label file missing for image '{img_path.name}' at '{label_file}'.")

        # Timed inference pass (post-warmup)
        t0 = time.perf_counter()
        detections = detector.predict(img_rgb, confidence_threshold=conf_threshold)
        infer_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # Instance mask accumulation & morphological measurement
        pred_mask_union = np.zeros((h_img, w_img), dtype=np.uint8)
        det_measurements: list[dict[str, float]] = []

        for det in detections:
            if det.mask is not None:
                inst_mask = (det.mask > 0).astype(np.uint8)
                # Verify mask dimensions match image dimensions
                if inst_mask.shape != (h_img, w_img):
                    inst_mask = cv2.resize(inst_mask, (w_img, h_img), interpolation=cv2.INTER_NEAREST)
                pred_mask_union = np.bitwise_or(pred_mask_union, inst_mask)
                m = measure_mask_morphology(inst_mask, measurement_service)
                det_measurements.append(m)
            else:
                det_measurements.append({
                    "area_px": 0.0,
                    "length_px": 0.0,
                    "width_px": 0.0,
                    "max_width_px": 0.0,
                })

        # Image-level union-mask metrics
        if gt_status in ("POSITIVE", "VERIFIED_NEGATIVE"):
            iou, dice = compute_mask_iou_dice(pred_mask_union, gt_mask, empty_value=None)
        else:
            iou, dice = None, None

        total_mask_area_px = float(np.count_nonzero(pred_mask_union))
        total_length_px = round(sum(m["length_px"] for m in det_measurements), 1)

        valid_widths = [m["width_px"] for m in det_measurements if m["width_px"] > 0]
        mean_width_px = round(float(np.mean(valid_widths)), 2) if valid_widths else 0.0
        max_width_px = round(max([m["max_width_px"] for m in det_measurements], default=0.0), 2)

        # Failure mode / anomaly detection
        anomalies = detect_anomalies(
            det_count=len(detections),
            gt_polygon_count=gt_count,
            gt_area_px=gt_area_px,
            det_measurements=det_measurements,
            iou=iou,
            gt_status=gt_status,
        )

        records.append({
            "image_name": img_path.name,
            "image_width": w_img,
            "image_height": h_img,
            "gt_status": gt_status,
            "gt_crack_count": gt_count,
            "gt_mask_area_px": round(gt_area_px, 1),
            "model_name": model_label,
            "detection_count": len(detections),
            "total_mask_area_px": round(total_mask_area_px, 1),
            "total_skeleton_length_px": total_length_px,
            "mean_crack_width_px": mean_width_px,
            "max_crack_width_px": max_width_px,
            "inference_time_ms": infer_time_ms,
            "mask_iou": iou,
            "mask_dice": dice,
            # Explicit failure analysis fields:
            "anomaly_missed_crack_heuristic": anomalies["missed_crack_heuristic"],
            "anomaly_fragmentation_proxy": anomalies["fragmentation_proxy"],
            "anomaly_broad_mask_heuristic": anomalies["broad_mask_heuristic"],
            "anomaly_false_positive": anomalies["false_positive"],
            # Backward-compatibility aliases:
            "anomaly_missed_crack": anomalies["anomaly_missed_crack"],
            "anomaly_fragmented": anomalies["anomaly_fragmented"],
            "anomaly_broad_mask": anomalies["anomaly_broad_mask"],
            "calibration_status": "uncalibrated_pixel_space",
        })

        if idx % 20 == 0 or idx == total_imgs:
            logger.info(f"[{model_label}] Processed {idx}/{total_imgs} images...")

    return records


def compute_benchmark_summary(sub_records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute structured benchmark summary statistics across positive, negative,
    and measurement subsets.
    """
    if not sub_records:
        return {}

    n = len(sub_records)
    pos_records = [
        r for r in sub_records
        if r.get("gt_status") == "POSITIVE" or (r.get("gt_status") is None and r.get("gt_mask_area_px", 0) > 0)
    ]
    neg_records = [
        r for r in sub_records
        if r.get("gt_status") == "VERIFIED_NEGATIVE" or (r.get("gt_status") is None and r.get("gt_mask_area_px", 0) == 0)
    ]
    missing_label_records = [r for r in sub_records if r.get("gt_status") in ("MISSING_LABEL", "UNREADABLE_LABEL")]

    n_pos = len(pos_records)
    n_neg = len(neg_records)

    # Positive image mask metrics (union-mask semantic proxy)
    valid_ious = [r["mask_iou"] for r in pos_records if r.get("mask_iou") is not None]
    valid_dices = [r["mask_dice"] for r in pos_records if r.get("mask_dice") is not None]

    mean_iou = float(np.mean(valid_ious)) if valid_ious else 0.0
    mean_dice = float(np.mean(valid_dices)) if valid_dices else 0.0

    # Negative image false positive rate
    neg_fps = sum(1 for r in neg_records if r.get("detection_count", 0) > 0)
    neg_fp_rate = round(neg_fps / n_neg, 4) if n_neg > 0 else 0.0

    # Detections and measurements
    detected_records = [r for r in sub_records if r.get("detection_count", 0) > 0]
    zero_det_records = [r for r in sub_records if r.get("detection_count", 0) == 0]

    mean_det_all = float(np.mean([r["detection_count"] for r in sub_records]))
    mean_det_pos = float(np.mean([r["detection_count"] for r in pos_records])) if pos_records else 0.0

    mean_area_detected = float(np.mean([r["total_mask_area_px"] for r in detected_records])) if detected_records else 0.0
    mean_length_detected = float(np.mean([r["total_skeleton_length_px"] for r in detected_records])) if detected_records else 0.0

    valid_widths = [r["mean_crack_width_px"] for r in detected_records if r.get("mean_crack_width_px", 0) > 0]
    mean_width_detected = float(np.mean(valid_widths)) if valid_widths else 0.0
    max_width_all = float(max([r["max_crack_width_px"] for r in sub_records], default=0.0))

    # Latency statistics
    latencies = [r["inference_time_ms"] for r in sub_records]
    lat_stats = compute_latency_statistics(latencies)

    # Heuristic failure modes
    missed = sum(1 for r in sub_records if r.get("anomaly_missed_crack_heuristic", r.get("anomaly_missed_crack", False)))
    fragmentation_proxies = sum(1 for r in sub_records if r.get("anomaly_fragmentation_proxy", r.get("anomaly_fragmented", False)))
    broad = sum(1 for r in sub_records if r.get("anomaly_broad_mask_heuristic", r.get("anomaly_broad_mask", False)))

    return {
        "total_images": n,
        "positive_images_count": n_pos,
        "negative_images_count": n_neg,
        "missing_label_images_count": len(missing_label_records),
        "mean_iou_positive_gt": round(mean_iou, 4),
        "mean_dice_positive_gt": round(mean_dice, 4),
        "negative_fp_count": neg_fps,
        "negative_fp_rate": neg_fp_rate,
        "mean_det_count_all": round(mean_det_all, 2),
        "mean_det_count_positive": round(mean_det_pos, 2),
        "images_with_valid_detections": len(detected_records),
        "images_without_detections": len(zero_det_records),
        "mean_area_detected_px": round(mean_area_detected, 1),
        "mean_length_detected_px": round(mean_length_detected, 1),
        "mean_width_detected_px": round(mean_width_detected, 2),
        "max_width_px": round(max_width_all, 2),
        "latency_mean_ms": lat_stats["mean_ms"],
        "latency_median_ms": lat_stats["median_ms"],
        "latency_p95_ms": lat_stats["p95_ms"],
        "missed_cracks_heuristic_count": missed,
        "fragmentation_proxy_count": fragmentation_proxies,
        "broad_masks_heuristic_count": broad,
    }


def save_results_csv(records: list[dict[str, Any]], output_path: Path) -> None:
    """Save evaluation metrics to CSV file preserving backward compatibility."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        return

    fieldnames = list(records[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            # Map None values to empty strings for standard CSV formatting
            row = {k: ("" if v is None else v) for k, v in r.items()}
            writer.writerow(row)


def generate_markdown_report(
    records: list[dict[str, Any]],
    model1_label: str,
    model2_label: str | None,
    output_path: Path,
    missing_model2_msg: str | None = None,
    device: str = "cpu",
    warmup_passes: int = 3,
) -> str:
    """
    Generate a comprehensive, methodologically sound Markdown report comparing the models.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    m1_records = [r for r in records if r["model_name"] == model1_label]
    m2_records = [r for r in records if r["model_name"] == model2_label] if model2_label else []

    s1 = compute_benchmark_summary(m1_records)
    s2 = compute_benchmark_summary(m2_records) if m2_records else None

    lines: list[str] = []
    lines.append("# SHM-AI: Concrete Crack Segmentation Model Benchmark Report")
    lines.append("")
    lines.append(f"- **Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Evaluated Images Total:** {s1['total_images']} (Positive GT: {s1['positive_images_count']}, Negative GT: {s1['negative_images_count']}, Missing Labels: {s1['missing_label_images_count']})")
    lines.append("- **Confidence Threshold:** `0.25` (fixed for rigorous comparability)")
    lines.append(f"- **Inference Device:** `{device}` (Warm-up passes: `{warmup_passes}` excluded from timing)")
    lines.append("- **Timing Methodology:** `time.perf_counter()` on detector `predict()` after warm-up passes (excludes image I/O and skeleton morphology)")
    lines.append("- **Spatial Calibration:** Withheld (strictly pixel-space geometry; physical dimensions uncalibrated)")
    lines.append("")

    if missing_model2_msg:
        lines.append("> [!WARNING]")
        lines.append(f"> {missing_model2_msg}")
        lines.append("")

    lines.append("## 1. Executive Summary & Benchmark Comparison")
    lines.append("")
    lines.append("> [!NOTE]")
    lines.append("> **Metric Interpretation Clarification:**")
    lines.append("> - **Mask IoU & Dice:** Evaluated strictly on crack-positive images (`gt_area_px > 0`) using 2D union masks. These are image-level semantic overlap metrics, **not** COCO instance-level Average Precision (AP50 / mAP50-95).")
    lines.append("> - **Negative False Positive Rate:** Evaluated strictly on confirmed negative images (`gt_area_px == 0`).")
    lines.append("> - **Geometric Measurements:** Reported strictly in pixel units (`px`) for images with valid detections. Without independently measured physical ground-truth calipers, differences in length/width reflect segmentation boundary morphology, **not** verified physical measurement accuracy.")
    lines.append("")

    if s2:
        lines.append(f"| Metric | {model1_label} | {model2_label} | Delta (M2 - M1) |")
        lines.append("|---|---:|---:|---:|")
        lines.append(f"| **Positive GT Images** | {s1['positive_images_count']} | {s2['positive_images_count']} | - |")
        lines.append(f"| **Negative GT Images** | {s1['negative_images_count']} | {s2['negative_images_count']} | - |")
        lines.append(f"| **Mean Mask IoU (Positive GT only)** | {s1['mean_iou_positive_gt']:.4f} | {s2['mean_iou_positive_gt']:.4f} | {s2['mean_iou_positive_gt'] - s1['mean_iou_positive_gt']:+.4f} |")
        lines.append(f"| **Mean Mask Dice (Positive GT only)** | {s1['mean_dice_positive_gt']:.4f} | {s2['mean_dice_positive_gt']:.4f} | {s2['mean_dice_positive_gt'] - s1['mean_dice_positive_gt']:+.4f} |")
        lines.append(f"| **Negative Image False-Positive Count** | {s1['negative_fp_count']} / {s1['negative_images_count']} | {s2['negative_fp_count']} / {s2['negative_images_count']} | {s2['negative_fp_count'] - s1['negative_fp_count']:+d} |")
        lines.append(f"| **Negative Image False-Positive Rate** | {s1['negative_fp_rate']:.2%} | {s2['negative_fp_rate']:.2%} | {s2['negative_fp_rate'] - s1['negative_fp_rate']:+.2%} |")
        lines.append(f"| **Mean Detections / Img (Positive GT)** | {s1['mean_det_count_positive']:.2f} | {s2['mean_det_count_positive']:.2f} | {s2['mean_det_count_positive'] - s1['mean_det_count_positive']:+.2f} |")
        lines.append(f"| **Images with Valid Detections** | {s1['images_with_valid_detections']} / {s1['total_images']} | {s2['images_with_valid_detections']} / {s2['total_images']} | {s2['images_with_valid_detections'] - s1['images_with_valid_detections']:+d} |")
        lines.append(f"| **Mean Mask Area (px, Valid Detections)** | {s1['mean_area_detected_px']:.1f} px | {s2['mean_area_detected_px']:.1f} px | {s2['mean_area_detected_px'] - s1['mean_area_detected_px']:+.1f} px |")
        lines.append(f"| **Mean Skeleton Length (px, Valid Detections)** | {s1['mean_length_detected_px']:.1f} px | {s2['mean_length_detected_px']:.1f} px | {s2['mean_length_detected_px'] - s1['mean_length_detected_px']:+.1f} px |")
        lines.append(f"| **Mean Crack Width (px, Valid Detections)** | {s1['mean_width_detected_px']:.2f} px | {s2['mean_width_detected_px']:.2f} px | {s2['mean_width_detected_px'] - s1['mean_width_detected_px']:+.2f} px |")
        lines.append(f"| **Max Crack Width (px)** | {s1['max_width_px']:.2f} px | {s2['max_width_px']:.2f} px | {s2['max_width_px'] - s1['max_width_px']:+.2f} px |")
        lines.append(f"| **Mean Latency (ms, post-warmup)** | {s1['latency_mean_ms']:.1f} ms | {s2['latency_mean_ms']:.1f} ms | {s2['latency_mean_ms'] - s1['latency_mean_ms']:+.1f} ms |")
        lines.append(f"| **Median Latency (ms, post-warmup)** | {s1['latency_median_ms']:.1f} ms | {s2['latency_median_ms']:.1f} ms | {s2['latency_median_ms'] - s1['latency_median_ms']:+.1f} ms |")
        lines.append(f"| **p95 Latency (ms, post-warmup)** | {s1['latency_p95_ms']:.1f} ms | {s2['latency_p95_ms']:.1f} ms | {s2['latency_p95_ms'] - s1['latency_p95_ms']:+.1f} ms |")
        lines.append(f"| **Missed Cracks Heuristic ($FN_{{heuristic}}$)** | {s1['missed_cracks_heuristic_count']} | {s2['missed_cracks_heuristic_count']} | {s2['missed_cracks_heuristic_count'] - s1['missed_cracks_heuristic_count']:+d} |")
        lines.append(f"| **Fragmentation Proxy ($N_{{proxy}}$)** | {s1['fragmentation_proxy_count']} | {s2['fragmentation_proxy_count']} | {s2['fragmentation_proxy_count'] - s1['fragmentation_proxy_count']:+d} |")
        lines.append(f"| **Suspiciously Broad Masks Heuristic ($N_{{broad}}$)** | {s1['broad_masks_heuristic_count']} | {s2['broad_masks_heuristic_count']} | {s2['broad_masks_heuristic_count'] - s1['broad_masks_heuristic_count']:+d} |")
    else:
        lines.append(f"| Metric | {model1_label} (Baseline) |")
        lines.append("|---|---:|")
        lines.append(f"| **Positive GT Images** | {s1['positive_images_count']} |")
        lines.append(f"| **Negative GT Images** | {s1['negative_images_count']} |")
        lines.append(f"| **Mean Mask IoU (Positive GT only)** | {s1['mean_iou_positive_gt']:.4f} |")
        lines.append(f"| **Mean Mask Dice (Positive GT only)** | {s1['mean_dice_positive_gt']:.4f} |")
        lines.append(f"| **Negative Image False-Positive Count** | {s1['negative_fp_count']} / {s1['negative_images_count']} |")
        lines.append(f"| **Negative Image False-Positive Rate** | {s1['negative_fp_rate']:.2%} |")
        lines.append(f"| **Mean Detections / Img (Positive GT)** | {s1['mean_det_count_positive']:.2f} |")
        lines.append(f"| **Images with Valid Detections** | {s1['images_with_valid_detections']} / {s1['total_images']} |")
        lines.append(f"| **Images without Detections** | {s1['images_without_detections']} / {s1['total_images']} |")
        lines.append(f"| **Mean Mask Area (px, Valid Detections)** | {s1['mean_area_detected_px']:.1f} px |")
        lines.append(f"| **Mean Skeleton Length (px, Valid Detections)** | {s1['mean_length_detected_px']:.1f} px |")
        lines.append(f"| **Mean Crack Width (px, Valid Detections)** | {s1['mean_width_detected_px']:.2f} px |")
        lines.append(f"| **Max Crack Width (px)** | {s1['max_width_px']:.2f} px |")
        lines.append(f"| **Mean Latency (ms, post-warmup)** | {s1['latency_mean_ms']:.1f} ms |")
        lines.append(f"| **Median Latency (ms, post-warmup)** | {s1['latency_median_ms']:.1f} ms |")
        lines.append(f"| **p95 Latency (ms, post-warmup)** | {s1['latency_p95_ms']:.1f} ms |")
        lines.append(f"| **Missed Cracks Heuristic ($FN_{{heuristic}}$)** | {s1['missed_cracks_heuristic_count']} / {s1['positive_images_count']} |")
        lines.append(f"| **Fragmentation Proxy ($N_{{proxy}}$)** | {s1['fragmentation_proxy_count']} |")
        lines.append(f"| **Suspiciously Broad Masks Heuristic ($N_{{broad}}$)** | {s1['broad_masks_heuristic_count']} |")
    lines.append("")

    lines.append("## 2. Failure Mode & Heuristic Anomaly Analysis")
    lines.append("")
    lines.append("### A. Fragmentation Proxy")
    lines.append("- **Definition & Limitation:** A detection-count screening heuristic that flags images where ground truth has $\\le 2$ polygons but the model outputs $\\ge 3$ detections. It does **not** prove true topological fragmentation or disconnected centerline breaks.")
    lines.append(f"- **{model1_label}:** {s1['fragmentation_proxy_count']} image(s) flagged.")
    if s2:
        lines.append(f"- **{model2_label}:** {s2['fragmentation_proxy_count']} image(s) flagged.")
    lines.append("")

    lines.append("### B. Missed Cracks Heuristic (False Negatives)")
    lines.append("- **Criterion:** Ground-truth crack exists (`gt_area_px > 0`) and model returned 0 detections or achieved mask IoU $< 0.01$.")
    lines.append(f"- **{model1_label}:** {s1['missed_cracks_heuristic_count']} image(s) missed.")
    if s2:
        lines.append(f"- **{model2_label}:** {s2['missed_cracks_heuristic_count']} image(s) missed.")
    lines.append("")

    lines.append("### C. Suspiciously Broad Masks Heuristic")
    lines.append("- **Definition & Limitation:** A morphological screening heuristic flagging instances where mean width $> 25.0$ px, max width $> 50.0$ px, or area/length $> 25.0$. It highlights potential boundary over-segmentation or shadow inclusion, but is **not** a confirmed diagnostic false positive.")
    lines.append(f"- **{model1_label}:** {s1['broad_masks_heuristic_count']} instance(s) flagged.")
    if s2:
        lines.append(f"- **{model2_label}:** {s2['broad_masks_heuristic_count']} instance(s) flagged.")
    lines.append("")

    lines.append("## 3. Physical Dimension Calibration Safeguards")
    lines.append("")
    lines.append("> [!IMPORTANT]")
    lines.append("> All physical dimensions (millimeters, square millimeters) are strictly withheld.")
    lines.append("> Under SHM-AI safety protocols, converting pixels to physical units requires a validated optical reference, checkerboard target, or laser distance sensor. Fabricating real-world metrics from uncalibrated photographs is prohibited.")
    lines.append("")

    lines.append("## 4. Dataset Limitations & Methodological Scope")
    lines.append("")
    lines.append("1. **Held-Out Test Set Scope:**")
    lines.append("   - The held-out test set consists of 112 images that are crack-positive. While effective for initial segmentation boundary testing, 112 images is a small sample size that cannot capture all environmental variations (varying concrete textures, lighting conditions, aggregate patterns, wet surfaces).")
    lines.append("2. **Candidate Negative Benchmark Notice:**")
    lines.append("   - Candidate negative images from the benchmark directory are drawn from uncurated field captures; they are not all independently verified by licensed structural inspectors as guaranteed crack-free. False positive rates reported on candidate negative sets must therefore be interpreted with caution.")
    lines.append("3. **Instance-level AP vs Union-Mask Metrics:**")
    lines.append("   - The metrics reported here evaluate pixel-level union mask overlap (semantic segmentation proxy), NOT COCO instance-level Average Precision (AP50, AP50-95), which requires bipartite matching and precision-recall curve integration across IoU thresholds.")
    lines.append("4. **No Definitive Production Decision:**")
    lines.append("   - This evaluation script provides exploratory comparative metrics between model architectures. No definitive production-model promotion, replacement, or deployment decision should be made based solely on this custom offline script without comprehensive field testing, multi-class verification, and domain validation.")
    lines.append("")

    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")
    return content


def run_benchmark(
    model1_path: Path,
    model2_path: Path | None,
    images_dir: Path,
    labels_dir: Path,
    output_dir: Path,
    conf_threshold: float = 0.25,
    allow_single_model: bool = False,
    device: str = "cpu",
    warmup_passes: int = 3,
) -> int:
    """
    Execute the evaluation benchmark and write reports.
    """
    effective_m2_path = model2_path or (PROJECT_ROOT / "weights" / "yolo26n-seg.pt")
    can_proceed, diag_msg = verify_checkpoints(model1_path, effective_m2_path, allow_single_model)
    print(diag_msg)

    if not can_proceed:
        return 1

    # Discover test images
    extensions = {".jpg", ".jpeg", ".png", ".bmp"}
    image_paths = sorted([p for p in images_dir.iterdir() if p.suffix.lower() in extensions])
    if not image_paths:
        print(f"Error: No test images found in '{images_dir}'.")
        return 1

    print(f"\nDiscovered {len(image_paths)} test images in '{images_dir}'.")
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "yolo11_vs_yolo26_comparison.csv"
    report_path = output_dir / "yolo11_vs_yolo26_report.md"

    # Evaluate Model 1
    m1_label = "YOLO11n-seg (Fine-tuned 15e)"
    print(f"\n[1/2] Loading {m1_label} from '{model1_path}'...")
    m1_detector = YOLO11Detector(model_path=model1_path, device=device, default_conf=conf_threshold)
    print(f"Running evaluation on {len(image_paths)} images at conf={conf_threshold} (warmup={warmup_passes})...")
    records_m1 = evaluate_model_on_dataset(
        detector=m1_detector,
        model_label=m1_label,
        image_paths=image_paths,
        labels_dir=labels_dir,
        conf_threshold=conf_threshold,
        warmup_passes=warmup_passes,
    )

    all_records = list(records_m1)
    m2_label = None
    missing_msg = None

    if effective_m2_path.is_file():
        m2_label = "YOLO26n-seg"
        print(f"\n[2/2] Loading {m2_label} from '{effective_m2_path}'...")
        m2_detector = YOLO11Detector(model_path=effective_m2_path, device=device, default_conf=conf_threshold)
        print(f"Running evaluation on {len(image_paths)} images at conf={conf_threshold} (warmup={warmup_passes})...")
        records_m2 = evaluate_model_on_dataset(
            detector=m2_detector,
            model_label=m2_label,
            image_paths=image_paths,
            labels_dir=labels_dir,
            conf_threshold=conf_threshold,
            warmup_passes=warmup_passes,
        )
        all_records.extend(records_m2)
    else:
        missing_msg = (
            f"YOLO26 weights not found at expected path `{effective_m2_path}`. "
            "Benchmarked YOLO11 baseline only."
        )

    # Save CSV
    save_results_csv(all_records, csv_path)
    print(f"\nSaved CSV results to: {csv_path.resolve()}")

    # Save Markdown report
    generate_markdown_report(
        records=all_records,
        model1_label=m1_label,
        model2_label=m2_label,
        output_path=report_path,
        missing_model2_msg=missing_msg,
        device=device,
        warmup_passes=warmup_passes,
    )
    print(f"Saved Markdown report to: {report_path.resolve()}\n")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SHM-AI: Validate YOLO11 vs YOLO26 Crack Measurements & Morphological Metrics"
    )
    parser.add_argument(
        "--model1",
        type=Path,
        default=PROJECT_ROOT / "weights" / "shm_ai_crack_seg_finetune_15e_best.pt",
        help="Path to Model 1 weights (fine-tuned YOLO11)",
    )
    parser.add_argument(
        "--model2",
        type=Path,
        default=PROJECT_ROOT / "weights" / "yolo26n-seg.pt",
        help="Path to Model 2 weights (YOLO26-seg candidate)",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=PROJECT_ROOT / "datasets" / "prepared_crack_seg_v1" / "images" / "test",
        help="Directory containing held-out test images",
    )
    parser.add_argument(
        "--labels-dir",
        type=Path,
        default=PROJECT_ROOT / "datasets" / "prepared_crack_seg_v1" / "labels" / "test",
        help="Directory containing YOLO polygon test labels",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "runs" / "benchmark",
        help="Directory to save CSV and Markdown report",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Inference confidence threshold (default: 0.25)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Compute target device ('cpu', 'cuda', 'auto')",
    )
    parser.add_argument(
        "--allow-single-model",
        action="store_true",
        help="Allow running Model 1 alone if Model 2 checkpoint is absent",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=3,
        help="Number of initial warm-up inference iterations to exclude from latency statistics (default: 3)",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = parse_args()
    code = run_benchmark(
        model1_path=args.model1,
        model2_path=args.model2,
        images_dir=args.images_dir,
        labels_dir=args.labels_dir,
        output_dir=args.output_dir,
        conf_threshold=args.conf,
        allow_single_model=args.allow_single_model,
        device=args.device,
        warmup_passes=args.warmup,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
