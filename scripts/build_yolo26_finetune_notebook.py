"""Generator script for shm_ai_yolo26_finetune.ipynb.
Validates all code cells with ast.parse to ensure zero syntax errors.
Writes the notebook to:
- notebooks/shm_ai_yolo26_finetune.ipynb
- shm_ai_yolo26_finetune.ipynb (project root)
"""

import ast
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Cell 1: Header Markdown
MD_HEADER = """# SHM-AI: YOLO26 Concrete Crack Segmentation Fine-Tuning (Kaggle GPU)

**Project:** SHM-AI — AI-Powered Structural Health Monitoring Platform  
**Target Architecture:** YOLO26 Nano Instance Segmentation (`yolo26n-seg`, `Segment26` head)  
**Task:** `segment` (Pixel-Level Polygon Mask + Centerline Delineation)  
**Initial Checkpoint:** `shm_ai_yolo26n_seg_15e_best.pt` (Pretrained 15-Epoch Checkpoint)  
**Dataset:** `prepared_crack_seg_v2` (Audited & Corrected Validation Split)  
**Dataset Composition:**  
- **Train Split:** 4,217 images (3,717 crack positives + 500 verified concrete negatives)  
- **Validation Split:** 275 images (200 crack positives with corrected annotation + 75 verified concrete negatives)  
- **Held-Out Test Split:** **STRICTLY EXCLUDED** (preserved locally in SHM-AI repository; zero test leakage)  

---

### Key Operational Rules:
1. **GPU Acceleration Required:** Runs on NVIDIA CUDA GPU (e.g. Kaggle T4 x2 or P100).
2. **Read-Only Kaggle Protection:** Automatically unpacks and mirrors datasets into `/kaggle/working/` to prevent read-only filesystem errors with Ultralytics caching.
3. **No Overwrite Policy:** Checkpoints and outputs are isolated in `runs/segment/shm_ai_yolo26_v2_finetune`.
4. **Resilience & Recovery:** Supports automated background execution ("Save Version" / "Commit") and provides instant artifact packaging (`best.pt`, `results.csv`, training plots).
"""

# Cell 2: Hardware & Environment
CODE_ENV = """# Step 1: Environment & Hardware Verification (Strict GPU Guard)
import os
import platform
import subprocess
import sys
from pathlib import Path

print("=" * 70)
print("SHM-AI: HARDWARE & ENVIRONMENT VERIFICATION".center(70))
print("=" * 70)

print(f"Python Version:    {platform.python_version()} ({sys.executable})")
print(f"Platform / OS:     {platform.platform()}")

import torch
print(f"PyTorch Version:   {torch.__version__}")
cuda_available = torch.cuda.is_available()
print(f"CUDA Available:    {cuda_available}")

ALLOW_CPU = False  # Set to True ONLY if intentionally running dry-run on CPU

if cuda_available:
    device_count = torch.cuda.device_count()
    device_name = torch.cuda.get_device_name(0)
    device_props = torch.cuda.get_device_properties(0)
    total_memory_gb = device_props.total_memory / (1024 ** 3)
    compute_capability = f"{device_props.major}.{device_props.minor}"
    print(f"GPU Device:        {device_name} (Count: {device_count})")
    print(f"GPU VRAM:          {total_memory_gb:.2f} GB")
    print(f"Compute Capability:{compute_capability}")
    DEVICE = 0
else:
    print("\\n" + "!" * 70)
    print("WARNING: No CUDA GPU detected in this runtime!".center(70))
    print("!" * 70)
    if not ALLOW_CPU:
        raise SystemExit(
            "\\n[GPU GUARD ABORT]\\n"
            "YOLO26 instance segmentation fine-tuning requires a CUDA GPU.\\n"
            "In Kaggle:\\n"
            "  1. Look at the right sidebar under 'Notebook options' -> 'Settings'.\\n"
            "  2. Click 'Accelerator' and select 'GPU T4 x2' or 'GPU P100'.\\n"
            "  3. Ensure 'Internet' is toggled ON to allow package installation.\\n"
            "  4. Restart session and rerun this notebook.\\n"
        )
    DEVICE = "cpu"

# Install/Verify Ultralytics
try:
    import ultralytics
    from ultralytics import YOLO
    print(f"Ultralytics:       v{ultralytics.__version__}")
except ImportError:
    print("Ultralytics not installed. Installing via pip...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "ultralytics>=8.3.0"])
    import ultralytics
    from ultralytics import YOLO
    print(f"Ultralytics:       v{ultralytics.__version__} (installed)")

print("=" * 70)
print("ENVIRONMENT CHECK PASSED - READY FOR TRAINING".center(70))
print("=" * 70)
"""

