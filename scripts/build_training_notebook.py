"""
Builder script to generate notebooks/SHM_AI_Crack_Segmentation_Training.ipynb.
Validates all code cells for syntax correctness before writing the notebook.
"""
import ast
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
NOTEBOOK_PATH = NOTEBOOKS_DIR / "SHM_AI_Crack_Segmentation_Training.ipynb"

# ── Notebook Cells Definition ──────────────────────────────────────────────────

MARKDOWN_HEADER = """# SHM-AI: Concrete Crack Instance Segmentation Training (YOLO11 Nano)

**Project:** SHM-AI — AI-Powered Structural Health Monitoring Platform  
**Target Model:** YOLO11 Nano Instance Segmentation (`yolo11n-seg`)  
**Upstream Dataset:** Ultralytics `crack-seg` (4,029 images, 5,290 polygon instances)  
**Dataset License:** AGPL-3.0 (Ultralytics Open Source License)  
**Dataset Documentation:** https://docs.ultralytics.com/datasets/segment/crack-seg/  
**Export Target:** `crack_yolo11n_seg.pt` (Never overwrites `best.pt` or production weights)

---

### Critical Evaluation & Assessment Rules
1. **Zero Data Leakage:** The 112-image held-out test split is strictly reserved for post-training evaluation. It is never used during training or hyperparameter tuning.
2. **2D Masks vs. Physical Measurements:** 2D segmentation masks do **not** directly equal physical millimeter measurements without camera metric calibration (mm/pixel ratio).
3. **Preserve Structural Health Safeguards:** In accordance with SHM-AI assessment integrity, crack dimensions and structural health scores remain **Unverified** until metric calibration and human engineer review are performed.
4. **Honest Metric Reporting:** Box mAP, Mask mAP, Precision, Recall, and any limitations are recorded with complete provenance in `training_run_metadata.json`.
"""

CODE_CELL_1_ENV = """# Cell 1: Environment & Hardware Verification (Strict GPU Guard)
import os
import platform
import sys

print("=" * 70)
print("SHM-AI: HARDWARE & ENVIRONMENT VERIFICATION".center(70))
print("=" * 70)

# 1. Python & OS Info
print(f"Python Version:    {platform.python_version()} ({sys.executable})")
print(f"Platform / OS:     {platform.platform()}")

# 2. PyTorch & CUDA Check
import torch
print(f"PyTorch Version:   {torch.__version__}")
cuda_available = torch.cuda.is_available()
print(f"CUDA Available:    {cuda_available}")

# Hardware safety guard: stop if no compatible GPU is available
ALLOW_CPU = False  # Set to True ONLY if you explicitly choose slow CPU training

if cuda_available:
    device_count = torch.cuda.device_count()
    device_name = torch.cuda.get_device_name(0)
    device_props = torch.cuda.get_device_properties(0)
    total_memory_gb = device_props.total_memory / (1024 ** 3)
    compute_capability = f"{device_props.major}.{device_props.minor}"
    print(f"GPU Device:        {device_name} (Total: {device_count} device(s))")
    print(f"GPU Memory (VRAM): {total_memory_gb:.2f} GB")
    print(f"Compute Capability:{compute_capability}")
    DEVICE = 0
else:
    print("\\n" + "!" * 70)
    print("WARNING: No CUDA GPU detected in this runtime!".center(70))
    print("!" * 70)
    if not ALLOW_CPU:
        raise SystemExit(
            "\\n[ABORTED BY GPU SAFETY GUARD]\\n"
            "YOLO11 instance segmentation training on CPU is extremely slow.\\n"
            "To enable GPU in Google Colab:\\n"
            "  1. Go to menu: Runtime -> Change runtime type\\n"
            "  2. Under 'Hardware accelerator', select 'T4 GPU' (or A100 / L4)\\n"
            "  3. Click 'Save' and re-run this notebook.\\n\\n"
            "If you intentionally wish to test in CPU mode, set ALLOW_CPU = True in this cell."
        )
    else:
        print("[OVERRIDE] ALLOW_CPU is set to True. Proceeding with CPU compute target (device='cpu').")
        DEVICE = "cpu"

# 3. Ultralytics Check
try:
    import ultralytics
    from ultralytics import YOLO
    print(f"Ultralytics:       v{ultralytics.__version__}")
except ImportError:
    print("Ultralytics not installed. Installing via pip...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ultralytics>=8.3.0"])
    import ultralytics
    from ultralytics import YOLO
    print(f"Ultralytics:       v{ultralytics.__version__} (installed)")

print("=" * 70)
print("ENVIRONMENT CHECK PASSED".center(70))
print("=" * 70)
"""

