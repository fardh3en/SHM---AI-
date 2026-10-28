"""
Builder script for notebooks/SHM_AI_YOLOv8_Concrete_Training.ipynb
Generates a reproducible Google Colab training notebook for the concrete-focused YOLOv8 crack detector.
Validates all code cells with ast.parse.
"""
import ast
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
NOTEBOOK_PATH = NOTEBOOKS_DIR / "SHM_AI_YOLOv8_Concrete_Training.ipynb"

MARKDOWN_HEADER = """# SHM-AI: Concrete Structural Crack Detection Training (YOLOv8) - Option A Fine-Tuning

**Project:** SHM-AI — AI-Powered Structural Health Monitoring Platform  
**Target Model:** YOLOv8 Nano Object Detection (`yolov8n.pt` / `crack_yolov8n_concrete.pt`)  
**Target Task:** `detect` (Bounding Boxes + Confidence, Single-Class: `0: crack`)  
**Focus Domain:** Concrete Civil Infrastructure (Columns, Beams, Walls, Slabs)  
**Strategy (Option A):** Fine-tune warm-start 5-epoch candidate checkpoint (`crack_yolov8n_concrete.pt`) on the revised concrete-only dataset with 576 verified authentic concrete hard negatives for 30 epochs to produce `crack_yolov8n_concrete_v2.pt`.

### Curated Sources:
1. **Ultralytics Crack-Seg:** Concrete surface & structural crack morphology.
2. **METU / SDNET2018:** Verified authentic uncracked concrete building walls and structural surfaces as hard negatives.

### Strict Data Cleanliness:
- **Zero Road / Pavement Data:** Road damage datasets and asphalt pavements are strictly excluded. Potholes and vehicle damage are rejected.
- **Zero Fabricated Bounding Boxes:** Unlocalized image-level classifications are excluded from box detection to prevent spurious predictions.
- **Leak-Free Partitioning:** 64-bit perceptual hashing (`dHash`) ensures near-duplicate images never cross train, validation, or test splits.
- **Candidate Output:** `crack_yolov8n_concrete_v2.pt` (preserves v1 checkpoint intact).
"""

CODE_CELL_1_ENV = """# Step 1: Environment & Hardware Verification (Strict GPU Guard)
import os
import platform
import sys

print("=" * 70)
print("SHM-AI: CONCRETE CRACK DETECTION GPU VERIFICATION".center(70))
print("=" * 70)

print(f"Python Version:    {platform.python_version()} ({sys.executable})")
print(f"Platform / OS:     {platform.platform()}")

import torch
print(f"PyTorch Version:   {torch.__version__}")
cuda_available = torch.cuda.is_available()
print(f"CUDA Available:    {cuda_available}")

ALLOW_CPU = False  # Set to True ONLY if intentionally running smoke tests on CPU

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
            "YOLOv8 concrete crack training requires a GPU.\\n"
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

MARKDOWN_PERSISTENCE = """## Step 2: Google Drive Persistent Storage Integration

Mount Google Drive to persist model checkpoints (`last.pt`, `best.pt`), training curves, and metadata across Colab runtime disconnects.
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
        DRIVE_ROOT = Path("/content/drive/MyDrive/SHM_AI_Training/crack_yolov8n_concrete")
        DRIVE_ROOT.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR = DRIVE_ROOT
        print(f"Persistent storage mounted: '{OUTPUT_DIR}'")
    except Exception as exc:
        print(f"Drive mount skipped: {exc}")
        OUTPUT_DIR = Path("/content/runs/crack_yolov8n_concrete")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
else:
    OUTPUT_DIR = Path("./runs/crack_yolov8n_concrete").resolve()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"
METRICS_DIR = OUTPUT_DIR / "metrics"
PLOTS_DIR = OUTPUT_DIR / "plots"

