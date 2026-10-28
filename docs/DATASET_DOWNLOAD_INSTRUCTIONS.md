# SHM-AI: Concrete Dataset Download & Acquisition Guide

**Project:** SHM-AI (Structural Health Monitoring AI Platform)  
**Purpose:** Instructions for acquiring concrete-structure datasets for YOLOv8 crack detection training.  
**Scope:** Concrete Columns, Beams, Walls, and Bridge Decks (Zero Road/Pavement Data).

---

## 1. Storage Standards

Raw downloads should be placed in `datasets/raw_downloads/` and staged into `datasets/staging_concrete/`.
Final leak-free curated splits are written to `datasets/crack-concrete/`.

```powershell
mkdir datasets\raw_downloads -Force
mkdir datasets\staging_concrete -Force
```

---

## 2. Dataset Acquisition Procedures

### 2.1 Dataset 1: Ultralytics Crack-Seg (Concrete Surface Cracks)
- **Status:** Already downloaded and verified in repository at `datasets/crack-seg/`.
- **Image Count:** 4,029 images (3,717 train, 200 val, 112 test).
- **Automated Re-download (if needed):**
  ```powershell
  .venv\Scripts\python scripts/prepare_crack_dataset.py
  ```
- **Verification:**
  Directory `datasets/crack-seg/images/train/` contains 3,717 `.jpg` images.

---

### 2.2 Dataset 2: SDNET2018 (Structural Concrete Walls & Bridge Decks)
- **Source Page:** [https://digitalcommons.unl.edu/archengfacpub/162/](https://digitalcommons.unl.edu/archengfacpub/162/)
- **Archive Size:** ~1.3 GB.
- **Download Command:**
  ```powershell
  curl -L -o datasets/raw_downloads/SDNET2018.zip "https://digitalcommons.unl.edu/cgi/viewcontent.cgi?article=1161&context=archengfacpub"
  ```
- **Extraction:**
  ```powershell
  Expand-Archive -Path datasets\raw_downloads\SDNET2018.zip -DestinationPath datasets\raw_downloads\sdnet2018 -Force
  ```
- **Ingestion Rule:**
  - Only `UW` (Uncracked Concrete Walls) and `UD` (Uncracked Concrete Bridge Decks) are ingested as 0-byte negative labels.
  - Pavements (`UP`, `CP`) are automatically excluded.
  - Cracked subsets (`CW`, `CD`) are excluded from bounding boxes to prevent unlocalized false predictions.

---

## 3. Road-Damage Datasets Status

- **RDD2022:** **DO NOT DOWNLOAD.** Removed completely from SHM-AI.
- **Crack500:** **DO NOT DOWNLOAD.** 100% asphalt road pavement. Excluded from concrete pipeline.
- **DeepCrack:** **DO NOT DOWNLOAD.** Blocked by Non-Commercial license restriction.