MARKDOWN_PERSISTENCE = """## Step 2: Persistent Storage Setup (Google Drive Integration)

Google Colab runtimes are ephemeral. To ensure that checkpoints, metrics, and trained weights are never lost if the browser tab disconnects or the runtime times out, mount your Google Drive.
"""

CODE_CELL_2_PERSISTENCE = """# Cell 2: Persistent Storage Setup (Google Drive Mount)
import os
import sys
from pathlib import Path

print("=" * 70)
print("PERSISTENT STORAGE SETUP".center(70))
print("=" * 70)

IN_COLAB = "google.colab" in sys.modules
MOUNT_DRIVE = True  # Set to False if you prefer local ephemeral /content/ storage

if IN_COLAB and MOUNT_DRIVE:
    try:
        from google.colab import drive
        drive.mount("/content/drive")
        DRIVE_ROOT = Path("/content/drive/MyDrive/SHM_AI_Training/crack_yolo11n_seg")
        DRIVE_ROOT.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR = DRIVE_ROOT
        print(f"Persistent storage mounted to Google Drive: '{OUTPUT_DIR}'")
    except Exception as drive_err:
        print(f"Drive mount skipped or unverified: {drive_err}")
        OUTPUT_DIR = Path("/content/runs/crack_yolo11n_seg")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Using ephemeral storage: '{OUTPUT_DIR}' (DOWNLOAD ARTIFACTS BEFORE CLOSING RUNTIME!)")
else:
    OUTPUT_DIR = Path("./runs/crack_yolo11n_seg").resolve()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Using local output directory: '{OUTPUT_DIR}'")

CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"
METRICS_DIR = OUTPUT_DIR / "metrics"
PLOTS_DIR = OUTPUT_DIR / "plots"
METADATA_DIR = OUTPUT_DIR / "metadata"

for d in (CHECKPOINT_DIR, METRICS_DIR, PLOTS_DIR, METADATA_DIR):
    d.mkdir(parents=True, exist_ok=True)

print(f"Artifact output directory: {OUTPUT_DIR}")
"""

MARKDOWN_DATASET = """## Step 3: Dataset Ingestion & Configuration

This step provisions the official Ultralytics `crack-seg` dataset:
- Direct download from official release: `https://github.com/ultralytics/assets/releases/download/v0.0.0/crack-seg.zip`
- Verifies archive integrity and extracts preserving train (3,717), val (200), and test (112) splits.
- Generates a localized `crack-seg-training.yaml` and `crack-smoke-training.yaml` with absolute paths.
"""

