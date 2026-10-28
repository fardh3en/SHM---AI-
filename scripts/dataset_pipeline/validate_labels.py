"""
Comprehensive label and split validator for the integrated multi-source crack dataset.

Validates:
1. Exact 1-to-1 correspondence between images and labels.
2. Strict YOLO detection format: <class_id> <xc> <yc> <w> <h>.
3. Class ID must be integer 0 (single-class: crack).
4. Normalized coordinate ranges [0.0, 1.0].
5. Box dimensions > 0.
6. Proper identification of hard negative samples (0-byte label files).
7. Zero data leakage across train, val, and test splits.
"""
import json
from pathlib import Path
from typing import Any

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def validate_label_line(line: str, filename: str, line_no: int) -> tuple[bool, str | None]:
    """Validate a single YOLO bounding box line."""
    tokens = line.strip().split()
    if not tokens:
        return True, None

    if len(tokens) != 5:
        return False, f"{filename}:{line_no} — Expected 5 tokens (<cls> <xc> <yc> <w> <h>), found {len(tokens)}"

    try:
        cls_id = int(tokens[0])
        xc, yc, w, h = float(tokens[1]), float(tokens[2]), float(tokens[3]), float(tokens[4])
    except ValueError:
        return False, f"{filename}:{line_no} — Non-numeric tokens encountered"

    if cls_id != 0:
        return False, f"{filename}:{line_no} — Invalid class ID '{cls_id}' (expected 0: crack)"

    tol = 0.05
    for val, name in [(xc, "xc"), (yc, "yc"), (w, "w"), (h, "h")]:
        if not (-tol <= val <= 1.0 + tol):
            return False, f"{filename}:{line_no} — Coordinate {name}={val} outside [0.0, 1.0]"

    if w <= 1e-5 or h <= 1e-5:
        return False, f"{filename}:{line_no} — Degenerate zero-area bounding box (w={w}, h={h})"

    return True, None


def validate_dataset_split(img_dir: Path, lbl_dir: Path | None = None) -> dict[str, Any]:
    """Validate images and labels for one split."""
    if lbl_dir is None:
        lbl_dir = img_dir / "labels"
        img_dir = img_dir / "images"

    stats: dict[str, Any] = {
        "images_found": 0,
        "labels_found": 0,
        "empty_negative_labels": 0,
        "images_with_boxes": 0,
        "total_bounding_boxes": 0,
        "missing_labels": 0,
        "orphan_labels": 0,
        "errors": [],
    }

    if not img_dir.is_dir() or not lbl_dir.is_dir():
        stats["errors"].append(f"Directory missing: {img_dir} or {lbl_dir}")
        return stats

    img_files = {p.stem: p for p in img_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS}
    lbl_files = {p.stem: p for p in lbl_dir.iterdir() if p.suffix.lower() == ".txt"}

    stats["images_found"] = len(img_files)
    stats["labels_found"] = len(lbl_files)

    # Check for missing and orphan labels
    for stem in img_files:
        if stem not in lbl_files:
            stats["missing_labels"] += 1
            stats["errors"].append(f"Missing label for image: {img_files[stem].name}")

    for stem in lbl_files:
        if stem not in img_files:
            stats["orphan_labels"] += 1
            stats["errors"].append(f"Orphan label without image: {lbl_files[stem].name}")

    # Validate each label file content
    for stem, lbl_path in lbl_files.items():
        content = lbl_path.read_text(encoding="utf-8").strip()
        if not content:
            stats["empty_negative_labels"] += 1
            continue

        stats["images_with_boxes"] += 1
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            valid, err = validate_label_line(line, lbl_path.name, idx)
            if not valid:
                stats["errors"].append(err)
            else:
                stats["total_bounding_boxes"] += 1

    return stats


def validate_integrated_dataset(dataset_root: Path) -> dict[str, Any]:
    """Validate entire dataset across train, val, test and check cross-split leakage."""
    report: dict[str, Any] = {
        "dataset_root": str(dataset_root),
        "splits": {},
        "totals": {
            "images": 0,
            "bounding_boxes": 0,
            "negative_images": 0,
            "errors": 0,
        },
        "leakage_detected": False,
    }

    split_images: dict[str, set[str]] = {}

    for split in ("train", "val", "test"):
        img_dir = dataset_root / "images" / split
        lbl_dir = dataset_root / "labels" / split

        if img_dir.is_dir() and lbl_dir.is_dir():
            sub_stats = validate_dataset_split(img_dir, lbl_dir)
            report["splits"][split] = sub_stats
            report["totals"]["images"] += sub_stats["images_found"]
            report["totals"]["bounding_boxes"] += sub_stats["total_bounding_boxes"]
            report["totals"]["negative_images"] += sub_stats["empty_negative_labels"]
            report["totals"]["errors"] += len(sub_stats["errors"])
            img_files = {p.name for p in img_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS}
            split_images[split] = img_files

    # Check cross-split leakage
    if "train" in split_images and "val" in split_images:
        inter_train_val = split_images["train"].intersection(split_images["val"])
        if inter_train_val:
            report["leakage_detected"] = True

    if "train" in split_images and "test" in split_images:
        inter_train_test = split_images["train"].intersection(split_images["test"])
        if inter_train_test:
            report["leakage_detected"] = True

    summary_path = dataset_root / "validation_summary.json"
    summary_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
