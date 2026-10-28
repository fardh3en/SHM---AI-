"""
Automated preparation, validation, and smoke-test subset generator for the
Ultralytics Crack Segmentation dataset (crack-seg).

Dataset Documentation:
    https://docs.ultralytics.com/datasets/segment/crack-seg/

Features:
1. Available disk space pre-flight check (> 1.5 GB recommended).
2. Resilient download with transient retry, backoff, and temporary .part file handling.
3. Zip archive structural and CRC integrity verification before extraction.
4. Preserves original train, val, and test splits in datasets/crack-seg/.
5. Strict validation of image files, label correspondence, class IDs, and normalized polygon coordinates.
6. Explicit distinction between missing labels and empty labels (negative background samples).
7. Reproducible 10-image smoke-test dataset generation in datasets/crack-smoke/.
8. Exports comprehensive validation metrics and audit report.

Usage:
    python scripts/prepare_crack_dataset.py
    python scripts/prepare_crack_dataset.py --skip-download  # If zip already present
    python scripts/prepare_crack_dataset.py --validate-only  # Run validation on existing dataset
"""
import argparse
import http.client
import json
import logging
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Upstream Dataset Source & Metadata
DATASET_NAME = "crack-seg"
DATASET_SOURCE_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/crack-seg.zip"
DATASET_DOCS_URL = "https://docs.ultralytics.com/datasets/segment/crack-seg/"
DATASET_LICENSE = "AGPL-3.0 (Ultralytics Open Source License)"
MIN_FREE_DISK_BYTES = 1_500_000_000  # 1.5 GB

# Valid image extensions recognized by YOLO
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("prepare_crack_dataset")


class InsufficientDiskSpaceError(RuntimeError):
    """Raised when available free disk space is below required threshold."""
    pass


class DatasetIntegrityError(IOError):
    """Raised when downloaded dataset archive is corrupted or invalid."""
    pass


@dataclass
class AnnotationIssue:
    file: str
    line_number: int
    issue_type: str
    details: str


@dataclass
class SplitValidationStats:
    split_name: str
    total_images: int = 0
    valid_images: int = 0
    corrupt_images: int = 0
    images_with_labels: int = 0
    empty_label_files: int = 0  # Valid negative samples without cracks
    missing_label_files: int = 0  # Image has no corresponding .txt file
    orphan_label_files: int = 0  # .txt exists without matching image
    total_polygon_instances: int = 0
    class_id_counts: dict[int, int] = field(default_factory=dict)
    issues: list[AnnotationIssue] = field(default_factory=list)


def check_free_disk_space(target_path: Path, min_bytes: int = MIN_FREE_DISK_BYTES) -> int:
    """
    Check if the drive hosting target_path has at least min_bytes of free space.
    
    Returns:
        free_bytes (int)
    Raises:
        InsufficientDiskSpaceError: if free space is less than min_bytes.
    """
    target_path.mkdir(parents=True, exist_ok=True)
    total, used, free = shutil.disk_usage(target_path)
    if free < min_bytes:
        free_mb = free / (1024 * 1024)
        req_mb = min_bytes / (1024 * 1024)
        raise InsufficientDiskSpaceError(
            f"Insufficient disk space on {target_path}. "
            f"Available: {free_mb:.1f} MB, Required: {req_mb:.1f} MB."
        )
    return free