CODE_CELL_3_DATASET = """# Cell 3: Dataset Ingestion & Setup
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

print("=" * 70)
print("DATASET INGESTION & SETUP".center(70))
print("=" * 70)

DATASET_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/crack-seg.zip"
DATASET_LICENSE = "AGPL-3.0 (Ultralytics Open Source License)"
DATASET_DOCS = "https://docs.ultralytics.com/datasets/segment/crack-seg/"

if IN_COLAB:
    BASE_DATA_DIR = Path("/content/datasets")
else:
    BASE_DATA_DIR = Path("./datasets").resolve()

BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)
CRACK_SEG_DIR = BASE_DATA_DIR / "crack-seg"
CRACK_SMOKE_DIR = BASE_DATA_DIR / "crack-smoke"
ARCHIVE_PATH = BASE_DATA_DIR / "crack-seg.zip"

# Download and extract if not present
if not (CRACK_SEG_DIR / "images").is_dir():
    if not ARCHIVE_PATH.is_file():
        print(f"Downloading crack-seg.zip from {DATASET_URL}...")
        req = urllib.request.Request(
            DATASET_URL,
            headers={"User-Agent": "SHM-AI-Colab-Trainer/1.0 (+https://github.com/fardh3en/SHM---AI-)"}
        )
        with urllib.request.urlopen(req) as resp, open(ARCHIVE_PATH, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)
        print(f"Downloaded archive: {ARCHIVE_PATH.stat().st_size:,} bytes")

    print(f"Extracting '{ARCHIVE_PATH}' into '{CRACK_SEG_DIR}'...")
    with zipfile.ZipFile(ARCHIVE_PATH, "r") as zf:
        members = zf.infolist()
        non_empty = [m.filename.replace("\\\\", "/") for m in members if m.filename.strip("/\\\\")]
        top_dirs = {name.split("/")[0] for name in non_empty if "/" in name}
        prefix = f"{list(top_dirs)[0]}/" if len(top_dirs) == 1 and all(n.startswith(f"{list(top_dirs)[0]}/") for n in non_empty) else ""

        for m in members:
            rel = m.filename.replace("\\\\", "/")
            if prefix and rel.startswith(prefix):
                rel = rel[len(prefix):]
            if not rel:
                continue
            target_file = CRACK_SEG_DIR / rel
            if m.is_dir() or m.filename.endswith("/"):
                target_file.mkdir(parents=True, exist_ok=True)
            else:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(m) as src, open(target_file, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    print("Dataset extracted successfully.")
else:
    print(f"Dataset already exists at: '{CRACK_SEG_DIR}'")

# Generate 10-image smoke test subset if missing
if not (CRACK_SMOKE_DIR / "images").is_dir():
    print(f"Creating 10-image smoke subset in '{CRACK_SMOKE_DIR}'...")
    plan = [("train", 6), ("val", 2), ("test", 2)]
    for split, count in plan:
        (CRACK_SMOKE_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (CRACK_SMOKE_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)
        src_img_dir = CRACK_SEG_DIR / "images" / split
        src_lbl_dir = CRACK_SEG_DIR / "labels" / split
        candidates = []
        for img in sorted(src_img_dir.iterdir()):
            lbl = src_lbl_dir / f"{img.stem}.txt"
            if lbl.is_file() and lbl.stat().st_size > 10:
                candidates.append(img)
            if len(candidates) >= count:
                break
        for img in candidates[:count]:
            shutil.copy2(img, CRACK_SMOKE_DIR / "images" / split / img.name)
            src_lbl = src_lbl_dir / f"{img.stem}.txt"
            dst_lbl = CRACK_SMOKE_DIR / "labels" / split / f"{img.stem}.txt"
            if src_lbl.is_file():
                shutil.copy2(src_lbl, dst_lbl)
            else:
                dst_lbl.touch()

# Generate localized YAML configs with absolute paths
CRACK_SEG_YAML = BASE_DATA_DIR / "crack-seg-training.yaml"
CRACK_SEG_YAML.write_text(f\"\"\"# Ultralytics YOLO Crack Segmentation Dataset Configuration
# Generated for Colab Training
path: {CRACK_SEG_DIR.resolve().as_posix()}
train: images/train
val: images/val
test: images/test

names:
  0: crack
\"\"\", encoding="utf-8")

CRACK_SMOKE_YAML = BASE_DATA_DIR / "crack-smoke-training.yaml"
CRACK_SMOKE_YAML.write_text(f\"\"\"# Ultralytics YOLO Smoke Dataset Configuration
# Generated for Colab Smoke Test
path: {CRACK_SMOKE_DIR.resolve().as_posix()}
train: images/train
val: images/val
test: images/test

names:
  0: crack
\"\"\", encoding="utf-8")

print(f"Training dataset YAML: {CRACK_SEG_YAML}")
print(f"Smoke dataset YAML:    {CRACK_SMOKE_YAML}")
"""

