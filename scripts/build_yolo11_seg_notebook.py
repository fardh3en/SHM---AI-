"""
Builder script for notebooks/SHM_AI_YOLO11_Seg_Training.ipynb
Generates a reproducible Google Colab training notebook for YOLO11 concrete crack segmentation.
Validates all code cells with ast.parse.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
NOTEBOOK_PATH = NOTEBOOKS_DIR / "SHM_AI_YOLO11_Seg_Training.ipynb"

MARKDOWN_HEADER = """# SHM-AI: Concrete Structural Crack Segmentation (YOLO11-seg)

**Project:** SHM-AI — AI-Powered Structural Health Monitoring Platform  
**Target Model:** YOLO11 Nano Instance Segmentation (`yolo11n-seg.pt`)  
**Target Task:** `segment` (Pixel-Level Polygon Mask + Centerline Delineation)  
**Dataset:** `prepared_crack_seg_v1` (4,217 train, 275 val, 112 test)  
**Negative Guard:** 575 verified uncracked concrete structural negatives (walls & decks) from SDNET2018  
**Strategy:**
1. **Pilot Run (5 Epochs):** Verify mask loss convergence, prototype mask generation, and VRAM memory stability.
2. **Production Run (30 Epochs):** Fine-tune prototype mask representations and boundary prediction.
3. **Safe Storage:** Checkpoints, metrics, and overlays saved to Google Drive without modifying existing YOLOv8 weights.
"""

CODE_CELL_1_ENV = """# Step 1: Environment & Hardware Verification (Strict GPU Guard)
import os
import platform
import sys

print("=" * 70)
print("SHM-AI: YOLO11 CRACK SEGMENTATION GPU VERIFICATION".center(70))
print("=" * 70)

print(f"Python Version:    {platform.python_version()} ({sys.executable})")
print(f"Platform / OS:     {platform.platform()}")

import torch
print(f"PyTorch Version:   {torch.__version__}")
cuda_available = torch.cuda.is_available()
print(f"CUDA Available:    {cuda_available}")

ALLOW_CPU = False  # Set to True ONLY if intentionally running dry-run on CPU

if cuda_available:
    device_name = torch.cuda.get_device_name(0)
    device_props = torch.cuda.get_device_properties(0)
    vram_gb = device_props.total_memory / (1024 ** 3)
    print(f"GPU Model:         {device_name}")
    print(f"GPU VRAM:          {vram_gb:.2f} GB")
    DEVICE = 0
else:
    print("\\n" + "!" * 70)
    print("WARNING: No CUDA GPU detected in this runtime!".center(70))
    print("!" * 70)
    if not ALLOW_CPU:
        raise SystemExit(
            "\\n[GPU GUARD ABORT]\\n"
            "YOLO11 crack segmentation training requires a GPU.\\n"
            "In Google Colab, go to: Runtime -> Change runtime type -> Hardware accelerator -> T4 GPU.\\n"
            "To test on CPU anyway, set ALLOW_CPU = True."
        )
    DEVICE = "cpu"

try:
    import ultralytics
    from ultralytics import YOLO
    print(f"Ultralytics:       v{ultralytics.__version__}")
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ultralytics>=8.3.0"])
    import ultralytics
    from ultralytics import YOLO
    print(f"Ultralytics:       v{ultralytics.__version__} (installed)")

print("=" * 70)
"""

MARKDOWN_PERSISTENCE = """## Step 2: Persistent Storage Setup (Google Drive Mount)

Mount Google Drive to persist model checkpoints (`last.pt`, `best.pt`), training curves, and evaluation metrics across Colab runtime disconnects.
"""

CODE_CELL_2_PERSISTENCE = """# Step 2: Persistent Storage Setup (Google Drive Mount)
import sys
from pathlib import Path

IN_COLAB = "google.colab" in sys.modules
MOUNT_DRIVE = True

