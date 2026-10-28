# Vision Engine — Phase 2 & Precision Calibration

**Status**: ✅ Implemented & Integrated

The **Vision Engine** performs deep-learning-based crack detection, instance segmentation, optical metric calibration, and geometric defect quantification from high-resolution structural inspection imagery.

---

## Architecture & Modules

```
vision/
├── calibration/                 ← Optical metric calibration & GSD governance
│   ├── depth_interface.py       ← Camera optics, sensor pitch & standoff distance
│   ├── image_quality.py         ← Laplacian sharpness, blur, and contrast metrics
│   ├── measurement_engine.py    ← Pixel-to-metric geometric scaling (mm, mm²)
│   └── schemas.py               ← Calibration contracts & data models
├── detectors/
│   ├── base.py                  ← Abstract IDetector interface & RawDetection
│   └── yolo.py                  ← YOLO26/YOLO11 instance segmentation & YOLOv8 detector
├── pipeline/
│   ├── base.py                  ← Abstract IPipeline interface
│   └── cv_pipeline.py           ← End-to-end computer vision pipeline orchestrator
├── preprocessing/
│   ├── loader.py                ← High-resolution multi-format image loader
│   └── slicing.py               ← Overlap-aware image slicer for gigapixel images
├── postprocessing/
│   ├── fusion.py                ← Spatial bounding box & mask OR-fusion across slices
│   ├── skeleton.py              ← Morphological skeletonization via scikit-image
│   ├── graph.py                 ← Topological NetworkX graph for crack branching & length
│   ├── measurements.py          ← Crack width, length, orientation & area metrics
│   └── polygon.py               ← GeoJSON-compatible polygon extraction
└── schemas.py                   ← Strongly-typed Pydantic vision contracts
```

---

## Available Model Weights

The platform maintains model options in `weights/`. Model selection is dynamic and managed through application configuration without code changes.

| Model / Checkpoint | Alias | Architecture | Task | Classes | Purpose |
|---|---|---|---|---|---|
| `shm_ai_yolo26n_seg_15e_best.pt` | `yolo26n-crack-seg` | YOLO26n-seg | Instance Segmentation | `{0: "crack"}` | **Recommended:** YOLO26 concrete crack segmentation. Produces high-fidelity pixel-level masks, GeoJSON polygons, and centerline skeleton metrics. |
| `shm_ai_crack_seg_finetune_15e_best.pt` | `yolo11n-crack-seg` | YOLO11n-seg | Instance Segmentation | `{0: "crack"}` | Fine-tuned concrete crack segmentation. Produces pixel-level masks, GeoJSON polygons, and morphological centerline skeleton metrics. |
| `crack_yolov8n_concrete.pt` | `crack_yolov8n_concrete` | YOLOv8n | Object Detection | `{0: "crack"}` | Fast bounding-box concrete crack detector. Bounding boxes only (no pixel segmentation masks). |
| `yolo11n-seg.pt` | `yolo11n-seg` | YOLO11n-seg | Instance Segmentation | 80 COCO classes | Base pre-trained model (general objects). Unvalidated for structural crack assessment. |

> [!IMPORTANT]
> **Git Policy**: Large binary model checkpoints (`*.pt`, `*.onnx`) are strictly excluded from source control via `.gitignore`. Never force-commit weights to the repository.

---

## Kaggle 15-Epoch Fine-Tuning Evaluation

The `shm_ai_crack_seg_finetune_15e_best.pt` checkpoint was fine-tuned on Kaggle using the prepared concrete crack segmentation dataset (`prepared_crack_seg_v1`).

### Independent Test Set Evaluation (112 images)
- **Box mAP50**: 68.3%
- **Box mAP50–95**: 47.2%
- **Mask Precision**: 73.7%
- **Mask Recall**: 58.1%
- **Mask mAP50**: 58.0%
- **Mask mAP50–95**: 20.6%