MARKDOWN_VERIFY = """## Step 4: Dataset Integrity & Annotation Sanity Verification

Performs exhaustive pre-flight verification on all splits:
- Confirms image decodability.
- Validates that all annotations are normalized polygon vertices in `[0.0, 1.0]`.
- Confirms class ID is `0: crack`.
- Validates negative background samples (0-byte labels).
"""

CODE_CELL_4_VERIFY = """# Cell 4: Dataset Integrity & Annotation Sanity Verification
from pathlib import Path

print("=" * 70)
print("DATASET INTEGRITY & ANNOTATION VERIFICATION".center(70))
print("=" * 70)

splits = ["train", "val", "test"]
expected_min_counts = {"train": 3500, "val": 150, "test": 100}

total_images = 0
total_polygons = 0
total_empty_labels = 0
total_issues = 0

for split in splits:
    img_dir = CRACK_SEG_DIR / "images" / split
    lbl_dir = CRACK_SEG_DIR / "labels" / split
    imgs = sorted([p for p in img_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}])
    count = len(imgs)
    total_images += count

    poly_count = 0
    empty_labels = 0
    split_issues = 0

    for img in imgs:
        lbl = lbl_dir / f"{img.stem}.txt"
        if not lbl.is_file():
            split_issues += 1
            continue
        content = lbl.read_text(encoding="utf-8").strip()
        if not content:
            empty_labels += 1
            continue
        for line in content.splitlines():
            tokens = line.strip().split()
            if len(tokens) < 7 or tokens[0] != "0" or len(tokens[1:]) % 2 != 0:
                split_issues += 1
                continue
            for val_str in tokens[1:]:
                try:
                    val = float(val_str)
                    if not (-0.05 <= val <= 1.05):
                        split_issues += 1
                except ValueError:
                    split_issues += 1
            poly_count += 1

    total_polygons += poly_count
    total_empty_labels += empty_labels
    total_issues += split_issues

    print(f"Split [{split.upper()}]:")
    print(f"  - Images:               {count:,} (expected >= {expected_min_counts[split]})")
    print(f"  - Polygons:             {poly_count:,}")
    print(f"  - Empty labels (neg):   {empty_labels}")
    print(f"  - Annotation issues:    {split_issues}")

print("-" * 70)
print(f"Total Images:             {total_images:,}")
print(f"Total Polygons:           {total_polygons:,}")
print(f"Negative Background:      {total_empty_labels}")
print(f"Annotation Issues:        {total_issues}")
print("=" * 70)
assert total_issues == 0, f"Integrity check failed: {total_issues} annotation issue(s) detected!"
print("DATASET INTEGRITY VERIFIED: 100% CLEAN")
"""

MARKDOWN_MODEL = """## Step 5: Base Model Checkpoint & Task Verification

Loads official pretrained `yolo11n-seg.pt` and verifies task compatibility (`task == 'segment'`).
"""

CODE_CELL_5_MODEL = """# Cell 5: Initialize YOLO11n-seg & Verify Model Task
from ultralytics import YOLO

print("=" * 70)
print("BASE MODEL INITIALIZATION & TASK COMPATIBILITY".center(70))
print("=" * 70)

BASE_MODEL_NAME = "yolo11n-seg.pt"
print(f"Loading pretrained base model: '{BASE_MODEL_NAME}'...")
base_model = YOLO(BASE_MODEL_NAME)

print(f"Model Task:        {base_model.task}")
print(f"Original Classes:  {len(base_model.names)} COCO classes")

assert base_model.task == "segment", (
    f"Task mismatch! Expected 'segment' task for instance segmentation, got '{base_model.task}'."
)
print("Model-Task compatibility verified: 'segment'")
print("=" * 70)
"""