if IN_COLAB and MOUNT_DRIVE:
    try:
        from google.colab import drive
        drive.mount("/content/drive")
        DRIVE_ROOT = Path("/content/drive/MyDrive/SHM_AI_Training/crack_yolo11n_seg")
        DRIVE_ROOT.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR = DRIVE_ROOT
        print(f"Persistent storage mounted at: '{OUTPUT_DIR}'")
    except Exception as exc:
        print(f"Drive mount skipped: {exc}")
        OUTPUT_DIR = Path("/content/runs/crack_yolo11n_seg")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
else:
    OUTPUT_DIR = Path("./runs/crack_yolo11n_seg").resolve()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"
METRICS_DIR = OUTPUT_DIR / "metrics"
PLOTS_DIR = OUTPUT_DIR / "plots"
OVERLAYS_DIR = OUTPUT_DIR / "overlays"

for d in (CHECKPOINT_DIR, METRICS_DIR, PLOTS_DIR, OVERLAYS_DIR):
    d.mkdir(parents=True, exist_ok=True)

print(f"Output directory initialized: {OUTPUT_DIR}")
"""

MARKDOWN_DATASET = """## Step 3: Dataset Configuration, Extraction & Verification

Verifies `prepared_crack_seg_v1`:
- 4,217 training images (3,717 crack + 500 verified uncracked concrete negatives).
- 275 validation images (200 crack + 75 verified uncracked concrete negatives).
- 112 test images (untouched held-out crack benchmark).
- Genuine polygon segmentation coordinates (`0 x1 y1 x2 y2 ...`).
"""

CODE_CELL_3_DATASET = """# Step 3: Dataset Configuration, Extraction & Verification
import zipfile
from pathlib import Path

if IN_COLAB:
    DATASET_DIR = Path("/content/datasets/prepared_crack_seg_v1")
    BENCHMARK_DIR = Path("/content/datasets/concrete-negatives-benchmark")
    ZIP_CANDIDATES = [
        Path("/content/drive/MyDrive/SHM_AI_Training/prepared_crack_seg_v1.zip"),
        Path("/content/drive/MyDrive/prepared_crack_seg_v1.zip"),
        Path("/content/prepared_crack_seg_v1.zip"),
    ]
    BENCHMARK_ZIP_CANDIDATES = [
        Path("/content/drive/MyDrive/SHM_AI_Training/concrete-negatives-benchmark.zip"),
        Path("/content/drive/MyDrive/concrete-negatives-benchmark.zip"),
        Path("/content/concrete-negatives-benchmark.zip"),
    ]
else:
    DATASET_DIR = Path("./datasets/prepared_crack_seg_v1").resolve()
    BENCHMARK_DIR = Path("./datasets/concrete-negatives-benchmark").resolve()
    ZIP_CANDIDATES = [Path("./datasets/prepared_crack_seg_v1.zip").resolve()]
    BENCHMARK_ZIP_CANDIDATES = [Path("./datasets/concrete-negatives-benchmark.zip").resolve()]

# Extract prepared dataset archive if not already extracted
train_img_dir = DATASET_DIR / "images" / "train"
if not train_img_dir.is_dir() or len(list(train_img_dir.glob("*.*"))) == 0:
    extracted = False
    for zip_path in ZIP_CANDIDATES:
        if zip_path.is_file():
            print(f"Found dataset archive at: '{zip_path}'. Extracting to '{DATASET_DIR.parent}'...")
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(DATASET_DIR.parent)
            print("Dataset extraction completed successfully.")
            extracted = True
            break
    if not extracted and not train_img_dir.is_dir():
        print("!" * 70)
        print("DATASET DIRECTORY OR ARCHIVE NOT FOUND!".center(70))
        print("Please upload 'prepared_crack_seg_v1.zip' to Google Drive:")
        print("  /content/drive/MyDrive/SHM_AI_Training/prepared_crack_seg_v1.zip")
        print("!" * 70)