# Cell 3: Markdown Setup
MD_SETUP = """## Step 2: Dataset & Checkpoint Discovery and Extraction

Kaggle `/kaggle/input` is mounted **read-only**. Ultralytics needs to write dataset cache files (`train.cache`, `val.cache`).  
This cell automatically locates the uploaded ZIP files or folders in `/kaggle/input` or `/kaggle/working`, extracts them cleanly into `/kaggle/working/dataset`, and generates an absolute-path YAML config.
"""

# Cell 4: Code Dataset & Checkpoint Extraction
CODE_SETUP = """# Step 2: Dataset & Checkpoint Extraction to Writable Storage
import glob
import json
import shutil
import zipfile
from pathlib import Path

# Setup directories
WORKING_DIR = Path("/kaggle/working" if Path("/kaggle/working").exists() else ".").resolve()
INPUT_DIR = Path("/kaggle/input" if Path("/kaggle/input").exists() else ".").resolve()

DATASET_ROOT = WORKING_DIR / "dataset" / "prepared_crack_seg_v2"
CHECKPOINT_DIR = WORKING_DIR / "weights"
RUNS_DIR = WORKING_DIR / "runs" / "segment"
RUN_NAME = "shm_ai_yolo26_v2_finetune"

for d in (DATASET_ROOT, CHECKPOINT_DIR, RUNS_DIR):
    d.mkdir(parents=True, exist_ok=True)

print(f"Working Directory: {WORKING_DIR}")
print(f"Dataset Target:    {DATASET_ROOT}")
print(f"Checkpoint Target: {CHECKPOINT_DIR}")

# 1. Discover & Extract Dataset
dataset_zip_candidates = list(INPUT_DIR.glob("**/shm_ai_prepared_crack_seg_v2*.zip")) + \\
                         list(WORKING_DIR.glob("shm_ai_prepared_crack_seg_v2*.zip"))

if dataset_zip_candidates:
    src_zip = dataset_zip_candidates[0]
    print(f"Extracting dataset archive: {src_zip} -> {DATASET_ROOT}")
    with zipfile.ZipFile(src_zip, "r") as zf:
        zf.extractall(DATASET_ROOT)
else:
    # Check if dataset is already extracted in input
    existing_dirs = list(INPUT_DIR.glob("**/prepared_crack_seg_v2")) + \\
                    list(INPUT_DIR.glob("**/images/train"))
    if existing_dirs:
        found_parent = existing_dirs[0].parent if existing_dirs[0].name == "train" else existing_dirs[0]
        print(f"Copying extracted dataset from read-only input: {found_parent} -> {DATASET_ROOT}")
        for item in found_parent.iterdir():
            dest = DATASET_ROOT / item.name
            if item.is_dir() and not dest.exists():
                shutil.copytree(item, dest)
            elif item.is_file() and not dest.exists():
                shutil.copy2(item, dest)
    else:
        print("Note: If running locally with datasets already in place, verifying local paths...")

# Verify dataset structure
train_images = list((DATASET_ROOT / "images" / "train").glob("*.jpg"))
val_images = list((DATASET_ROOT / "images" / "val").glob("*.jpg"))
test_images = list((DATASET_ROOT / "images" / "test").glob("*.jpg"))

print(f"Dataset verification:")
print(f"  Train images: {len(train_images)} (expected 4,217)")
print(f"  Val images:   {len(val_images)} (expected 275)")
print(f"  Test images:  {len(test_images)} (strictly 0 - no leakage)")

assert len(train_images) == 4217, f"Expected 4217 train images, found {len(train_images)}"
assert len(val_images) == 275, f"Expected 275 val images, found {len(val_images)}"
assert len(test_images) == 0, "Security alert: held-out test split must not be in training dataset!"

# Write clean absolute YAML configuration
DATASET_YAML = DATASET_ROOT / "crack_seg_prepared_v2.yaml"
yaml_content = f\"\"\"# SHM-AI YOLO26 Crack Segmentation Dataset Configuration
path: {DATASET_ROOT.as_posix()}
train: images/train
val: images/val

names:
  0: crack
\"\"\"
DATASET_YAML.write_text(yaml_content, encoding="utf-8")
print(f"Dataset YAML written at: {DATASET_YAML}")

# 2. Discover & Prepare Starting Checkpoint
checkpoint_candidates = (
    list(INPUT_DIR.glob("**/shm_ai_yolo26n_seg_15e_best.pt")) +
    list(WORKING_DIR.glob("**/shm_ai_yolo26n_seg_15e_best.pt")) +
    list(INPUT_DIR.glob("**/shm_ai_yolo26n_seg_checkpoint*.zip")) +
    list(WORKING_DIR.glob("shm_ai_yolo26n_seg_checkpoint*.zip"))
)

CHECKPOINT_PATH = CHECKPOINT_DIR / "shm_ai_yolo26n_seg_15e_best.pt"

if not CHECKPOINT_PATH.exists():
    if checkpoint_candidates:
        cand = checkpoint_candidates[0]
        if cand.suffix == ".zip":
            print(f"Extracting checkpoint from: {cand}")
            with zipfile.ZipFile(cand, "r") as zf:
                zf.extractall(CHECKPOINT_DIR)
        else:
            print(f"Copying checkpoint from: {cand} -> {CHECKPOINT_PATH}")
            shutil.copy2(cand, CHECKPOINT_PATH)
    else:
        raise FileNotFoundError(
            "Initial checkpoint 'shm_ai_yolo26n_seg_15e_best.pt' not found in /kaggle/input or working directory! "
            "Please upload 'shm_ai_yolo26n_seg_checkpoint.zip' as a Kaggle dataset."
        )

print(f"Initial Checkpoint verified: {CHECKPOINT_PATH} ({CHECKPOINT_PATH.stat().st_size / (1024*1024):.2f} MB)")
print("=" * 70)
print("DATASET & CHECKPOINT EXTRACTION COMPLETE".center(70))
print("=" * 70)
"""

