# SHM-AI: Concrete Structural Dataset Manifest & License Governance

**Project:** SHM-AI (Structural Health Monitoring AI Platform)  
**Document:** Dataset Manifest and Intellectual Property Governance  
**Scope:** Concrete-Only Datasets for YOLOv8 Structural Crack Detection  

---

## 1. Overview and Legal Governance

To retrain the SHM-AI crack detector effectively on civil infrastructure while maintaining strict compliance with licensing terms, this manifest records the provenance, licensing terms, redistribution boundaries, and attribution requirements for all audited datasets.

Following strict engineering guidelines, **all road-damage and asphalt datasets have been eliminated** from the active training workflow.

---

## 2. Active & Retained Concrete Datasets

### 2.1 Ultralytics Crack-Seg (Concrete Surface Cracks)
- **Official Documentation:** [https://docs.ultralytics.com/datasets/segment/crack-seg/](https://docs.ultralytics.com/datasets/segment/crack-seg/)
- **Direct Asset Archive:** `https://github.com/ultralytics/assets/releases/download/v0.0.0/crack-seg.zip`
- **License:** AGPL-3.0 (GNU Affero General Public License v3.0)
- **Archive Size:** ~91.6 MB (96,089,865 bytes)
- **Image Count:** 4,029 images
- **Native Format:** YOLO normalized polygon segmentation format (`0 x1 y1 x2 y2 ...`)
- **Conversion:** Bounding boxes derived via `scripts/dataset_pipeline/convert_crack_seg.py`.
- **Status:** **ACTIVE & VERIFIED** in `datasets/crack-seg/`.

### 2.2 SDNET2018 (Structural Concrete Walls & Bridge Decks)
- **Publication Citation:**  
  Dorafshan, S., Thomas, R. J., & Maguire, M. (2018). *SDNET2018: An annotated image dataset for non-contact concrete crack detection using deep convolutional neural networks*. Data in Brief, 21, 1664-1668.
- **Repository URL:** [https://digitalcommons.unl.edu/archengfacpub/162/](https://digitalcommons.unl.edu/archengfacpub/162/)
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Dataset Size:** 56,098 images (256×256 pixels)
- **Retained Subsets:**
  - `UW`: Uncracked Concrete Walls (Structural negative samples)
  - `UD`: Uncracked Concrete Bridge Decks (Structural slab negative samples)
- **Excluded Subsets:**
  - `UP` and `CP`: Concrete/Asphalt pavements (Excluded - road/pavement domain)
  - `CW` and `CD`: Cracked walls and decks without spatial coordinates (Excluded from bounding boxes to prevent fake boxes)
- **Status:** **ACTIVE FOR HARD NEGATIVE INGESTION** (0-byte labels).

---

## 3. Audited & Excluded Datasets (Reasons & Licensing Blockers)

### 3.1 Crack500 — EXCLUDED (Domain Incompatible: Asphalt Pavements)
- **Publication Citation:** Yang et al. (2016), IEEE Transactions on Intelligent Transportation Systems.
- **Surface Type:** 100% Asphalt Road Pavements.
- **Reason for Exclusion:** Crack500 was captured on campus road pavements using smartphones. It contains zero concrete columns, beams, or structural walls. All 3,368 images are excluded to ensure the detector is not biased toward asphalt texture.

### 3.2 DeepCrack — EXCLUDED (Licensing Blocker & Asphalt Mixed Content)
- **Publication Citation:** Liu et al. (2019), Neurocomputing.
- **License:** **Non-Commercial Academic Research License**.
- **Licensing Blocker:** DeepCrack explicitly stipulates: *"The dataset is only used for academic research... not for commercial purposes."* Training weights intended for proprietary commercial deployment violates this condition.
- **Surface Type:** Mixed ~60% masonry/concrete walls and ~40% asphalt road surfaces.
- **Reason for Exclusion:** Legal licensing blocker and mixed asphalt content.

### 3.3 RDD2022 — FULLY REMOVED (Domain Incompatible: Road Damage)
- **Source:** Crowdsensing Road Damage Dataset (Arya et al., 2022).
- **Surface Type:** Vehicle windshield driving scenes of public asphalt highways.
- **Reason for Removal:** Potholes (`D40`), road wear (`D50`), and asphalt longitudinal/transverse cracks do not represent civil concrete infrastructure. Completely purged from the pipeline.

---

## 4. Licensing Summary Table

| Source | License Type | Commercial Use Permissible | Status in SHM-AI Pipeline |
| :--- | :--- | :--- | :--- |
| **Ultralytics Crack-Seg** | AGPL-3.0 | Yes (with open service code) | **RETAINED (Positives)** |
| **SDNET2018 (UW & UD)** | CC BY 4.0 | Yes (Attribution required) | **RETAINED (Hard Negatives)** |
| **Crack500** | Academic Use | Restricted | **EXCLUDED (Asphalt Road Surface)** |
| **DeepCrack** | Non-Commercial | **PROHIBITED** | **EXCLUDED (License Blocker)** |
| **RDD2022** | CC BY-SA 4.0 | Yes | **FULLY REMOVED (Road Damage)** |