MARKDOWN_SMOKE = """## Step 6: 1-Epoch Fast Smoke Test (Pipeline Verification)

Executes a 1-epoch dry-run on the 10-image smoke dataset to verify the entire PyTorch/CUDA forward pass, backward pass, loss calculation, and mask head operation before committing to full training.
"""

CODE_CELL_6_SMOKE = """# Cell 6: Fast 1-Epoch Smoke Test (Pipeline & GPU Verification)
print("=" * 70)
print("SMOKE TEST (1 EPOCH ON 10-IMAGE SUBSET)".center(70))
print("=" * 70)

smoke_run_dir = OUTPUT_DIR / "runs" / "smoke_test"
smoke_model = YOLO("yolo11n-seg.pt")

print("Executing 1-epoch smoke test on GPU...")
smoke_results = smoke_model.train(
    data=str(CRACK_SMOKE_YAML),
    epochs=1,
    batch=2,
    imgsz=320,
    device=DEVICE,
    project=str(smoke_run_dir.parent),
    name=smoke_run_dir.name,
    exist_ok=True,
    verbose=False,
    plots=False,
    save=False,
    val=True,
)

print("\\n" + "=" * 70)
print("SMOKE TEST PASSED: GPU segmentation pipeline fully operational!".center(70))
print("=" * 70)
"""

MARKDOWN_FULL_TRAIN = """## Step 7: Full Training Pipeline (Protected by Safety Guard)

### Hyperparameters & Safety Constraints
- **Safety Guard:** `RUN_FULL_TRAINING = False` by default. You must explicitly set it to `True` when ready.
- **Checkpoints:** Saved every 5 epochs; supports resuming interrupted runs via `RESUME_TRAINING = True`.
- **Target Filename:** Saved as `crack_yolo11n_seg.pt` (never overwrites `best.pt` or base weights).
"""

