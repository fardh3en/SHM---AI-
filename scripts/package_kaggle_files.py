"""Script to prepare clean Kaggle-ready packages for YOLO26 fine-tuning.

Creates:
1. shm_ai_prepared_crack_seg_v2.zip (train + val images/labels, manifest, and training YAML; strictly excludes test split)
2. shm_ai_yolo26n_seg_checkpoint.zip (starting weights shm_ai_yolo26n_seg_15e_best.pt)
"""

import os
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def package_dataset():
    dataset_dir = PROJECT_ROOT / "datasets" / "prepared_crack_seg_v2"
    output_zip = PROJECT_ROOT / "shm_ai_prepared_crack_seg_v2.zip"
    
    print(f"Packaging dataset from: {dataset_dir}")
    print(f"Target archive:         {output_zip}")

    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    # Prepare Kaggle-specific YAML without test split
    kaggle_yaml_content = """# SHM-AI Concrete Crack Segmentation Dataset (v2 - Kaggle Fine-Tuning)
# Excludes held-out test split to guarantee zero test leakage
path: .
train: images/train
val: images/val

names:
  0: crack
"""

    train_images = sorted((dataset_dir / "images" / "train").glob("*.jpg"))
    val_images = sorted((dataset_dir / "images" / "val").glob("*.jpg"))
    train_labels = sorted((dataset_dir / "labels" / "train").glob("*.txt"))
    val_labels = sorted((dataset_dir / "labels" / "val").glob("*.txt"))
    manifest_file = dataset_dir / "manifest_v2.json"

    print(f"Found train images: {len(train_images)} (expected 4217)")
    print(f"Found val images:   {len(val_images)} (expected 275)")
    print(f"Found train labels: {len(train_labels)} (expected 4217)")
    print(f"Found val labels:   {len(val_labels)} (expected 275)")

    assert len(train_images) == 4217, f"Unexpected train images count: {len(train_images)}"
    assert len(val_images) == 275, f"Unexpected val images count: {len(val_images)}"
    assert len(train_labels) == 4217, f"Unexpected train labels count: {len(train_labels)}"
    assert len(val_labels) == 275, f"Unexpected val labels count: {len(val_labels)}"

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # Write YAML
        zf.writestr("crack_seg_prepared_v2.yaml", kaggle_yaml_content)
        # Write manifest
        if manifest_file.exists():
            zf.write(manifest_file, arcname="manifest_v2.json")
        
        # Write train images
        for img in train_images:
            zf.write(img, arcname=f"images/train/{img.name}")
        # Write val images
        for img in val_images:
            zf.write(img, arcname=f"images/val/{img.name}")
        # Write train labels
        for lbl in train_labels:
            zf.write(lbl, arcname=f"labels/train/{lbl.name}")
        # Write val labels
        for lbl in val_labels:
            zf.write(lbl, arcname=f"labels/val/{lbl.name}")

    file_size_mb = output_zip.stat().st_size / (1024 * 1024)
    print(f"Dataset ZIP created: {output_zip} ({file_size_mb:.2f} MB)")
    return output_zip

def package_checkpoint():
    checkpoint_file = PROJECT_ROOT / "weights" / "shm_ai_yolo26n_seg_15e_best.pt"
    output_zip = PROJECT_ROOT / "shm_ai_yolo26n_seg_checkpoint.zip"

    print(f"\nPackaging checkpoint from: {checkpoint_file}")
    print(f"Target archive:            {output_zip}")

    if not checkpoint_file.is_file():
        raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_file}")

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(checkpoint_file, arcname="shm_ai_yolo26n_seg_15e_best.pt")

    file_size_mb = output_zip.stat().st_size / (1024 * 1024)
    print(f"Checkpoint ZIP created: {output_zip} ({file_size_mb:.2f} MB)")
    return output_zip

def verify_archives():
    dataset_zip = PROJECT_ROOT / "shm_ai_prepared_crack_seg_v2.zip"
    checkpoint_zip = PROJECT_ROOT / "shm_ai_yolo26n_seg_checkpoint.zip"

    print("\n" + "=" * 70)
    print("ARCHIVE VERIFICATION REPORT")
    print("=" * 70)

    # 1. Dataset ZIP
    with zipfile.ZipFile(dataset_zip, "r") as zf:
        names = zf.namelist()
        print(f"Dataset ZIP total entries: {len(names)}")
        train_imgs = [n for n in names if n.startswith("images/train/") and n.endswith(".jpg")]
        val_imgs = [n for n in names if n.startswith("images/val/") and n.endswith(".jpg")]
        test_imgs = [n for n in names if "test" in n]
        train_lbls = [n for n in names if n.startswith("labels/train/") and n.endswith(".txt")]
        val_lbls = [n for n in names if n.startswith("labels/val/") and n.endswith(".txt")]
        caches = [n for n in names if n.endswith(".cache")]
        
        print(f"  Train images: {len(train_imgs)}")
        print(f"  Val images:   {len(val_imgs)}")
        print(f"  Test items:   {len(test_imgs)} (MUST BE 0)")
        print(f"  Train labels: {len(train_lbls)}")
        print(f"  Val labels:   {len(val_lbls)}")
        print(f"  Cache files:  {len(caches)} (MUST BE 0)")
        print(f"  YAML present: {'crack_seg_prepared_v2.yaml' in names}")
        print(f"  Manifest:     {'manifest_v2.json' in names}")

        assert len(train_imgs) == 4217, "Train image count mismatch"
        assert len(val_imgs) == 275, "Val image count mismatch"
        assert len(test_imgs) == 0, "Test data leakage detected!"
        assert len(train_lbls) == 4217, "Train label count mismatch"
        assert len(val_lbls) == 275, "Val label count mismatch"
        assert len(caches) == 0, "Cache files found in ZIP!"
        assert "crack_seg_prepared_v2.yaml" in names, "YAML missing!"

    # 2. Checkpoint ZIP
    with zipfile.ZipFile(checkpoint_zip, "r") as zf:
        names = zf.namelist()
        print(f"\nCheckpoint ZIP entries: {names}")
        assert "shm_ai_yolo26n_seg_15e_best.pt" in names, "Checkpoint missing from ZIP!"
        assert len(names) == 1, "Unexpected extra files in checkpoint ZIP!"

    print("\nALL ARCHIVE VERIFICATION CHECKS PASSED!")
    print("=" * 70)

if __name__ == "__main__":
    package_dataset()
    package_checkpoint()
    verify_archives()