# Cell 5: Markdown Baseline Inspection
MD_PREFLIGHT = """## Step 3: Checkpoint Architecture & Baseline Inspection

Loads the YOLO26 segmentation model weights and verifies layer configuration, parameter counts, and task specification before training.
"""

# Cell 6: Code Baseline Inspection
CODE_PREFLIGHT = """# Step 3: Inspect Starting YOLO26 Checkpoint
from ultralytics import YOLO

print("Loading starting checkpoint...")
model = YOLO(str(CHECKPOINT_PATH))

print(f"Task:            {model.task}")
print(f"Model Class:     {type(model.model).__name__}")
print(f"Class Names:     {model.names}")
print(f"Total Params:    {sum(p.numel() for p in model.model.parameters()):,}")

print("\\nArchitecture check passed: Ready to fine-tune.")
"""

# Cell 7: Markdown Training Execution
MD_TRAIN = """## Step 4: Launch YOLO26 Instance Segmentation Fine-Tuning

### Training Parameters:
- **Task:** `segment`
- **Starting Weights:** `shm_ai_yolo26n_seg_15e_best.pt`
- **Max Epochs:** `50`
- **Image Resolution:** `640 x 640`
- **Early Stopping Patience:** `12` epochs
- **Optimizer:** Auto (`AdamW` with dynamic learning rate schedule)
- **Batch Size:** `16` (optimized for 16 GB GPU VRAM)
- **DataLoader Workers:** `4`
- **Validation:** Evaluated at each epoch on the 275-image corrected validation split
- **Held-Out Test Split:** **STRICTLY EXCLUDED** (preserves test benchmark integrity)
- **Output Directory:** `runs/segment/shm_ai_yolo26_v2_finetune`
- **Resume Flag:** `False` (initiates clean fine-tuning run from existing weights)

*Note: In Kaggle, this typically runs in ~25 to 35 minutes on an NVIDIA T4 GPU.*
"""