def _is_transient_error(exc: Exception) -> bool:
    """Classify transient network errors eligible for retry."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (408, 429, 500, 502, 503, 504)
    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead)):
        return True
    return False


def download_dataset_archive(
    url: str = DATASET_SOURCE_URL,
    dest_path: Path | None = None,
    max_retries: int = 3,
    timeout_seconds: float = 60.0,
) -> Path:
    """
    Download dataset zip archive with bounded retries and exponential backoff.
    Uses atomic temporary .part file to avoid leaving truncated archives.
    """
    if dest_path is None:
        dest_path = PROJECT_ROOT / "datasets" / "crack-seg.zip"

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dest_path.is_file() and zipfile.is_zipfile(dest_path):
        logger.info(f"Valid dataset archive already exists at '{dest_path}' ({dest_path.stat().st_size:,} bytes).")
        return dest_path

    part_path = dest_path.with_name(f"{dest_path.name}.part")
    max_attempts = max_retries + 1

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Downloading dataset archive from {url} (attempt {attempt}/{max_attempts})...")
        try:
            if part_path.exists():
                part_path.unlink()

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "SHM-AI-Dataset-Prep/1.0 (+https://github.com/fardh3en/SHM---AI-)"},
            )

            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                total_size_hdr = response.headers.get("Content-Length")
                total_size = int(total_size_hdr) if total_size_hdr and total_size_hdr.isdigit() else -1

                downloaded = 0
                chunk_size = 256 * 1024  # 256 KB
                with open(part_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = min(100.0, (downloaded / total_size) * 100)
                            sys.stdout.write(f"\rProgress: {pct:.1f}% ({downloaded:,} / {total_size:,} bytes)")
                            sys.stdout.flush()

                if total_size > 0:
                    sys.stdout.write("\n")

            # Verify downloaded file is a valid zip before promoting
            if not zipfile.is_zipfile(part_path):
                raise DatasetIntegrityError(f"Downloaded payload at '{part_path}' is not a valid zip archive.")

            # Test zip archive integrity (reads all headers and CRC32 checksums)
            with zipfile.ZipFile(part_path, "r") as zf:
                bad_file = zf.testzip()
                if bad_file:
                    raise DatasetIntegrityError(f"Zip CRC corrupted on file '{bad_file}' in '{part_path}'")

            part_path.replace(dest_path)
            logger.info(f"Dataset archive successfully verified on disk: '{dest_path}' ({dest_path.stat().st_size:,} bytes).")
            return dest_path

        except Exception as exc:
            logger.warning(f"Download attempt {attempt}/{max_attempts} failed: {exc}")
            if part_path.exists():
                try:
                    part_path.unlink()
                except OSError:
                    pass

            if not _is_transient_error(exc) or attempt == max_attempts:
                raise

            sleep_time = min(30.0, 2.0 ** (attempt - 1))
            logger.info(f"Retrying in {sleep_time:.1f}s...")
            time.sleep(sleep_time)

    raise DatasetIntegrityError(f"Failed to download valid dataset archive after {max_attempts} attempts.")


def extract_dataset_archive(archive_path: Path, target_dir: Path) -> Path:
    """
    Extract zip archive to target directory, ensuring images/ and labels/ are directly
    under target_dir (stripping any redundant top-level directory like 'crack-seg/').
    Guards against directory traversal (Zip Slip).
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Extracting '{archive_path}' into '{target_dir}'...")

    with zipfile.ZipFile(archive_path, "r") as zf:
        members = zf.infolist()
        logger.info(f"Archive contains {len(members):,} files/directories.")

        # Determine if all non-empty entries share a single top-level directory prefix
        non_empty_names = [m.filename.replace("\\", "/") for m in members if m.filename.strip("/\\")]
        top_dirs = {name.split("/")[0] for name in non_empty_names if "/" in name}
        has_single_top_dir = len(top_dirs) == 1 and all(
            name.startswith(f"{list(top_dirs)[0]}/") for name in non_empty_names
        )

        top_dir_prefix = f"{list(top_dirs)[0]}/" if has_single_top_dir else ""

        for member in members:
            rel_path = member.filename.replace("\\", "/")
            if top_dir_prefix and rel_path.startswith(top_dir_prefix):
                rel_path = rel_path[len(top_dir_prefix):]

            if not rel_path:
                continue

            target_file = target_dir / rel_path
            # Prevent Zip Slip directory traversal vulnerability
            if not str(target_file.resolve()).startswith(str(target_dir.resolve())):
                raise DatasetIntegrityError(f"Zip Slip security issue detected in member: {member.filename}")

            if member.is_dir() or member.filename.endswith("/"):
                target_file.mkdir(parents=True, exist_ok=True)
            else:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target_file, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    logger.info(f"Dataset extracted cleanly to '{target_dir}'.")
    return target_dir


