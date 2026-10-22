# Vision Engine — Phase 2 & Phase 6

**Status**: ✅ Implemented & Integrated

The **Vision Engine** performs deep-learning-based crack detection, instance segmentation, and geometric defect quantification from high-resolution structural inspection imagery.

---

## Architecture & Modules

```
vision/
├── detectors/
│   ├── base.py                  ← Abstract IDetector interface & DetectionResult
│   └── yolo.py                  ← YOLO11 instance segmentation & detection implementation
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

## Core Algorithms & Implementations

### 1. Sliced Inference (`slicing.py`)
To preserve hairline crack features without downsampling high-resolution photographic evidence:
- Divides images into tiles (default: 640×640 px).
- Implements spatial overlap (default: 40%) to eliminate boundary edge clipping.
- Reprojects local tile coordinates back into global image space.

### 2. Instance Segmentation (`yolo.py`)
- Employs Ultralytics YOLO11 (`yolo11n-seg.pt` or fine-tuned custom weights).
- Gracefully handles missing local weights via `ModelNotFoundError` (503 status code), directing users to run `python scripts/download_weights.py`.
- Yields bounding boxes, confidence scores, and raw segmentation masks.

### 3. Topological Skeletonization & Crack Graph (`skeleton.py` & `graph.py`)
- **Centerline Extraction**: Computes binary skeleton via `skimage.morphology.skeletonize`.
- **Topological Graph**: Constructs an 8-connectivity NetworkX graph of the skeleton pixels.
- **Junction & Endpoint Detection**: Convolves with an 8-neighbor kernel to isolate endpoints and junction nodes.
- **Metric Extraction**: Traverses graph edges to measure true crack length, branches, and average/maximum opening widths.

---

## Weight Provisioning

Provision YOLO11 weights using the repository CLI utility:

```bash
# Explicit interactive confirmation
python scripts/download_weights.py

# Non-interactive confirmation
python scripts/download_weights.py --yes
```
Weights are stored in `weights/` and resolved automatically by the vision detector.