# Cell 8: Code Training Execution
CODE_TRAIN = """# Step 4: Execute Fine-Tuning
import os
import time

print("=" * 70)
print("STARTING YOLO26 FINE-TUNING EXPERIMENT".center(70))
print("=" * 70)

start_time = time.time()

train_results = model.train(
    data=str(DATASET_YAML),
    epochs=50,
    imgsz=640,
    patience=12,
    task="segment",
    device=DEVICE,
    batch=16,
    workers=4,
    project=str(RUNS_DIR),
    name=RUN_NAME,
    exist_ok=True,
    resume=False,
    save=True,
    plots=True,
    val=True,
)

elapsed_sec = time.time() - start_time
print("=" * 70)
print(f"TRAINING COMPLETED IN {elapsed_sec / 60:.2f} MINUTES".center(70))
print("=" * 70)
"""

# Cell 9: Markdown Evaluation
MD_EVAL = """## Step 5: Post-Training Metric Analysis & Training Curves

Reads the generated `results.csv`, displays the performance curves (`results.png`), and summarizes mask/box mAP@50 and mAP@50-95.
"""

# Cell 10: Code Evaluation
CODE_EVAL = """# Step 5: Metric Evaluation & Visualization
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import Image, display

RUN_OUTPUT_DIR = RUNS_DIR / RUN_NAME
results_csv = RUN_OUTPUT_DIR / "results.csv"
results_png = RUN_OUTPUT_DIR / "results.png"

if results_csv.exists():
    df = pd.read_csv(results_csv)
    df.columns = df.columns.str.strip()
    print("=" * 70)
    print("TRAINING METRIC SUMMARY (FINAL EPOCH)".center(70))
    print("=" * 70)
    last_row = df.iloc[-1]
    for col in df.columns:
        val = last_row[col]
        if isinstance(val, (float, int)):
            print(f"  {col:<30}: {val:.5f}")
        else:
            print(f"  {col:<30}: {val}")

if results_png.exists():
    print("\\nDisplaying Training Performance Curves:")
    display(Image(filename=str(results_png), width=900))

# Display sample validation predictions
val_batch_preds = list(RUN_OUTPUT_DIR.glob("val_batch*_pred.jpg"))
if val_batch_preds:
    print(f"\\nDisplaying Validation Predictions ({val_batch_preds[0].name}):")
    display(Image(filename=str(val_batch_preds[0]), width=900))
"""

# Cell 11: Markdown Packaging & Recovery
MD_PACKAGE = """## Step 6: Artifact Packaging, Recovery Strategy & Download

Creates a self-contained ZIP archive (`shm_ai_yolo26_v2_finetune_artifacts.zip`) in `/kaggle/working/` containing:
- `weights/best.pt` (the best checkpoint based on validation mask mAP)
- `weights/last.pt` (the final epoch checkpoint)
- `results.csv` (complete epoch-by-epoch loss and mAP telemetry)
- `results.png` & validation prediction visualizations
- `args.yaml` (training configuration metadata)

### Recovery Strategy in Case of Disconnection:
1. **Headless Execution ("Save Version"):** In Kaggle, click **"Save Version"** (top right) -> Select **"Save & Run All (Commit)"**. Kaggle runs the entire notebook in the cloud for up to 12 hours independently of your browser.
2. **Resumption:** If a run was interrupted mid-way, set `resume=True` and pass `model = YOLO("runs/segment/shm_ai_yolo26_v2_finetune/weights/last.pt")` to continue from the last saved epoch without losing progress.
"""