def validate_polygon_line(line: str, line_no: int, filename: str) -> tuple[bool, int | None, list[tuple[float, float]] | None, AnnotationIssue | None]:
    """
    Validate a single line of a YOLO segmentation label file.

    Format: <class_id> <x1> <y1> <x2> <y2> ... <xn> <yn>
    All coordinates must be normalized to [0.0, 1.0].
    Minimum 3 vertices (6 coordinate values) are required for a polygon.

    Returns:
        (is_valid, class_id, list_of_points, issue_or_none)
    """
    raw = line.strip()
    if not raw:
        return True, None, None, None

    tokens = raw.split()
    if len(tokens) < 7:
        issue = AnnotationIssue(
            file=filename,
            line_number=line_no,
            issue_type="too_few_coordinates",
            details=f"Line has {len(tokens)} tokens; minimum 7 tokens required (1 class ID + >= 3 (x,y) pairs).",
        )
        return False, None, None, issue

    try:
        class_id = int(tokens[0])
    except ValueError:
        issue = AnnotationIssue(
            file=filename,
            line_number=line_no,
            issue_type="invalid_class_id",
            details=f"Class ID '{tokens[0]}' is not an integer.",
        )
        return False, None, None, issue

    coord_tokens = tokens[1:]
    if len(coord_tokens) % 2 != 0:
        issue = AnnotationIssue(
            file=filename,
            line_number=line_no,
            issue_type="odd_coordinate_count",
            details=f"Coordinate count {len(coord_tokens)} is odd; must contain (x, y) pairs.",
        )
        return False, class_id, None, issue

    points: list[tuple[float, float]] = []
    # Small tolerance for floating point representations slightly beyond [0, 1] e.g. 1.00001
    tol = 0.05
    for i in range(0, len(coord_tokens), 2):
        try:
            x = float(coord_tokens[i])
            y = float(coord_tokens[i + 1])
        except ValueError:
            issue = AnnotationIssue(
                file=filename,
                line_number=line_no,
                issue_type="non_numeric_coordinate",
                details=f"Coordinates '{coord_tokens[i]}', '{coord_tokens[i+1]}' cannot be parsed as floats.",
            )
            return False, class_id, None, issue

        if not (-tol <= x <= 1.0 + tol and -tol <= y <= 1.0 + tol):
            issue = AnnotationIssue(
                file=filename,
                line_number=line_no,
                issue_type="unnormalized_coordinate",
                details=f"Point ({x}, {y}) is outside valid normalized range [-0.05, 1.05].",
            )
            return False, class_id, None, issue

        # Clamp into strict [0.0, 1.0]
        points.append((max(0.0, min(1.0, x)), max(0.0, min(1.0, y))))

    return True, class_id, points, None


def is_image_readable(image_path: Path) -> bool:
    """Verify that an image file can be opened and decoded without corruption."""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            img.verify()
        return True
    except Exception:
        return False


def validate_split(
    dataset_root: Path,
    split: str,
) -> SplitValidationStats:
    """
    Validate all images and label files for a specific dataset split (train, val, or test).
    """
    stats = SplitValidationStats(split_name=split)
    img_dir = dataset_root / "images" / split
    lbl_dir = dataset_root / "labels" / split

    if not img_dir.is_dir():
        logger.warning(f"Images directory missing for split '{split}': {img_dir}")
        return stats

    image_files = sorted([p for p in img_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS])
    stats.total_images = len(image_files)

    label_files_found: set[str] = set()
    if lbl_dir.is_dir():
        label_files_found = {p.stem for p in lbl_dir.iterdir() if p.suffix.lower() == ".txt"}

    image_stems = {p.stem for p in image_files}

    # 1. Check for orphan labels (label exists without corresponding image)
    for lbl_stem in label_files_found:
        if lbl_stem not in image_stems:
            stats.orphan_label_files += 1
            stats.issues.append(
                AnnotationIssue(
                    file=f"{lbl_stem}.txt",
                    line_number=0,
                    issue_type="orphan_label",
                    details=f"Label file exists in labels/{split} without matching image in images/{split}.",
                )
            )

    # 2. Iterate and validate each image and its corresponding label
    for img_path in image_files:
        stem = img_path.stem
        if not is_image_readable(img_path):
            stats.corrupt_images += 1
            stats.issues.append(
                AnnotationIssue(
                    file=img_path.name,
                    line_number=0,
                    issue_type="corrupt_image",
                    details="Image file cannot be decoded by PIL/imaging library.",
                )
            )
            continue

        stats.valid_images += 1
        lbl_path = lbl_dir / f"{stem}.txt"

        if not lbl_path.is_file():
            stats.missing_label_files += 1
            continue

        stats.images_with_labels += 1
        try:
            content = lbl_path.read_text(encoding="utf-8").strip()
        except Exception as read_err:
            stats.issues.append(
                AnnotationIssue(
                    file=lbl_path.name,
                    line_number=0,
                    issue_type="unreadable_label_file",
                    details=f"Cannot read label file: {read_err}",
                )
            )
            continue

        if not content:
            # Empty label file = valid negative background sample
            stats.empty_label_files += 1
            continue

        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            valid, cls_id, _, issue = validate_polygon_line(line, idx, lbl_path.name)
            if not valid and issue:
                stats.issues.append(issue)
            elif cls_id is not None:
                stats.total_polygon_instances += 1
                stats.class_id_counts[cls_id] = stats.class_id_counts.get(cls_id, 0) + 1

    return stats