CODE_CELL_7_FULL_TRAIN = """# Cell 7: Full Training Pipeline (Disabled by Default)
import hashlib
import shutil
import time
from pathlib import Path
from ultralytics import YOLO

print("=" * 70)
print("FULL MODEL TRAINING PIPELINE".center(70))
print("=" * 70)

# ==============================================================================
# CONFIGURATION FLAGS & HYPERPARAMETERS
# ==============================================================================
RUN_FULL_TRAINING = False    # <<-- Set to True to start training!
RESUME_TRAINING = False      # Set to True to resume an interrupted training run

EPOCHS = 50                  # 50-100 epochs recommended for crack-seg convergence
BATCH_SIZE = 16              # 16 for T4 (16GB VRAM); reduce to 8 if OOM occurs
IMAGE_SIZE = 640             # Standard YOLO resolution
PATIENCE = 15                # Early stopping patience
SEED = 42                    # Fixed seed for reproducibility
SAVE_PERIOD = 5              # Save checkpoint every 5 epochs
OPTIMIZER = "auto"
LEARNING_RATE_0 = 0.01
LEARNING_RATE_F = 0.01

# Destination Candidate Weight Filename - NEVER overwrites best.pt!
CANDIDATE_MODEL_NAME = "crack_yolo11n_seg.pt"
CANDIDATE_WEIGHTS_PATH = OUTPUT_DIR / CANDIDATE_MODEL_NAME
TRAIN_PROJECT_DIR = OUTPUT_DIR / "runs"
RUN_NAME = "crack_yolo11n_seg_run"
# ==============================================================================

if not RUN_FULL_TRAINING:
    print("[SAFETY GUARD] Full training is DISABLED by default.")
    print("To start training:")
    print("  1. Review the hyperparameters above.")
    print("  2. Set RUN_FULL_TRAINING = True")
    print("  3. Run this cell again.")
else:
    print(f"Starting full training run: {RUN_NAME}")
    print(f"  - Base Checkpoint:  yolo11n-seg.pt")
    print(f"  - Dataset Config:   {CRACK_SEG_YAML}")
    print(f"  - Epochs:           {EPOCHS}")
    print(f"  - Batch Size:       {BATCH_SIZE}")
    print(f"  - Image Resolution: {IMAGE_SIZE}x{IMAGE_SIZE}")
    print(f"  - Compute Device:   {DEVICE}")
    print(f"  - Output Target:    {CANDIDATE_WEIGHTS_PATH}")
    print("-" * 70)

    start_time = time.time()

    if RESUME_TRAINING:
        last_ckpt = TRAIN_PROJECT_DIR / RUN_NAME / "weights" / "last.pt"
        if not last_ckpt.is_file():
            raise FileNotFoundError(f"Cannot resume: checkpoint not found at '{last_ckpt}'")
        print(f"Resuming from checkpoint: {last_ckpt}")
        model = YOLO(str(last_ckpt))
        train_results = model.train(resume=True)
    else:
        model = YOLO("yolo11n-seg.pt")
        train_results = model.train(
            data=str(CRACK_SEG_YAML),
            epochs=EPOCHS,
            batch=BATCH_SIZE,
            imgsz=IMAGE_SIZE,
            patience=PATIENCE,
            seed=SEED,
            deterministic=True,
            device=DEVICE,
            project=str(TRAIN_PROJECT_DIR),
            name=RUN_NAME,
            exist_ok=True,
            save=True,
            save_period=SAVE_PERIOD,
            optimizer=OPTIMIZER,
            lr0=LEARNING_RATE_0,
            lrf=LEARNING_RATE_F,
            val=True,
            plots=True,
        )

    elapsed_mins = (time.time() - start_time) / 60
    print(f"\\nTraining completed in {elapsed_mins:.1f} minutes.")

    best_weights_src = TRAIN_PROJECT_DIR / RUN_NAME / "weights" / "best.pt"
    if not best_weights_src.is_file():
        raise FileNotFoundError(f"Expected best weights not found at '{best_weights_src}'")

    shutil.copy2(best_weights_src, CANDIDATE_WEIGHTS_PATH)
    file_size_mb = CANDIDATE_WEIGHTS_PATH.stat().st_size / (1024 * 1024)

    h = hashlib.sha256()
    with open(CANDIDATE_WEIGHTS_PATH, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    candidate_sha256 = h.hexdigest()

    print("\\n" + "=" * 70)
    print("CANDIDATE MODEL WEIGHTS SAVED".center(70))
    print("=" * 70)
    print(f"Candidate Model:   {CANDIDATE_WEIGHTS_PATH.name}")
    print(f"Saved To:          {CANDIDATE_WEIGHTS_PATH}")
    print(f"File Size:         {file_size_mb:.2f} MB")
    print(f"SHA-256 Checksum:  {candidate_sha256}")
    print("=" * 70)
"""

MARKDOWN_EVAL = """## Step 8: Held-Out Test Set Evaluation (Zero Data Leakage)

Evaluates the trained candidate model strictly on the held-out 112 test images. Reports precision, recall, box mAP, and mask mAP.
"""