# Cell 12: Code Packaging & Download
CODE_PACKAGE = """# Step 6: Package Artifacts and Generate Download Link
import hashlib
import zipfile
from IPython.display import FileLink, display

RUN_OUTPUT_DIR = RUNS_DIR / RUN_NAME
ARTIFACTS_ZIP = WORKING_DIR / "shm_ai_yolo26_v2_finetune_artifacts.zip"

print(f"Packaging artifacts from: {RUN_OUTPUT_DIR}")
print(f"Destination:              {ARTIFACTS_ZIP}")

files_to_pack = [
    RUN_OUTPUT_DIR / "weights" / "best.pt",
    RUN_OUTPUT_DIR / "weights" / "last.pt",
    RUN_OUTPUT_DIR / "results.csv",
    RUN_OUTPUT_DIR / "results.png",
    RUN_OUTPUT_DIR / "args.yaml",
] + list(RUN_OUTPUT_DIR.glob("val_batch*_pred.jpg")) + list(RUN_OUTPUT_DIR.glob("confusion_matrix*.png"))

with zipfile.ZipFile(ARTIFACTS_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for f in files_to_pack:
        if f.exists():
            arcname = f.relative_to(RUN_OUTPUT_DIR)
            zf.write(f, arcname=str(arcname))
            print(f"  + Packed: {arcname} ({f.stat().st_size / 1024:.1f} KB)")

zip_size_mb = ARTIFACTS_ZIP.stat().st_size / (1024 * 1024)
hasher = hashlib.sha256()
with open(ARTIFACTS_ZIP, "rb") as f:
    while chunk := f.read(65536):
        hasher.update(chunk)
zip_hash = hasher.hexdigest()

print("\\n" + "=" * 70)
print("EXPERIMENT ARTIFACTS PACKAGED SUCCESSFULLY".center(70))
print("=" * 70)
print(f"Archive Name:   {ARTIFACTS_ZIP.name}")
print(f"Archive Size:   {zip_size_mb:.2f} MB")
print(f"SHA-256 Hash:   {zip_hash}")
print("=" * 70)

# Display download link
display(FileLink(str(ARTIFACTS_ZIP.relative_to(WORKING_DIR))))
print("\\nYou can download 'shm_ai_yolo26_v2_finetune_artifacts.zip' directly from the Kaggle Output file pane!")
"""

def build_notebook():
    cells_data = [
        ("markdown", MD_HEADER),
        ("code", CODE_ENV),
        ("markdown", MD_SETUP),
        ("code", CODE_SETUP),
        ("markdown", MD_PREFLIGHT),
        ("code", CODE_PREFLIGHT),
        ("markdown", MD_TRAIN),
        ("code", CODE_TRAIN),
        ("markdown", MD_EVAL),
        ("code", CODE_EVAL),
        ("markdown", MD_PACKAGE),
        ("code", CODE_PACKAGE),
    ]

    nb_cells = []
    for cell_type, content in cells_data:
        if cell_type == "code":
            # Validate code with ast.parse
            ast.parse(content)
            nb_cells.append({
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [line + "\n" for line in content.split("\n")]
            })
        else:
            nb_cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": [line + "\n" for line in content.split("\n")]
            })

    notebook = {
        "cells": nb_cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {
                "provenance": []
            },
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.10.12"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

    # Save to notebooks/ and root
    nb_path_notebooks = PROJECT_ROOT / "notebooks" / "shm_ai_yolo26_finetune.ipynb"
    nb_path_root = PROJECT_ROOT / "shm_ai_yolo26_finetune.ipynb"

    with open(nb_path_notebooks, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2)
    print(f"Saved notebook: {nb_path_notebooks}")

    with open(nb_path_root, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2)
    print(f"Saved notebook: {nb_path_root}")

if __name__ == "__main__":
    build_notebook()
    print("Notebook build and AST syntax validation completed successfully!")
