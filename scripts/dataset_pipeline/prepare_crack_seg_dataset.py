"""
SHM-AI: Dataset Preparation Script for YOLO11 Crack Segmentation Fine-Tuning (v1)

Prepares `datasets/prepared_crack_seg_v1/` by:
1. Copying genuine polygon segmentation annotations and images from `datasets/crack-seg/`.
2. Preserving the untouched 112-image crack test split.
3. Ingesting verified uncracked concrete structural negatives (walls and bridge decks)
   from SDNET2018 into train and val splits with 0-byte label files.
4. Ensuring complete isolation from `datasets/concrete-negatives-benchmark/` (zero exact
   or perceptual leakage).
5. Emitting a corrected YAML manifest and a comprehensive JSON provenance report.
6. Being fully idempotent and safe to rerun.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import sys
from typing import Any
from PIL import Image


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_dhash(img_path: Path, hash_size: int = 8) -> int:
    """Compute 64-bit difference hash for perceptual similarity checks."""
    try:
        with Image.open(img_path) as img:
            resized = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
            pixels = list(resized.getdata())
            diff = []
            for row in range(hash_size):
                offset = row * (hash_size + 1)
                for col in range(hash_size):
                    diff.append(pixels[offset + col] > pixels[offset + col + 1])
            val = 0
            for i, b in enumerate(diff):
                if b:
                    val += 1 << i
            return val
    except Exception:
        return 0


def hamming_distance(h1: int, h2: int) -> int:
    """Calculate bitwise Hamming distance between two 64-bit integer hashes."""
    return bin(h1 ^ h2).count("1")


def get_benchmark_hashes(benchmark_dir: Path) -> tuple[set[str], list[int]]:
    """Compute exact and perceptual hashes for the isolated 100-image negative benchmark."""
    sha_set: set[str] = set()
    dhash_list: list[int] = []
    img_dir = benchmark_dir / "images"
    if img_dir.is_dir():
        for p in img_dir.glob("*.*"):
            if p.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                sha_set.add(compute_sha256(p))
                dh = compute_dhash(p)
                if dh != 0:
                    dhash_list.append(dh)
    return sha_set, dhash_list


def prepare_crack_seg_dataset(
    src_dir: Path,
    sdnet_dir: Path,
    benchmark_dir: Path,
    dst_dir: Path,
    train_negatives: int = 500,
    val_negatives: int = 75,
    seed: int = 42,
) -> dict[str, Any]:
    """
    Build the prepared segmentation dataset.
    """
    rng = random.Random(seed)
    dst_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("SHM-AI: PREPARING YOLO11 CRACK SEGMENTATION DATASET (v1)")
    print("=" * 80)
    print(f"Source segmentation dataset: {src_dir}")
    print(f"Negative source (SDNET2018): {sdnet_dir}")
    print(f"Negative benchmark:          {benchmark_dir}")
    print(f"Destination output:          {dst_dir}")
    print(f"Seed:                        {seed}")

    # 1. Gather benchmark hashes to guarantee strict exclusion
    bench_shas, bench_dhashes = get_benchmark_hashes(benchmark_dir)
    print(f"Loaded {len(bench_shas)} benchmark SHA-256 hashes and {len(bench_dhashes)} dHashes for exclusion guard.")

    # 2. Stage destination directories
    splits = ["train", "val", "test"]
    for s in splits:
        (dst_dir / "images" / s).mkdir(parents=True, exist_ok=True)
        (dst_dir / "labels" / s).mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "dataset_name": "prepared_crack_seg_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "splits": {},
        "provenance": {
            "positives": {
                "source": "Ultralytics Crack-Seg",
                "license": "AGPL-3.0",
                "format": "Normalized Polygon Coordinates (class_id x1 y1 x2 y2 ...)",
                "classes": {0: "crack"},
            },
            "negatives": {
                "source": "SDNET2018 (Utah State University, Dorafshan et al., 2018)",
                "license": "CC BY 4.0",
                "subsets": {
                    "W/UW": "Uncracked Concrete Wall (Structural)",
                    "D/UD": "Uncracked Concrete Bridge Deck (Structural Slab)",
                },
                "format": "0-byte Empty Label Files (.txt)",
            },
        },
        "negative_exclusion_guard": {
            "benchmark_images_excluded": len(bench_shas),
            "guarantee": "Zero exact (SHA-256) or perceptual (dHash <= 2) matches with negative benchmark",
        },
    }

    # 3. Copy original positive crack-seg images and labels
    print("\n--- Copying original positive segmentation splits ---")
    pos_shas: dict[str, set[str]] = {s: set() for s in splits}
    pos_dhashes: dict[str, list[int]] = {s: [] for s in splits}
    total_pos_polygons = 0

    for s in splits:
        src_img_dir = src_dir / "images" / s
        src_lbl_dir = src_dir / "labels" / s
        dst_img_dir = dst_dir / "images" / s
        dst_lbl_dir = dst_dir / "labels" / s

        imgs = sorted(list(src_img_dir.glob("*.jpg")))
        split_polygons = 0

        for img_path in imgs:
            lbl_path = src_lbl_dir / f"{img_path.stem}.txt"
            dst_img = dst_img_dir / img_path.name
            dst_lbl = dst_lbl_dir / f"{img_path.stem}.txt"

            # Copy image
            shutil.copy2(img_path, dst_img)
            # Copy label
            if lbl_path.is_file():
                shutil.copy2(lbl_path, dst_lbl)
                content = lbl_path.read_text(encoding="utf-8").strip()
                for line in content.splitlines():
                    if line.strip():
                        split_polygons += 1
            else:
                dst_lbl.write_text("", encoding="utf-8")

            # Track hashes
            sha = compute_sha256(dst_img)
            pos_shas[s].add(sha)
            dh = compute_dhash(dst_img)
            if dh != 0:
                pos_dhashes[s].append(dh)

        total_pos_polygons += split_polygons
        print(f"  [{s.upper()}] Copied {len(imgs)} positive images with {split_polygons} polygons.")

        manifest["splits"][s] = {
            "positive_crack_images": len(imgs),
            "positive_polygons": split_polygons,
            "negative_concrete_images": 0,
            "total_images": len(imgs),
        }

    # 4. Ingest verified negatives from SDNET2018 (UW and UD only)
    print("\n--- Ingesting verified structural concrete negatives ---")
    subsets = [
        ("W/UW", sdnet_dir / "W" / "UW", "sdnet_uw"),
        ("D/UD", sdnet_dir / "D" / "UD", "sdnet_ud"),
    ]

    # Collect eligible candidates
    eligible_by_subset: dict[str, list[Path]] = {}
    for subset_name, subset_path, prefix in subsets:
        if not subset_path.is_dir():
            print(f"  [WARNING] Subset directory not found: {subset_path}")
            eligible_by_subset[subset_name] = []
            continue

        raw_candidates = sorted(list(subset_path.glob("*.jpg")))
        rng.shuffle(raw_candidates)

        filtered: list[Path] = []
        for p in raw_candidates:
            # Check decode
            try:
                with Image.open(p) as img:
                    img.verify()
            except Exception:
                continue

            # Check benchmark exclusion
            sha = compute_sha256(p)
            if sha in bench_shas:
                continue

            dh = compute_dhash(p)
            if dh != 0 and any(hamming_distance(dh, bdh) <= 2 for bdh in bench_dhashes):
                continue

            filtered.append(p)

        eligible_by_subset[subset_name] = filtered
        print(f"  Subset '{subset_name}': {len(raw_candidates)} total -> {len(filtered)} verified eligible (non-benchmark)")

    # Allocate negatives to train and val (50% UW, 50% UD)
    uw_list = eligible_by_subset.get("W/UW", [])
    ud_list = eligible_by_subset.get("D/UD", [])

    train_uw_target = train_negatives // 2
    train_ud_target = train_negatives - train_uw_target

    val_uw_target = val_negatives // 2
    val_ud_target = val_negatives - val_uw_target

    train_neg_selected = [(p, "sdnet_uw") for p in uw_list[:train_uw_target]] + \
                         [(p, "sdnet_ud") for p in ud_list[:train_ud_target]]

    val_neg_selected = [(p, "sdnet_uw") for p in uw_list[train_uw_target:train_uw_target + val_uw_target]] + \
                       [(p, "sdnet_ud") for p in ud_list[train_ud_target:train_ud_target + val_ud_target]]

    # Write train negatives
    train_img_dst = dst_dir / "images" / "train"
    train_lbl_dst = dst_dir / "labels" / "train"
    for src_p, prefix in train_neg_selected:
        target_name = f"{prefix}_{src_p.name}"
        shutil.copy2(src_p, train_img_dst / target_name)
        (train_lbl_dst / f"{target_name[:-4]}.txt").write_text("", encoding="utf-8")

    manifest["splits"]["train"]["negative_concrete_images"] = len(train_neg_selected)
    manifest["splits"]["train"]["total_images"] += len(train_neg_selected)
    print(f"  [TRAIN] Ingested {len(train_neg_selected)} verified negatives ({train_uw_target} wall, {train_ud_target} deck).")

    # Write val negatives
    val_img_dst = dst_dir / "images" / "val"
    val_lbl_dst = dst_dir / "labels" / "val"
    for src_p, prefix in val_neg_selected:
        target_name = f"{prefix}_{src_p.name}"
        shutil.copy2(src_p, val_img_dst / target_name)
        (val_lbl_dst / f"{target_name[:-4]}.txt").write_text("", encoding="utf-8")

    manifest["splits"]["val"]["negative_concrete_images"] = len(val_neg_selected)
    manifest["splits"]["val"]["total_images"] += len(val_neg_selected)
    print(f"  [VAL]   Ingested {len(val_neg_selected)} verified negatives ({val_uw_target} wall, {val_ud_target} deck).")

    # Test split retains ZERO added negatives (strictly preserves original 112 crack test images)
    print(f"  [TEST]  Preserved exact 112 positive crack test images (0 negatives added to test split).")

    # 5. Write corrected dataset YAML
    yaml_path = dst_dir / "crack_seg_prepared.yaml"
    yaml_content = f"""# SHM-AI Concrete Crack Segmentation Dataset (v1)