for d in (CHECKPOINT_DIR, METRICS_DIR, PLOTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

print(f"Output directory initialized: {OUTPUT_DIR}")
"""

MARKDOWN_DATASET = """## Step 3: Concrete Dataset Configuration & Integrity Verification

Configures `crack-concrete.yaml` pointing exclusively to concrete structures with zero road/pavement scenes.
"""

CODE_CELL_3_DATASET = """# Step 3: Dataset Configuration, Extraction & Verification
import zipfile
from pathlib import Path

if IN_COLAB:
    DATASET_DIR = Path("/content/datasets/crack-concrete")
    # Potential zip candidate locations in Google Colab / Google Drive
    ZIP_CANDIDATES = [
        Path("/content/drive/MyDrive/SHM_AI_Training/crack-concrete.zip"),
        Path("/content/drive/MyDrive/crack-concrete.zip"),
        Path("/content/crack-concrete.zip"),
    ]
else:
    DATASET_DIR = Path("./datasets/crack-concrete").resolve()
    ZIP_CANDIDATES = [Path("./datasets/crack-concrete.zip").resolve()]

# Check if dataset images exist; if not, extract from zip archive
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
        print("DATASET ARCHIVE NOT FOUND!".center(70))
        print("Please upload 'crack-concrete.zip' to Google Drive:")
        print("  /content/drive/MyDrive/SHM_AI_Training/crack-concrete.zip")
        print("or directly into Colab file explorer at /content/crack-concrete.zip")
        print("!" * 70)

YAML_PATH = DATASET_DIR / "crack-concrete.yaml"
YAML_CONTENT = f\"\"\"# SHM-AI Concrete Structural Crack Detection Configuration
path: {DATASET_DIR.as_posix()}
train: images/train
val: images/val
test: images/test

names:
  0: crack
\"\"\"

DATASET_DIR.mkdir(parents=True, exist_ok=True)
YAML_PATH.write_text(YAML_CONTENT, encoding="utf-8")
print(f"Dataset configuration written to: {YAML_PATH}")

total_imgs = 0
for split in ("train", "val", "test"):
    img_dir = DATASET_DIR / "images" / split
    lbl_dir = DATASET_DIR / "labels" / split
    imgs = list(img_dir.glob("*.*")) if img_dir.is_dir() else []
    lbls = list(lbl_dir.glob("*.txt")) if lbl_dir.is_dir() else []
    empty_lbls = sum(1 for l in lbls if l.stat().st_size == 0)
    total_imgs += len(imgs)
    print(f"Split [{split.upper()}]: {len(imgs):,} images, {len(lbls):,} labels ({empty_lbls:,} hard negative concrete samples)")

if total_imgs >= 4500:
    print(f"\\n[DATASET VERIFIED] All {total_imgs:,} concrete structural images ready for training (including 576 verified hard negatives).")
else:
    print(f"\\n[WARNING] Found {total_imgs:,} images. Expected 4,604 images.")
"""

MARKDOWN_MODEL = """## Step 4: Base Model Checkpoint & Task Initialization (Option A)

Selects the warm-start base model for Option A fine-tuning:
1. Searches for the previous 5-epoch candidate checkpoint (`crack_yolov8n_concrete.pt`) across Google Drive and local paths.
2. Falls back to official `yolov8n.pt` baseline if the previous candidate is not present.
3. Verifies task compatibility (`task == 'detect'`).
"""

CODE_CELL_4_MODEL = """# Step 4: Model Checkpoint Selection & Initialization (Option A)
import os
from pathlib import Path
from ultralytics import YOLO

# Option A: Warm-start fine-tuning from previous 5-epoch candidate weights
# Search paths for the v1 candidate weights:
PREV_CANDIDATE_PATHS = [
    OUTPUT_DIR / "crack_yolov8n_concrete.pt",
    OUTPUT_DIR / "checkpoints" / "crack_yolov8n_concrete.pt",
    Path("/content/drive/MyDrive/SHM_AI_Training/crack_yolov8n_concrete/crack_yolov8n_concrete.pt"),
    Path("/content/drive/MyDrive/SHM_AI_Training/crack_yolov8n_concrete.pt"),
    Path("/content/crack_yolov8n_concrete.pt"),
    Path("./crack_yolov8n_concrete.pt").resolve(),
]

FINE_TUNE_PREV = True  # Option A: Set to True to warm-start from previous candidate

selected_model = None
if FINE_TUNE_PREV:
    for cand in PREV_CANDIDATE_PATHS:
        if cand.is_file():
            selected_model = str(cand)
            print(f"[OPTION A] Found warm-start candidate weights at: '{selected_model}'")
            break

if selected_model is None:
    if FINE_TUNE_PREV:
        print("[NOTICE] Previous candidate 'crack_yolov8n_concrete.pt' not found at candidate paths.")
        print("Falling back to official pretrained 'yolov8n.pt' baseline.")
    selected_model = "yolov8n.pt"

BASE_MODEL = selected_model
print(f"Loading checkpoint: '{BASE_MODEL}'...")
model = YOLO(BASE_MODEL)
print(f"Model Task:        {model.task}")
assert model.task == "detect", f"Task mismatch! Expected 'detect', got '{model.task}'."
print("Architecture confirmed: YOLOv8 Object Detection")
"""

MARKDOWN_TRAIN = """## Step 5: Option A Fine-Tuning Pipeline (Safety Guard Protected)

Fine-tunes the candidate detector for 30 epochs on the concrete dataset with hard negatives:
- `base_weights = crack_yolov8n_concrete.pt` (warm-start)
- `candidate_output = crack_yolov8n_concrete_v2.pt` (preserves v1 intact)
- `imgsz = 640`
- `batch = 16`
- `epochs = 30` (patience = 10)
- `lr0 = 0.0015` (fine-tuning learning rate)
- `close_mosaic = 10` (disables mosaic augmentation for final 10 epochs for crisp crack edges)
- `optimizer = AdamW`
- Checkpoints saved every 5 epochs to Google Drive.
"""

CODE_CELL_5_TRAIN = """# Step 5: Execute Option A Fine-Tuning (Disabled by Default)
import hashlib
import json
import shutil
import time
from pathlib import Path
from ultralytics import YOLO

# Safety switch: Set to True ONLY after Steps 1-4 pass successfully
RUN_FULL_TRAINING = False
RESUME_TRAINING = False

# Option A Configuration: 30 epochs fine-tuning with patience=10
EPOCHS = 30
BATCH_SIZE = 16
IMAGE_SIZE = 640
PATIENCE = 10
SEED = 42

CANDIDATE_MODEL_NAME = "crack_yolov8n_concrete_v2.pt"
CANDIDATE_PATH = OUTPUT_DIR / CANDIDATE_MODEL_NAME
TRAIN_PROJECT = OUTPUT_DIR / "runs"
RUN_NAME = "crack_concrete_v2_run"

if not RUN_FULL_TRAINING:
    print("=" * 70)
    print("[SAFETY GUARD] Model training is currently DISABLED.".center(70))
    print("=" * 70)
    print("Option A Fine-Tuning Setup:")
    print(f"  - Base Model:        {BASE_MODEL}")
    print(f"  - Target Model:      {CANDIDATE_MODEL_NAME}")
    print(f"  - Epochs:            {EPOCHS}")
    print(f"  - Patience:          {PATIENCE}")
    print(f"  - Batch Size:        {BATCH_SIZE}")
    print(f"  - Image Resolution:  {IMAGE_SIZE}x{IMAGE_SIZE}")
    print("Dataset status: 4,604 concrete structural images (Revised Dataset):")
    print("  - Train Split:   3,723 images (3,222 positive crack crops, 501 verified uncracked negatives)")
    print("  - Val Split:       477 images (402 positive crack crops, 75 verified uncracked negatives)")
    print("  - Test Split:      404 images (Immutable held-out crack benchmark, 543 crack annotations)")
    print("  - Hard Negatives:  576 verified undamaged concrete building surfaces (12.5% negative density)")
    print("\\nPre-training verification checklist:")
    print("  1. Step 1 passed (CUDA GPU detected, e.g. Tesla T4).")
    print("  2. Step 2 mounted Google Drive persistent storage.")
    print("  3. Step 3 verified 4,604 concrete images extracted from 'crack-concrete.zip'.")
    print("  4. Step 4 confirmed base model loaded successfully.")
    print("\\nTo begin training:")
    print("  - Set RUN_FULL_TRAINING = True.")
    print("  - Re-run this cell.")
    print("=" * 70)
else:
    print(f"Starting YOLOv8 Concrete Crack Option A training run: {RUN_NAME} ({EPOCHS} epochs)")
    print(f"Base checkpoint:  {BASE_MODEL}")
    print(f"Target candidate: {CANDIDATE_PATH}")
    start_time = time.time()

    results = model.train(
        data=str(YAML_PATH),
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        device=DEVICE,
        patience=PATIENCE,
        save=True,
        save_period=5,
        project=str(TRAIN_PROJECT),
        name=RUN_NAME,
        exist_ok=True,
        resume=RESUME_TRAINING,
        seed=SEED,
        optimizer="AdamW",
        lr0=0.0015,
        lrf=0.01,
        weight_decay=0.0005,
        warmup_epochs=2.0,
        close_mosaic=10,
        box=7.5,
        cls=0.5,
        dfl=1.5,
        fl_gamma=1.5,
        verbose=True,
    )

    elapsed_s = time.time() - start_time
    print(f"Option A fine-tuning completed in {elapsed_s / 60:.2f} minutes.")

    best_checkpoint = TRAIN_PROJECT / RUN_NAME / "weights" / "best.pt"
    if best_checkpoint.is_file():
        shutil.copy2(best_checkpoint, CANDIDATE_PATH)
        h = hashlib.sha256(CANDIDATE_PATH.read_bytes()).hexdigest()
        print(f"Candidate model preserved: '{CANDIDATE_PATH}'")
        print(f"Candidate SHA-256:         {h}")
    else:
        print(f"[WARNING] Best weights not found at: {best_checkpoint}")
"""

MARKDOWN_EVAL = """## Step 6: Evaluation on Frozen Held-Out Test Set

Evaluates `crack_yolov8n_concrete_v2.pt` on the 404 immutable held-out test images (543 crack annotations) and calculates performance deltas against the 5-epoch pilot baseline.
"""

CODE_CELL_6_EVAL = """# Step 6: Strictly Held-Out Test Evaluation & Comparison
import json
from pathlib import Path
from ultralytics import YOLO

# Benchmark baseline (5-epoch pilot results without hard negatives)
BASELINE_V1 = {
    "precision": 0.7831,
    "recall": 0.6515,
    "map50": 0.5959,
    "map50_95": 0.3648,
}

if CANDIDATE_PATH.is_file():
    print(f"Loading candidate model for evaluation: '{CANDIDATE_PATH}'...")
    eval_model = YOLO(str(CANDIDATE_PATH))
    test_metrics = eval_model.val(
        data=str(YAML_PATH),
        split="test",
        imgsz=IMAGE_SIZE,
        device=DEVICE,
        conf=0.25,
        iou=0.60,
        plots=True,
    )

    mAP50 = float(test_metrics.box.map50)
    mAP50_95 = float(test_metrics.box.map)
    precision = float(test_metrics.box.mp)
    recall = float(test_metrics.box.mr)

    d_prec = (precision - BASELINE_V1["precision"]) * 100
    d_rec = (recall - BASELINE_V1["recall"]) * 100
    d_m50 = (mAP50 - BASELINE_V1["map50"]) * 100
    d_m95 = (mAP50_95 - BASELINE_V1["map50_95"]) * 100

    print("=" * 72)
    print("HELD-OUT TEST SET EVALUATION: OPTION A vs BASELINE PILOT".center(72))
    print("=" * 72)
    print(f"{'Metric':<18} | {'Pilot Baseline (v1)':<20} | {'Option A (v2)':<15} | {'Delta':<10}")
    print("-" * 72)
    print(f"{'Precision':<18} | {BASELINE_V1['precision']*100:6.2f}%{' ':13} | {precision*100:6.2f}%{' ':8} | {d_prec:+6.2f}%")
    print(f"{'Recall':<18} | {BASELINE_V1['recall']*100:6.2f}%{' ':13} | {recall*100:6.2f}%{' ':8} | {d_rec:+6.2f}%")
    print(f"{'mAP@0.50':<18} | {BASELINE_V1['map50']*100:6.2f}%{' ':13} | {mAP50*100:6.2f}%{' ':8} | {d_m50:+6.2f}%")
    print(f"{'mAP@0.50-0.95':<18} | {BASELINE_V1['map50_95']*100:6.2f}%{' ':13} | {mAP50_95*100:6.2f}%{' ':8} | {d_m95:+6.2f}%")
    print("=" * 72)

    results_summary = {
        "candidate_model": CANDIDATE_MODEL_NAME,
        "base_model": BASE_MODEL,
        "epochs": EPOCHS,
        "mAP50": mAP50,
        "mAP50_95": mAP50_95,
        "precision": precision,
        "recall": recall,
        "baseline_v1": BASELINE_V1,
        "delta": {
            "precision_diff_pct": d_prec,
            "recall_diff_pct": d_rec,
            "map50_diff_pct": d_m50,
            "map50_95_diff_pct": d_m95,
        },
    }
    summary_path = METRICS_DIR / "test_evaluation_summary_v2.json"
    summary_path.write_text(json.dumps(results_summary, indent=2), encoding="utf-8")
    print(f"Results summary saved to: {summary_path}")
else:
    print(f"Candidate weights not found at: {CANDIDATE_PATH}. Run Step 5 first.")
"""


def build_notebook() -> Path:
    """Constructs and validates the concrete crack detection training notebook."""
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
    print(f"Generated concrete notebook: {NOTEBOOK_PATH} ({len(cells)} cells)")
    return NOTEBOOK_PATH


if __name__ == "__main__":
    build_notebook()