def create_smoke_test_subset(
    dataset_root: Path,
    target_root: Path,
    num_train: int = 6,
    num_val: int = 2,
    num_test: int = 2,
) -> dict[str, Any]:
    """
    Generate an isolated 10-image mini smoke-test dataset in target_root.
    Preserves original dataset integrity by copying valid samples.
    """
    target_root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "dataset_name": "crack-smoke",
        "description": "Deterministic 10-image mini dataset for fast CPU/pipeline smoke testing.",
        "samples": {"train": [], "val": [], "test": []},
    }

    plan = [
        ("train", num_train),
        ("val", num_val),
        ("test", num_test),
    ]

    for split, count in plan:
        src_img_dir = dataset_root / "images" / split
        src_lbl_dir = dataset_root / "labels" / split
        dst_img_dir = target_root / "images" / split
        dst_lbl_dir = target_root / "labels" / split

        dst_img_dir.mkdir(parents=True, exist_ok=True)
        dst_lbl_dir.mkdir(parents=True, exist_ok=True)

        if not src_img_dir.is_dir():
            continue

        # Find candidates that have non-empty labels with valid cracks
        candidates: list[Path] = []
        for img in sorted(src_img_dir.iterdir()):
            if img.suffix.lower() in IMAGE_EXTENSIONS:
                lbl = src_lbl_dir / f"{img.stem}.txt"
                if lbl.is_file() and lbl.stat().st_size > 10:
                    candidates.append(img)
                if len(candidates) >= count:
                    break

        # Fallback if candidates with labels are fewer than requested
        if len(candidates) < count:
            for img in sorted(src_img_dir.iterdir()):
                if img.suffix.lower() in IMAGE_EXTENSIONS and img not in candidates:
                    candidates.append(img)
                if len(candidates) >= count:
                    break

        for img in candidates[:count]:
            dst_img = dst_img_dir / img.name
            shutil.copy2(img, dst_img)

            src_lbl = src_lbl_dir / f"{img.stem}.txt"
            dst_lbl = dst_lbl_dir / f"{img.stem}.txt"
            if src_lbl.is_file():
                shutil.copy2(src_lbl, dst_lbl)
            else:
                dst_lbl.touch()

            manifest["samples"][split].append({
                "image": img.name,
                "label": dst_lbl.name,
                "has_annotation": src_lbl.is_file() and src_lbl.stat().st_size > 0,
            })

    # Generate YOLO configuration file for smoke dataset
    yaml_content = f"""# Ultralytics YOLO Smoke Dataset Configuration
# Generated automatically by scripts/prepare_crack_dataset.py
path: {target_root.resolve().as_posix()}
train: images/train
val: images/val
test: images/test

names:
  0: crack
"""
    yaml_path = target_root / "crack-smoke.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")
    manifest["yaml_path"] = str(yaml_path)

    return manifest


