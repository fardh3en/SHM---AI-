# SHM-AI: Concrete Structural Crack Dataset Audit & Hard-Negative Remediation Report

**Project:** SHM-AI (Structural Health Monitoring Platform)  
**Date:** October 27, 2026  
**Status:** Hard-Negative Remediation Completed · Test Set Preserved (404 Images Frozen) · Verified on Disk  
**Target Architecture:** YOLOv8 Nano (`yolov8n.pt`, single-class `0: crack`)  

---

## 1. Forensic Audit: Cause of Missing SDNET2018 Negatives

An audit of [`curate_concrete_dataset.py`](file:///c:/Users/ahamm/Downloads/SHM AI PROJECT/SHM-AI/scripts/dataset_pipeline/curate_concrete_dataset.py), [`ingest_sdnet_negatives.py`](file:///c:/Users/ahamm/Downloads/SHM AI PROJECT/SHM-AI/scripts/dataset_pipeline/ingest_sdnet_negatives.py), and local disk storage established the exact chain of failure:

### Evidence 1: Ingestion Parameter Defaulted to None
In `curate_concrete_dataset.py` (lines 225 & 232):
```python
parser.add_argument("--sdnet-root", type=Path, default=None)
...
audit = curate_concrete_pipeline(
    crack_seg_dir=args.crack_seg_dir,
    sdnet_root=args.sdnet_root,  # evaluates to None
    ...
)
```
Line 108 guarded SDNET execution:
```python
if sdnet_root and sdnet_root.is_dir():
    # Ingestion was skipped entirely because sdnet_root was None
```

### Evidence 2: Automated Download Blocked by Cloudflare (HTTP 403 Forbidden)
When automated download commands attempted to pull `SDNET2018.zip` from DigitalCommons UNL and DigitalCommons USU:
```
HTTP/1.1 403 Forbidden
Server: cloudflare
Cf-Mitigated: challenge
CF-RAY: a511d6ff9e6ea923-MAA
```
Both academic institutional repositories protect raw archive endpoints with Cloudflare interactive JavaScript browser challenges (`Cf-Mitigated: challenge`), rejecting headless CLI tools (`curl`, `urllib`, `wget`). As a result, `SDNET2018.zip` was never downloaded onto local disk.

### Evidence 3: Only Crack-Seg Was Materialized
Because SDNET ingestion was bypassed, the staging script populated `datasets/crack-concrete/` solely from `datasets/crack-seg/`. In `crack-seg`, 4,028 images contain positive polygon crack annotations and exactly **1 image** (`1177.rf.6bb0830b57f7fd1ed4aa0dbabb8688c2.txt` in validation) is an empty label file.

---

## 2. Remediation Plan Executed

To solve the negative sample deficit without relying on Cloudflare-blocked CLI requests:

1. **Acquired Genuine Concrete Negatives via CC BY 4.0 Academic Benchmark:**
   - Sourced the **Middle East Technical University (METU) Concrete Crack Dataset** (*Özgenel & Sorguç, 2018*), a premier structural concrete surface dataset captured across 458 high-resolution concrete building surfaces on the university campus.
   - Sourced via Hugging Face (`mohammadnajeeb/concrete_crack_images`) under the **CC BY 4.0** license (identical terms to SDNET2018).
   - Sourced the verified `Negative/` category containing undamaged concrete building walls, columns, beams, and slabs with formwork grooves, aggregate variations, surface voids, and lighting shadows.
2. **Strict Test-Set Contamination Shield:**
   - All 404 images and 543 bounding boxes in the held-out test split (`datasets/crack-concrete/images/test/`) are **100% frozen and immutable**.
   - Before accepting any negative image, [`ingest_concrete_negatives.py`](file:///c:/Users/ahamm/Downloads/SHM AI PROJECT/SHM-AI/scripts/dataset_pipeline/ingest_concrete_negatives.py) computed SHA-256 and 64-bit perceptual `dHash` against every test image, verifying **zero duplicate or near-duplicate leakage**.
3. **Allocated Negatives to Training and Validation Only:**
   - 500 verified uncracked concrete images added to `train`.
   - 75 verified uncracked concrete images added to `val`.
4. **Created an Isolated False-Positive Benchmark:**
   - 100 verified uncracked concrete images staged in [`datasets/concrete-negatives-benchmark/`](file:///c:/Users/ahamm/Downloads/SHM AI PROJECT/SHM-AI/datasets/concrete-negatives-benchmark) to evaluate the detector's false-positive rate on undamaged concrete independently of the crack recall test set.

---

## 3. Dataset Accounting: Before vs. After Remediation

| Split | Original Images | Original Negatives | Revised Images | Revised Positives | Revised Negatives | Crack Bounding Boxes | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Train** | 3,223 | 1 | **3,723** (+500) | 3,222 | **501** | 4,214 | Revised with hard negatives |
| **Validation** | 402 | 0 | **477** (+75) | 402 | **75** | 533 | Revised with hard negatives |
| **Test (Held-Out)** | **404** | **0** | **404** (+0) | **404** | **0** | **543** | **100% Frozen & Immutable** |
| **Total Active** | **4,029** | **1** | **4,604** | **4,028** | **576** | **5,290** | **12.5% Negative Density** |
| **Isolated Benchmark** | — | — | **100** | 0 | **100** | 0 | False alarm evaluation set |

### Verified Positive-to-Negative Ratio:
- Training Split: **6.4 : 1** (3,222 positive crack crops to 501 verified uncracked concrete textures).
- Validation Split: **5.4 : 1** (402 positive crack crops to 75 verified uncracked concrete textures).
- This provides sufficient negative texture gradient for the loss function to penalize false boundary activations without starving the detector of crack recall signal.

---

## 4. Manual SDNET2018 Download Instructions (Optional Secondary Source)

If you wish to augment the pipeline further with SDNET2018 concrete walls and decks:
1. Open your web browser (which automatically solves Cloudflare challenges):
   - [Utah State University DigitalCommons SDNET2018](https://digitalcommons.usu.edu/all_datasets/48/)
   - Or [Kaggle SDNET2018 Mirror](https://www.kaggle.com/datasets/anokas/structural-defects-network-sdnet-2018)
2. Click the blue **Download** button to download `SDNET2018.zip` (1.3 GB).
3. Place `SDNET2018.zip` into `datasets/raw_downloads/SDNET2018.zip`.
4. Extract using: `Expand-Archive datasets/raw_downloads/SDNET2018.zip -DestinationPath datasets/raw_downloads/sdnet2018`.
5. Run: `python scripts/dataset_pipeline/ingest_concrete_negatives.py --sdnet-root datasets/raw_downloads/sdnet2018`.

---

## 5. Pre-Training Validation (PASS/FAIL Summary)

| Validation Gate | Requirement | Actual Status | Evidence |
| :--- | :--- | :--- | :--- |
| **1. 0-Byte Negative Labels** | Every negative image must have an exact matching 0-byte `.txt` file | **PASS** | 576 empty `.txt` files verified in train & val. |
| **2. Test Set Protection** | 404 test images must remain 100% immutable | **PASS** | Test split unchanged (404 images, 543 boxes, 0 leakage). |
| **3. Duplicate Leakage** | Zero cross-split duplicates | **PASS** | `validate_integrated_dataset` reports `leakage_detected: False`. |
| **4. Domain Cleanliness** | Concrete structures only (no asphalt, roads, traffic) | **PASS** | RDD2022 and Crack500 purged; verified campus building surfaces. |
| **5. Transfer Archive Integrity** | Packaged archive matches on-disk dataset | **PASS** | `datasets/crack-concrete.zip` (169.57 MB, SHA-256 `bbe4676...`). |
| **6. Unit Test Health** | 100% tests passing | **PASS** | 585 backend tests + 16 frontend tests passing. |
