"""SHM-AI YOLO26 Instance Segmentation Fine-Tuning Script.

Fine-tunes YOLO26 segmentation model on prepared_crack_seg_v2 dataset.
Dataset: datasets/prepared_crack_seg_v2/crack_seg_prepared_v2.yaml
Initial Checkpoint: weights/shm_ai_yolo26n_seg_15e_best.pt
Output: runs/segment/shm_ai_yolo26_v2_finetune
"""

import os
import sys
import torch
from pathlib import Path
from ultralytics import YOLO

def main():
    print("=" * 70)
    print("SHM-AI YOLO26 SEGMENTATION FINE-TUNING")
    print("=" * 70)

    # 1. Verification of paths
    dataset_yaml = Path("datasets/prepared_crack_seg_v2/crack_seg_prepared_v2.yaml").resolve()
    checkpoint = Path("weights/shm_ai_yolo26n_seg_15e_best.pt").resolve()
    project_dir = Path("runs/segment").resolve()
    run_name = "shm_ai_yolo26_v2_finetune"

    print(f"Dataset config: {dataset_yaml}")
    print(f"Checkpoint:     {checkpoint}")
    print(f"Output target:  {project_dir / run_name}")

    if not dataset_yaml.is_file():
        raise FileNotFoundError(f"Dataset YAML not found at {dataset_yaml}")
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Initial checkpoint not found at {checkpoint}")

    # 2. Hardware / Device detection
    cuda_available = torch.cuda.is_available()
    print(f"CUDA Available: {cuda_available}")
    if cuda_available:
        device = 0
        gpu_name = torch.cuda.get_device_name(0)
        gpu_vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        print(f"CUDA Device: {gpu_name} ({gpu_vram:.2f} GB VRAM)")
    else:
        device = "cpu"
        print("Hardware Notice: CUDA GPU is not available. Using CPU for training.")

    # 3. Model initialization (from existing checkpoint, without resuming previous run history)
    print("\nLoading model from checkpoint...")
    model = YOLO(str(checkpoint))
    print(f"Model task: {model.task}")

    # 4. Launch training
    print("\nLaunching fine-tuning experiment...")
    print("Configuration: epochs=50, imgsz=640, patience=12, resume=False")
    
    results = model.train(
        data=str(dataset_yaml),
        epochs=50,
        imgsz=640,
        patience=12,
        task="segment",
        device=device,
        project=str(project_dir),
        name=run_name,
        exist_ok=True,
        resume=False,
    )
    
    print("\nTraining completed successfully.")
    return results

if __name__ == "__main__":
    main()