def generate_dataset_report(
    dataset_root: Path,
    stats_list: list[SplitValidationStats],
    smoke_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a structured summary report of dataset validation."""
    report = {
        "dataset_name": DATASET_NAME,
        "source_url": DATASET_SOURCE_URL,
        "documentation_url": DATASET_DOCS_URL,
        "license": DATASET_LICENSE,
        "dataset_root": str(dataset_root),
        "validation_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "splits": {},
        "totals": {
            "total_images": sum(s.total_images for s in stats_list),
            "valid_images": sum(s.valid_images for s in stats_list),
            "corrupt_images": sum(s.corrupt_images for s in stats_list),
            "images_with_labels": sum(s.images_with_labels for s in stats_list),
            "empty_label_files": sum(s.empty_label_files for s in stats_list),
            "missing_label_files": sum(s.missing_label_files for s in stats_list),
            "orphan_label_files": sum(s.orphan_label_files for s in stats_list),
            "total_polygon_instances": sum(s.total_polygon_instances for s in stats_list),
            "total_annotation_issues": sum(len(s.issues) for s in stats_list),
        },
        "smoke_test_subset": smoke_manifest,
    }

    for s in stats_list:
        report["splits"][s.split_name] = asdict(s)

    report_path = dataset_root / "dataset_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info(f"Dataset validation report saved to '{report_path}'.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Download, validate, and prepare Ultralytics crack-seg dataset.")
    parser.add_argument("--skip-download", action="store_true", help="Skip download if archive or dataset directory already exists.")
    parser.add_argument("--validate-only", action="store_true", help="Run validation only on existing extracted dataset.")
    args = parser.parse_args()

    datasets_dir = PROJECT_ROOT / "datasets"
    target_extract_dir = datasets_dir / "crack-seg"
    smoke_extract_dir = datasets_dir / "crack-smoke"
    archive_path = datasets_dir / "crack-seg.zip"

    # 1. Pre-flight free disk space check
    free_bytes = check_free_disk_space(datasets_dir)
    logger.info(f"Pre-flight disk check: {free_bytes / (1024**3):.2f} GB free disk space available.")

    # 2. Download archive if needed
    if not args.validate_only and not args.skip_download:
        download_dataset_archive(dest_path=archive_path)

    # 3. Extract archive if needed
    dataset_root = target_extract_dir
    if not args.validate_only:
        if not (target_extract_dir / "images").is_dir() or not args.skip_download:
            if not archive_path.is_file():
                logger.error(f"Archive file not found at '{archive_path}'")
                return 1
            dataset_root = extract_dataset_archive(archive_path, target_extract_dir)

    # Verify directory structure
    if not (dataset_root / "images").is_dir():
        # Check if contents are nested inside crack-seg/crack-seg
        if (target_extract_dir / "crack-seg" / "images").is_dir():
            dataset_root = target_extract_dir / "crack-seg"
        else:
            logger.error(f"Cannot find 'images' directory in extracted dataset: {dataset_root}")
            return 1

    # 4. Validate each split
    splits = ["train", "val", "test"]
    stats_list: list[SplitValidationStats] = []
    print("\n" + "=" * 70)
    print("DATASET VALIDATION RUNNING".center(70))
    print("=" * 70)

    for split in splits:
        logger.info(f"Validating split: '{split}'...")
        stats = validate_split(dataset_root, split)
        stats_list.append(stats)
        print(f"Split [{split.upper()}]:")
        print(f"  - Images:               {stats.total_images:,} (Valid: {stats.valid_images:,}, Corrupt: {stats.corrupt_images})")
        print(f"  - Labels Found:         {stats.images_with_labels:,} (Empty/Negatives: {stats.empty_label_files:,}, Missing: {stats.missing_label_files})")
        print(f"  - Polygons:             {stats.total_polygon_instances:,}")
        print(f"  - Class Counts:         {stats.class_id_counts}")
        print(f"  - Annotation Issues:    {len(stats.issues)}")

    # 5. Generate 10-image smoke-test subset
    logger.info("Generating 10-image smoke-test subset in datasets/crack-smoke...")
    smoke_manifest = create_smoke_test_subset(dataset_root, smoke_extract_dir, num_train=6, num_val=2, num_test=2)
    print(f"\nSmoke-test subset generated: {smoke_manifest['yaml_path']}")
    print(f"  - Train: {len(smoke_manifest['samples']['train'])} images")
    print(f"  - Val:   {len(smoke_manifest['samples']['val'])} images")
    print(f"  - Test:  {len(smoke_manifest['samples']['test'])} images")

    # 6. Generate final report
    report = generate_dataset_report(dataset_root, stats_list, smoke_manifest)
    print("\n" + "=" * 70)
    print("FINAL SUMMARY REPORT".center(70))
    print("=" * 70)
    print(f"Dataset:              {report['dataset_name']}")
    print(f"Source URL:           {report['source_url']}")
    print(f"License:              {report['license']}")
    print(f"Total Images:         {report['totals']['total_images']:,}")
    print(f"Total Polygons:       {report['totals']['total_polygon_instances']:,}")
    print(f"Empty Labels:         {report['totals']['empty_label_files']:,} (negative samples)")
    print(f"Missing Labels:       {report['totals']['missing_label_files']}")
    print(f"Annotation Issues:    {report['totals']['total_annotation_issues']}")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