# Extract negative benchmark if present
if not BENCHMARK_DIR.is_dir():
    for bzip in BENCHMARK_ZIP_CANDIDATES:
        if bzip.is_file():
            print(f"Extracting benchmark archive: {bzip}...")
            with zipfile.ZipFile(bzip, 'r') as zf:
                zf.extractall(BENCHMARK_DIR.parent)
            break

YAML_PATH = DATASET_DIR / "crack_seg_prepared.yaml"
YAML_CONTENT = f\"\"\"# SHM-AI Concrete Crack Segmentation Configuration
path: {DATASET_DIR.as_posix()}
train: images/train
val: images/val
test: images/test

names:
  0: crack
\"\"\"

DATASET_DIR.mkdir(parents=True, exist_ok=True)
YAML_PATH.write_text(YAML_CONTENT, encoding="utf-8")
print(f"Dataset configuration confirmed at: {YAML_PATH}")

total_imgs = 0
for split in ("train", "val", "test"):
    img_dir = DATASET_DIR / "images" / split
    lbl_dir = DATASET_DIR / "labels" / split
    imgs = list(img_dir.glob("*.jpg")) if img_dir.is_dir() else []
    lbls = list(lbl_dir.glob("*.txt")) if lbl_dir.is_dir() else []
    empty_lbls = sum(1 for l in lbls if l.stat().st_size == 0)
    total_imgs += len(imgs)
    print(f"Split [{split.upper()}]: {len(imgs):,} images, {len(lbls):,} labels ({empty_lbls:,} background negatives)")

# Verify sample polygon format
sample_lbls = [l for l in (DATASET_DIR / "labels" / "train").glob("*.txt") if l.stat().st_size > 0]
if sample_lbls:
    sample_line = sample_lbls[0].read_text(encoding="utf-8").strip().splitlines()[0]
    tokens = sample_line.split()
    print(f"Sample polygon verify: {sample_lbls[0].name} -> {len(tokens)} tokens, class={tokens[0]}")
    assert len(tokens) >= 7 and len(tokens) % 2 == 1, "Invalid polygon token structure!"
    print("[VERIFICATION PASSED] Dataset contains genuine polygon segmentation labels.")
"""

MARKDOWN_MODEL = """## Step 4: Base Segmentation Model Initialization

Loads the official `yolo11n-seg.pt` checkpoint and verifies task compatibility (`task == 'segment'`).
"""

CODE_CELL_4_MODEL = """# Step 4: Model Checkpoint Selection & Initialization
from pathlib import Path
from ultralytics import YOLO

MODEL_CANDIDATE_PATHS = [
    Path("./weights/yolo11n-seg.pt").resolve(),
    Path("/content/drive/MyDrive/SHM_AI_Training/crack_yolo11n_seg/yolo11n-seg.pt"),
    Path("/content/yolo11n-seg.pt"),
]

selected_model = None
for cand in MODEL_CANDIDATE_PATHS:
    if cand.is_file():
        selected_model = str(cand)
        print(f"Found local base segmentation model: '{selected_model}'")
        break

if selected_model is None:
    print("Local checkpoint not found; loading official Ultralytics 'yolo11n-seg.pt'...")
    selected_model = "yolo11n-seg.pt"

model = YOLO(selected_model)
print(f"Model Task:        {model.task}")
assert model.task == "segment", f"Task mismatch! Expected 'segment', got '{model.task}'."
print(f"Base Model loaded: {selected_model}")
"""

MARKDOWN_TRAIN = """## Step 5: Segmentation Fine-Tuning Execution (Pilot or Full Run)

- **Pilot Mode:** 5 epochs to verify prototype mask convergence and VRAM headroom.
- **Production Mode:** 30 epochs for full boundary delineation.
- Checkpoints and TensorBoard event logs are written to Google Drive persistent storage.
"""

CODE_CELL_5_TRAIN = """# Step 5: Segmentation Training Execution
import shutil
import time

