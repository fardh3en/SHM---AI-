# SHM-AI: Concrete Crack Detection Model Acceptance Checklist & Evaluation Protocol

**Project:** SHM-AI (Structural Health Monitoring AI Platform)  
**Target Model:** Retrained YOLOv8 Nano (`crack_yolov8n_concrete.pt`)  
**Baseline Model:** Current Production `best.pt` (`048e18345da67b9e2be3f8183c6ae2a7918edd0aa71c405355af46d805be8a21`)  
**Target Domain:** Concrete Infrastructure (Columns, Beams, Walls, Slabs)  
**Status:** Concrete Acceptance Protocol Established  

---

## 1. Acceptance Gates & Performance Matrix

| Evaluation Criterion | Production Baseline (`best.pt`) | Minimum Candidate Gate | Target Performance | Candidate Actual | Pass / Fail |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Validation mAP@0.50** | 0.582 (estimated) | $\ge \mathbf{0.680}$ | $\ge 0.750$ | `[Pending Eval]` | Pending |
| **Validation mAP@0.50-0.95** | 0.315 (estimated) | $\ge \mathbf{0.400}$ | $\ge 0.480$ | `[Pending Eval]` | Pending |
| **Test Set Recall (@ 0.25 Conf)** | ~0.490 | $\ge \mathbf{0.750}$ | $\ge 0.850$ | `[Pending Eval]` | Pending |
| **Test Set Precision (@ 0.50 Conf)**| ~0.550 | $\ge \mathbf{0.700}$ | $\ge 0.800$ | `[Pending Eval]` | Pending |
| **Concrete Column Crack Detection** | **FAILED (Missed)** | **DETECTED ($\ge 50\%$)** | Detected $\ge 65\%$ | `[Pending Eval]` | Pending |
| **Column Edge Spurious Detections** | **2 FPs (26.0%, 27.3%)** | $\mathbf{\le 0\text{ FPs}}$ | 0 FPs at conf $\ge 0.25$ | `[Pending Eval]` | Pending |
| **Concrete Wall Crack Detection** | 48.9% Conf | $\ge \mathbf{60.0\%}$ | $\ge 75.0\%$ | `[Pending Eval]` | Pending |
| **Uncracked Concrete Wall (UW)** | High false alarm risk | **0 False Positives** | 0 detections $\ge 0.25$ | `[Pending Eval]` | Pending |
| **CPU Inference Latency (Local)** | 62 ms | $\le \mathbf{100\text{ ms}}$ | $\le 75\text{ ms}$ | `[Pending Eval]` | Pending |
| **GPU Inference Latency (Colab T4)** | ~6.5 ms | $\le \mathbf{15\text{ ms}}$ | $\le 8\text{ ms}$ | `[Pending Eval]` | Pending |
| **Model Weights File Size** | 6.25 MB | $\le \mathbf{12.0\text{ MB}}$ | $\le 6.5\text{ MB}$ | `[Pending Eval]` | Pending |

---

## 2. Four-Stage Acceptance Protocol

### Stage 1: Quantitative Validation on Concrete Test Set
The candidate model must be evaluated on the 10% held-out test split of `datasets/crack-concrete/` using `model.val(split='test')`:
```python
from ultralytics import YOLO

model = YOLO("crack_yolov8n_concrete.pt")
metrics = model.val(data="datasets/crack-concrete.yaml", split="test", conf=0.25, iou=0.60)

print(f"mAP50:     {metrics.box.map50:.4f}")
print(f"mAP50-95:  {metrics.box.map:.4f}")
print(f"Precision: {metrics.box.mp:.4f}")
print(f"Recall:    {metrics.box.mr:.4f}")
```

### Stage 2: Structural Defect Benchmark Tests
1. **Concrete Column with Vertical Crack:**
   - Must detect the central vertical shear crack (confidence $\ge 50\%$).
   - Must suppress edge false alarms along the column/background boundary.
2. **Concrete Beam & Wall Cracks:**
   - Must detect diagonal shear and flexural cracks on concrete surfaces.
3. **Uncracked Concrete Wall Negative (SDNET UW):**
   - Must yield zero false detections at confidence $\ge 0.25$.

### Stage 3: Operational Latency Verification
CPU forward pass must be $\le 100$ ms for 640×640 input resolution.

### Stage 4: Non-Destructive Deployment
Deploy to Preview first by updating `MODEL_WEIGHTS_PATH=crack_yolov8n_concrete.pt`. Baseline `best.pt` remains available for instantaneous rollback.