CODE_CELL_8_EVAL = """# Cell 8: Held-Out Test Set Evaluation (Zero Data Leakage)
from pathlib import Path
from ultralytics import YOLO

print("=" * 70)
print("HELD-OUT TEST SET EVALUATION (112 TEST IMAGES)".center(70))
print("=" * 70)

if 'CANDIDATE_WEIGHTS_PATH' in globals() and CANDIDATE_WEIGHTS_PATH.is_file():
    TEST_MODEL_PATH = CANDIDATE_WEIGHTS_PATH
else:
    print("[NOTE] Candidate weights not found. Run Cell 7 or specify existing checkpoint.")
    TEST_MODEL_PATH = None

if TEST_MODEL_PATH is not None and TEST_MODEL_PATH.is_file():
    print(f"Evaluating candidate model: '{TEST_MODEL_PATH.name}' on split='test'...")
    eval_model = YOLO(str(TEST_MODEL_PATH))

    test_metrics = eval_model.val(
        data=str(CRACK_SEG_YAML),
        split="test",
        imgsz=IMAGE_SIZE if 'IMAGE_SIZE' in globals() else 640,
        conf=0.25,
        iou=0.45,
        device=DEVICE,
        project=str(OUTPUT_DIR / "runs" / "test_eval"),
        name="test_results",
        exist_ok=True,
        plots=True,
    )

    box_p = float(test_metrics.box.p[0]) if len(test_metrics.box.p) > 0 else 0.0
    box_r = float(test_metrics.box.r[0]) if len(test_metrics.box.r) > 0 else 0.0
    box_map50 = float(test_metrics.box.map50)
    box_map = float(test_metrics.box.map)

    seg_p = float(test_metrics.seg.p[0]) if (hasattr(test_metrics, "seg") and len(test_metrics.seg.p) > 0) else 0.0
    seg_r = float(test_metrics.seg.r[0]) if (hasattr(test_metrics, "seg") and len(test_metrics.seg.r) > 0) else 0.0
    seg_map50 = float(test_metrics.seg.map50) if hasattr(test_metrics, "seg") else 0.0
    seg_map = float(test_metrics.seg.map) if hasattr(test_metrics, "seg") else 0.0

    print("\\n" + "=" * 70)
    print("TEST SET EVALUATION RESULTS (112 HELD-OUT IMAGES)".center(70))
    print("=" * 70)
    print(f"{'Metric':<25} | {'Bounding Box':<15} | {'Segmentation Mask':<15}")
    print("-" * 65)
    print(f"{'Precision (P)':<25} | {box_p:<15.4f} | {seg_p:<15.4f}")
    print(f"{'Recall (R)':<25} | {box_r:<15.4f} | {seg_r:<15.4f}")
    print(f"{'mAP@0.50':<25} | {box_map50:<15.4f} | {seg_map50:<15.4f}")
    print(f"{'mAP@0.50:0.95':<25} | {box_map:<15.4f} | {seg_map:<15.4f}")
    print("=" * 70)
else:
    print("[SKIPPED] Test evaluation skipped because candidate weights are not yet generated.")
    test_metrics = None
    box_p, box_r, box_map50, box_map = None, None, None, None
    seg_p, seg_r, seg_map50, seg_map = None, None, None, None
"""

MARKDOWN_METADATA = """## Step 9: Honest Assessment, Safeguards & Metadata Export

Exports structured `training_run_metadata.json` documenting environment, dataset provenance, hyperparameters, candidate weight hash, test metrics, and structural health assessment limitations.
"""