PILOT_MODE = True       # Set to False after approving the 5-epoch pilot
EPOCHS = 5 if PILOT_MODE else 30
BATCH_SIZE = 8          # Safe for Tesla T4 (allocates ~2.8 GB VRAM)
IMGSZ = 640
RESUME = False          # Set to True to resume interrupted training
# Pilot safety: For 5-epoch pilot, keep mosaic active throughout (close_mosaic=0).
# A 5-epoch close_mosaic schedule would disable mosaic from the very first epoch!
CLOSE_MOSAIC = 0 if PILOT_MODE else 5

run_name = "crack_seg_pilot_5e" if PILOT_MODE else "crack_seg_production_30e"
print(f"Starting YOLO11 segmentation training (Mode: {'PILOT (5 epochs)' if PILOT_MODE else 'PRODUCTION (30 epochs)'})...")
print(f"Run name: {run_name} | Batch: {BATCH_SIZE} | ImgSz: {IMGSZ} | Close Mosaic: {CLOSE_MOSAIC}")

t0 = time.time()
train_results = model.train(
    data=str(YAML_PATH),
    task="segment",
    epochs=EPOCHS,
    batch=BATCH_SIZE,
    imgsz=IMGSZ,
    device=DEVICE,
    workers=4,
    optimizer="auto",
    lr0=0.01,
    lrf=0.01,
    mosaic=0.5,
    close_mosaic=CLOSE_MOSAIC,
    project=str(OUTPUT_DIR / "runs"),
    name=run_name,
    exist_ok=True,
    resume=RESUME,
    save=True,
    val=True,
)
train_time_min = (time.time() - t0) / 60
print(f"\\nTraining completed in {train_time_min:.2f} minutes.")

# Preserve candidate checkpoint with stripped optimizer
best_pt = OUTPUT_DIR / "runs" / run_name / "weights" / "best.pt"
candidate_pt = CHECKPOINT_DIR / f"{run_name}_best.pt"

if best_pt.is_file():
    from ultralytics.utils.torch_utils import strip_optimizer
    strip_optimizer(best_pt)
    shutil.copy2(best_pt, candidate_pt)
    print(f"[CHECKPOINT PRESERVED] Stripped candidate saved to: {candidate_pt}")
else:
    print(f"[WARNING] Expected best weights not found at: {best_pt}")
"""

MARKDOWN_EVAL = """## Step 6: Validation & Held-Out Test Evaluation

Evaluates the candidate segmentation checkpoint on:
1. The **Validation Set (275 images)** containing 200 crack images and 75 background concrete negatives.
2. The **Held-Out Test Set (112 images)** preserving the untouched positive crack benchmark.
"""

CODE_CELL_6_EVAL = """# Step 6: Validation & Test Evaluation
import json
from ultralytics import YOLO

EVAL_WEIGHTS = candidate_pt if candidate_pt.is_file() else (OUTPUT_DIR / "runs" / run_name / "weights" / "best.pt")
print(f"Evaluating candidate segmentation model: {EVAL_WEIGHTS}...")
eval_model = YOLO(str(EVAL_WEIGHTS))

# 1. Validation Set Evaluation (275 images: 200 cracks + 75 negatives)
print("\\n--- Evaluating on Validation Set (275 images) ---")
val_results = eval_model.val(
    data=str(YAML_PATH),
    split="val",
    imgsz=640,
    batch=8,
    device=DEVICE,
    save_json=True,
    project=str(OUTPUT_DIR / "runs"),
    name=f"{run_name}_val_eval",
    exist_ok=True,
)

# 2. Held-Out Test Set Evaluation (112 images: 100% positive cracks)
print("\\n--- Evaluating on Held-Out Test Set (112 images) ---")
test_results = eval_model.val(
    data=str(YAML_PATH),
    split="test",
    imgsz=640,
    batch=8,
    device=DEVICE,
    save_json=True,
    project=str(OUTPUT_DIR / "runs"),
    name=f"{run_name}_test_eval",
    exist_ok=True,
)