### Candidate Concrete-Negative Benchmark (100 uncracked concrete images)
| Confidence Threshold | False Positives Flagged | Specificity |
|---|---:|---:|
| 0.25 | 2 / 100 | 98.0% |
| 0.40 | 1 / 100 | 99.0% |
| 0.50 | 0 / 100 | 100.0% |

---

## Configuration & Model Selection

Configure the active model in `.env` or runtime environment variables:

```bash
# Option 1: Friendly alias for YOLO26 segmentation model
DEFAULT_MODEL_NAME=yolo26n-crack-seg

# Option 2: Friendly alias for fine-tuned YOLO11 model
DEFAULT_MODEL_NAME=yolo11n-crack-seg

# Option 3: Direct checkpoint filename
DEFAULT_MODEL_NAME=shm_ai_yolo26n_seg_15e_best.pt

# Option 4: Detection-only YOLOv8 model
DEFAULT_MODEL_NAME=crack_yolov8n_concrete

# Option 5: Explicit absolute or relative path (highest precedence)
MODEL_PATH=weights/shm_ai_yolo26n_seg_15e_best.pt
```

### Resolution Precedence:
1. `MODEL_PATH`: If set, takes absolute precedence (resolved relative to project root if not absolute). Missing target raises `ModelNotFoundError`.
2. `DEFAULT_MODEL_NAME` (alias): Resolves alias mappings (`yolo26n-crack-seg`, `yolo11n-crack-seg`, `crack_yolov8n_concrete`, `yolo11n-seg`).
3. `DEFAULT_MODEL_NAME` (filename/path): Checked against `WEIGHTS_DIR`.

Inference execution remains synchronous and non-blocking via background worker threads in FastAPI services.

---

## Pixel Measurements vs Physical Calibration Disclosure

The vision pipeline extracts geometric metrics from instance masks:

- **Pixel Units**: `area_px`, `length_px`, `width_px`, `max_width_px`, and `orientation_deg` represent direct morphological measurements computed from the segmentation mask and binary skeleton.
- **Physical Calibration**: Real-world dimensions (`length_mm`, `width_mm`, `area_mm2`) require an explicit optical calibration factor (`pixel_to_mm_ratio` / Ground Sampling Distance).
- **Engineering Standard**: In the absence of metric camera calibration, physical millimeters are never fabricated or estimated. The structural assessment engine flags calibration as `uncalibrated_pixel_space`.

---

## Core Algorithms & Implementations

### 1. Sliced Inference (`slicing.py`)
To preserve hairline crack features without downsampling high-resolution photographic evidence:
- Divides images into tiles (default: 640×640 px).
- Implements spatial overlap (default: 40%) to eliminate boundary edge clipping.
- Reprojects local tile coordinates back into global image space.

### 2. Instance Segmentation (`yolo.py`)
- Employs Ultralytics YOLO11 (`shm_ai_crack_seg_finetune_15e_best.pt` or base `yolo11n-seg.pt`).
- Gracefully handles missing local weights via `ModelNotFoundError` (503 status code), directing users to place the weights in `weights/`.
- Yields normalized bounding boxes, confidence scores, binary instance masks, and GeoJSON polygon boundaries.

### 3. Topological Skeletonization & Crack Graph (`skeleton.py` & `graph.py`)
- **Centerline Extraction**: Computes binary skeleton via `skimage.morphology.skeletonize`.
- **Topological Graph**: Constructs an 8-connectivity NetworkX graph of the skeleton pixels.
- **Junction & Endpoint Detection**: Convolves with an 8-neighbor kernel to isolate endpoints and junction nodes.
- **Metric Extraction**: Traverses graph edges to measure true crack length, branches, and average/maximum opening widths.

---

## Local Smoke Test & Verification

Verify the vision runtime and test model resolution:

```bash
# 1. Verify vision dependencies and configured weights
python scripts/verify_vision_environment.py

# 2. Run fine-tuned YOLO11 segmentation test suite
pytest tests/unit/test_yolo11_crack_seg_integration.py -v

# 3. Run YOLOv8 detection backward-compatibility suite
pytest tests/unit/test_yolov8_concrete_integration.py -v
```