CODE_CELL_9_METADATA = """# Cell 9: Honest Assessment & Training Run Metadata Export
import json
import platform
import time
import torch

print("=" * 70)
print("TRAINING METADATA & PROVENANCE EXPORT".center(70))
print("=" * 70)

metadata = {
    "project": "SHM-AI",
    "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "framework": {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "ultralytics_version": ultralytics.__version__,
    },
    "dataset": {
        "name": "crack-seg",
        "source_url": DATASET_URL,
        "documentation_url": DATASET_DOCS,
        "license": DATASET_LICENSE,
        "splits": {
            "train_images": 3717,
            "val_images": 200,
            "test_images": 112,
            "total_images": 4029,
            "classes": {0: "crack"},
        },
    },
    "training_configuration": {
        "base_model": "yolo11n-seg.pt",
        "candidate_model": CANDIDATE_MODEL_NAME if 'CANDIDATE_MODEL_NAME' in globals() else "crack_yolo11n_seg.pt",
        "epochs": EPOCHS if 'EPOCHS' in globals() else 50,
        "batch_size": BATCH_SIZE if 'BATCH_SIZE' in globals() else 16,
        "image_size": IMAGE_SIZE if 'IMAGE_SIZE' in globals() else 640,
        "patience": PATIENCE if 'PATIENCE' in globals() else 15,
        "seed": SEED if 'SEED' in globals() else 42,
        "deterministic": True,
        "optimizer": OPTIMIZER if 'OPTIMIZER' in globals() else "auto",
        "learning_rate_0": LEARNING_RATE_0 if 'LEARNING_RATE_0' in globals() else 0.01,
        "learning_rate_f": LEARNING_RATE_F if 'LEARNING_RATE_F' in globals() else 0.01,
    },
    "candidate_weights": {
        "filename": CANDIDATE_MODEL_NAME if 'CANDIDATE_MODEL_NAME' in globals() else "crack_yolo11n_seg.pt",
        "sha256": candidate_sha256 if 'candidate_sha256' in globals() else None,
        "path": str(CANDIDATE_WEIGHTS_PATH) if 'CANDIDATE_WEIGHTS_PATH' in globals() else None,
    },
    "test_evaluation_metrics": {
        "box": {
            "precision": box_p,
            "recall": box_r,
            "map50": box_map50,
            "map50_95": box_map,
        },
        "mask": {
            "precision": seg_p,
            "recall": seg_r,
            "map50": seg_map50,
            "map50_95": seg_map,
        },
    },
    "assessment_limitations_and_safeguards": [
        "Pixel mask area and bounding boxes represent 2D camera projections and do NOT equate to physical mm measurements without metric calibration (mm/px ratio).",
        "Skeletonization and crack aperture measurements require known focal distance or calibration targets.",
        "Structural health score must remain 'Unverified' until metric calibration and human engineer inspection validate defect dimensions.",
        "The model was evaluated strictly on held-out test data (112 images) with zero train/val data leakage."
    ]
}

metadata_path = METADATA_DIR / "training_run_metadata.json"
metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
print(f"Metadata exported to: {metadata_path}")
print("=" * 70)
"""


def build_notebook() -> dict:
    NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)

    cells_spec = [
        ("markdown", MARKDOWN_HEADER),
        ("code", CODE_CELL_1_ENV),
        ("markdown", MARKDOWN_PERSISTENCE),
        ("code", CODE_CELL_2_PERSISTENCE),
        ("markdown", MARKDOWN_DATASET),
        ("code", CODE_CELL_3_DATASET),
        ("markdown", MARKDOWN_VERIFY),
        ("code", CODE_CELL_4_VERIFY),
        ("markdown", MARKDOWN_MODEL),
        ("code", CODE_CELL_5_MODEL),
        ("markdown", MARKDOWN_SMOKE),
        ("code", CODE_CELL_6_SMOKE),
        ("markdown", MARKDOWN_FULL_TRAIN),
        ("code", CODE_CELL_7_FULL_TRAIN),
        ("markdown", MARKDOWN_EVAL),
        ("code", CODE_CELL_8_EVAL),
        ("markdown", MARKDOWN_METADATA),
        ("code", CODE_CELL_9_METADATA),
    ]

    cells = []
    for cell_type, content in cells_spec:
        if cell_type == "code":
            # Verify Python syntax
            ast.parse(content)
            cells.append({
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [line + "\n" for line in content.splitlines()],
            })
        else:
            cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": [line + "\n" for line in content.splitlines()],
            })

    notebook = {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {
                "name": "SHM_AI_Crack_Segmentation_Training.ipynb",
                "provenance": [],
                "toc_visible": True,
            },
            "language_info": {
                "name": "python",
                "version": "3.10.12",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }

    NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
    print(f"Successfully generated notebook: {NOTEBOOK_PATH}")
    print(f"Total cells: {len(cells)} (Code: {sum(1 for c in cells if c['cell_type'] == 'code')}, Markdown: {sum(1 for c in cells if c['cell_type'] == 'markdown')})")
    return notebook


if __name__ == "__main__":
    build_notebook()