metrics_dict = {
    "model_checkpoint": str(EVAL_WEIGHTS),
    "run_name": run_name,
    "validation_set": {
        "images": 275,
        "mask_mAP50": float(getattr(val_results.seg, "map50", 0.0)),
        "mask_mAP50_95": float(getattr(val_results.seg, "map", 0.0)),
        "mask_precision": float(getattr(val_results.seg, "mp", 0.0)),
        "mask_recall": float(getattr(val_results.seg, "mr", 0.0)),
        "box_mAP50": float(getattr(val_results.box, "map50", 0.0)),
        "box_mAP50_95": float(getattr(val_results.box, "map", 0.0)),
    },
    "test_set": {
        "images": 112,
        "mask_mAP50": float(getattr(test_results.seg, "map50", 0.0)),
        "mask_mAP50_95": float(getattr(test_results.seg, "map", 0.0)),
        "mask_precision": float(getattr(test_results.seg, "mp", 0.0)),
        "mask_recall": float(getattr(test_results.seg, "mr", 0.0)),
        "box_mAP50": float(getattr(test_results.box, "map50", 0.0)),
        "box_mAP50_95": float(getattr(test_results.box, "map", 0.0)),
    },
}

summary_path = METRICS_DIR / f"{run_name}_evaluation_metrics.json"
summary_path.write_text(json.dumps(metrics_dict, indent=2), encoding="utf-8")

print("=" * 70)
print(f"PILOT EVALUATION SUMMARY ({run_name})".center(70))
print("=" * 70)
print(f"VALIDATION SET (275 images):")
print(f"  Mask mAP@0.50:       {metrics_dict['validation_set']['mask_mAP50']:.4f}")
print(f"  Mask mAP@0.50-0.95:  {metrics_dict['validation_set']['mask_mAP50_95']:.4f}")
print(f"  Mask Precision:      {metrics_dict['validation_set']['mask_precision']:.4f}")
print(f"  Mask Recall:         {metrics_dict['validation_set']['mask_recall']:.4f}")
print("-" * 70)
print(f"HELD-OUT TEST SET (112 images):")
print(f"  Mask mAP@0.50:       {metrics_dict['test_set']['mask_mAP50']:.4f}")
print(f"  Mask mAP@0.50-0.95:  {metrics_dict['test_set']['mask_mAP50_95']:.4f}")
print(f"  Mask Precision:      {metrics_dict['test_set']['mask_precision']:.4f}")
print(f"  Mask Recall:         {metrics_dict['test_set']['mask_recall']:.4f}")
print("=" * 70)
print(f"Metrics saved to: {summary_path}")
"""

MARKDOWN_BENCHMARK = """## Step 7: Negative Benchmark Evaluation & False Positive Guard

Evaluates the candidate segmentation model on the separate 100-image concrete negative benchmark across multiple confidence thresholds.
"""

CODE_CELL_7_BENCHMARK = """# Step 7: Negative Benchmark Evaluation
from pathlib import Path
import json

bench_images = list((BENCHMARK_DIR / "images").glob("*.jpg")) if BENCHMARK_DIR.is_dir() else []
print(f"Found {len(bench_images)} images in negative benchmark directory: {BENCHMARK_DIR}")

if len(bench_images) > 0:
    benchmark_report = {}
    for conf in [0.25, 0.40, 0.50]:
        flagged = []
        for p in bench_images:
            res = eval_model.predict(str(p), conf=conf, verbose=False)[0]
            if len(res.boxes) > 0 or (res.masks is not None and len(res.masks) > 0):
                max_c = float(res.boxes.conf.cpu().numpy().max()) if len(res.boxes) > 0 else 0.0
                flagged.append((p.name, max_c))
        fp_rate = (len(flagged) / len(bench_images)) * 100
        benchmark_report[f"conf_{conf:.2f}"] = {
            "flagged_count": len(flagged),
            "total_negatives": len(bench_images),
            "false_positive_rate_pct": fp_rate,
            "flagged_files": flagged,
        }
        print(f"Confidence {conf:.2f}: {len(flagged)}/100 images triggered detections ({fp_rate:.1f}% FP rate)")

    bench_summary_path = METRICS_DIR / f"{run_name}_negative_benchmark_metrics.json"
    bench_summary_path.write_text(json.dumps(benchmark_report, indent=2), encoding="utf-8")
    print(f"Negative benchmark metrics saved to: {bench_summary_path}")
