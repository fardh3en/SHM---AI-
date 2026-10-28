# SHM-AI: Concrete Crack Dataset Pipeline Guide

**Project:** SHM-AI (Structural Health Monitoring AI Platform)  
**Location:** `scripts/dataset_pipeline/`  
**Purpose:** End-to-end processing pipeline to convert, filter, deduplicate, and split concrete-only crack datasets into a unified, leak-free YOLOv8 dataset.

---

## 1. Pipeline Architecture

The pipeline standardizes concrete crack annotations into single-class YOLO detection bounding boxes (`class 0: crack`) and ingests negative concrete background images:

```
Concrete Sources:
├── Ultralytics Crack-Seg  ──> convert_crack_seg.py      ──┐
└── SDNET2018 (UW & UD)    ──> ingest_sdnet_negatives.py  ──┴──> Staging Directory
                                                                      │
                                                                      ▼
                                                         deduplicate_and_split.py
                                                         (SHA-256 + 64-bit dHash Clustering)
                                                                      │
                                                                      ▼
                                                            validate_labels.py
                                                         (Format, Class 0, Bound Checks)
                                                                      │
                                                                      ▼
                                                           datasets/crack-concrete/
                                                           (Train: 80%, Val: 10%, Test: 10%)
```

---

## 2. Script Reference & CLI Commands

### 2.1 Convert Ultralytics Crack-Seg Polygons to Bounding Boxes
Converts polygon coordinates $(x_1, y_1, x_2, y_2, \dots)$ into bounding boxes $(x_c, y_c, w, h)$.
```powershell
.venv\Scripts\python scripts/dataset_pipeline/convert_crack_seg.py `
  --input-dir datasets/crack-seg `
  --output-dir datasets/staging_concrete/crack_seg
```

### 2.2 Ingest SDNET2018 Structural Hard Negatives (Concrete Walls & Decks)
Extracts uncracked concrete walls (`UW`) and decks (`UD`) and generates 0-byte negative YOLO labels. **Excludes road pavements (`UP`, `CP`) and excludes unlocalized cracked images (`CW`, `CD`).**
```powershell
.venv\Scripts\python scripts/dataset_pipeline/ingest_sdnet_negatives.py `
  --sdnet-root datasets/raw_downloads/sdnet2018 `
  --output-dir datasets/staging_concrete/sdnet_negatives `
  --max-samples 500
```

### 2.3 Deduplication and Stratified Split Generation
- Computes SHA-256 and 64-bit perceptual difference hash (`dHash`).
- Clusters near-duplicates (Hamming distance $\le 2$).
- Partitions clusters into 80% Train, 10% Validation, and 10% Test splits. **Guarantees 0% cross-split duplicate leakage.**
```powershell
.venv\Scripts\python scripts/dataset_pipeline/deduplicate_and_split.py `
  --staging-dirs datasets/staging_concrete/crack_seg datasets/staging_concrete/sdnet_negatives `
  --output-dir datasets/crack-concrete `
  --train-ratio 0.80 `
  --val-ratio 0.10 `
  --seed 42
```

### 2.4 Label Validation Check
Enforces single-class index `0`, valid normalized bounding coordinates, and non-empty images:
```powershell
.venv\Scripts\python scripts/dataset_pipeline/validate_labels.py `
  --dataset-dir datasets/crack-concrete
```

---

## 3. Running Pipeline Unit Tests

```powershell
.venv\Scripts\python -m pytest tests/unit/test_dataset_pipeline.py -v
```
All 13 unit tests pass, validating polygon conversion, binary masks, SDNET concrete ingestion, dHash clustering, and label syntax.