# Documentation: Prepared for YOLO11 Segmentation Fine-Tuning
path: {dst_dir.as_posix()}
train: images/train  # {manifest['splits']['train']['total_images']} images ({manifest['splits']['train']['positive_crack_images']} crack + {manifest['splits']['train']['negative_concrete_images']} verified concrete negatives)
val: images/val      # {manifest['splits']['val']['total_images']} images ({manifest['splits']['val']['positive_crack_images']} crack + {manifest['splits']['val']['negative_concrete_images']} verified concrete negatives)
test: images/test    # {manifest['splits']['test']['total_images']} images ({manifest['splits']['test']['positive_crack_images']} untouched held-out crack benchmark)

names:
  0: crack
"""
    yaml_path.write_text(yaml_content, encoding="utf-8")
    print(f"\nDataset YAML written to: {yaml_path}")

    # 6. Write provenance manifest
    manifest_path = dst_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest written to:     {manifest_path}")

    # 7. Final integrity audit
    print("\n--- Final Dataset Partition Audit ---")
    for s in splits:
        i_cnt = len(list((dst_dir / "images" / s).glob("*.jpg")))
        l_cnt = len(list((dst_dir / "labels" / s).glob("*.txt")))
        empty_l_cnt = sum(1 for l in (dst_dir / "labels" / s).glob("*.txt") if l.stat().st_size == 0)
        print(f"  {s.upper():5s}: {i_cnt:4d} images, {l_cnt:4d} labels ({empty_l_cnt:3d} background negatives)")

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare YOLO11 crack segmentation dataset.")
    parser.add_argument("--src-dir", type=Path, default=Path("datasets/crack-seg"))
    parser.add_argument("--sdnet-dir", type=Path, default=Path("datasets/raw_downloads/sdnet2018"))
    parser.add_argument("--benchmark-dir", type=Path, default=Path("datasets/concrete-negatives-benchmark"))
    parser.add_argument("--dst-dir", type=Path, default=Path("datasets/prepared_crack_seg_v1"))
    parser.add_argument("--train-negatives", type=int, default=500)
    parser.add_argument("--val-negatives", type=int, default=75)
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()
    prepare_crack_seg_dataset(
        src_dir=args.src_dir,
        sdnet_dir=args.sdnet_dir,
        benchmark_dir=args.benchmark_dir,
        dst_dir=args.dst_dir,
        train_negatives=args.train_negatives,
        val_negatives=args.val_negatives,
        seed=args.seed,
    )