else:
    print("[NOTICE] Negative benchmark directory not present. Skipping Step 7.")
"""

MARKDOWN_OVERLAYS = """## Step 8: Visual Prediction Overlays & Checkpoint Export

Generates visual prediction overlays (segmentation masks + bounding boxes) on test images and saves them to `overlays/`.
"""

CODE_CELL_8_OVERLAYS = """# Step 8: Visual Prediction Overlays & Checkpoint Export
import cv2
import matplotlib.pyplot as plt
from pathlib import Path

test_images = sorted(list((DATASET_DIR / "images" / "test").glob("*.jpg")))[:6]
print(f"Generating visual prediction overlays for {len(test_images)} test images...")

for idx, img_p in enumerate(test_images):
    res = eval_model.predict(str(img_p), conf=0.25, verbose=False)[0]
    plotted = res.plot()  # Ultralytics built-in segmentation overlay rendering
    out_path = OVERLAYS_DIR / f"test_overlay_{idx + 1}_{img_p.name}"
    cv2.imwrite(str(out_path), plotted)

print(f"Visual overlays saved to: {OVERLAYS_DIR}")

# Instructions for downloading checkpoint
print("\\n" + "=" * 70)
print("CHECKPOINT DOWNLOAD INSTRUCTIONS".center(70))
print("=" * 70)
print("To download the candidate model checkpoint directly to your local workstation:")
print(f"1. In Google Drive: MyDrive/SHM_AI_Training/crack_yolo11n_seg/checkpoints/{run_name}_best.pt")
print("2. Or run the code below in a new Colab cell:")
print(f"   from google.colab import files")
print(f"   files.download('{candidate_pt.as_posix()}')")
print("=" * 70)
"""


def build_notebook() -> Path:
    """Constructs and validates the YOLO11 crack segmentation training notebook."""
    cells = [
        {"cell_type": "markdown", "metadata": {}, "source": MARKDOWN_HEADER},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": CODE_CELL_1_ENV},
        {"cell_type": "markdown", "metadata": {}, "source": MARKDOWN_PERSISTENCE},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": CODE_CELL_2_PERSISTENCE},
        {"cell_type": "markdown", "metadata": {}, "source": MARKDOWN_DATASET},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": CODE_CELL_3_DATASET},
        {"cell_type": "markdown", "metadata": {}, "source": MARKDOWN_MODEL},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": CODE_CELL_4_MODEL},
        {"cell_type": "markdown", "metadata": {}, "source": MARKDOWN_TRAIN},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": CODE_CELL_5_TRAIN},
        {"cell_type": "markdown", "metadata": {}, "source": MARKDOWN_EVAL},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": CODE_CELL_6_EVAL},
        {"cell_type": "markdown", "metadata": {}, "source": MARKDOWN_BENCHMARK},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": CODE_CELL_7_BENCHMARK},
        {"cell_type": "markdown", "metadata": {}, "source": MARKDOWN_OVERLAYS},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": CODE_CELL_8_OVERLAYS},
    ]

    for idx, c in enumerate(cells):
        if c["cell_type"] == "code":
            try:
                ast.parse(c["source"])
            except SyntaxError as e:
                raise ValueError(f"Syntax error in code cell {idx}: {e}")

    notebook = {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"gpuType": "T4", "provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 0,
    }

    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=2), encoding="utf-8")
    print(f"Generated segmentation notebook: {NOTEBOOK_PATH} ({len(cells)} cells, syntax-validated)")
    return NOTEBOOK_PATH


if __name__ == "__main__":
    build_notebook()
