#!/usr/bin/env bash
# ==============================================================================
# Render Build Script for SHM-AI Platform
# Ensures reproducible, CPU-only deep learning vision runtime on Render Free tier
# ==============================================================================
set -euo pipefail

echo "===================================================================="
echo "==> [SHM-AI Build] Step 1/5: Upgrading pip, setuptools, and wheel..."
echo "===================================================================="
pip install --upgrade pip setuptools wheel

echo "===================================================================="
echo "==> [SHM-AI Build] Step 2/5: Installing CPU-only PyTorch & Torchvision..."
echo "===================================================================="
# Direct to PyTorch CPU wheel index so 2.5GB CUDA packages are NEVER downloaded
pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

echo "===================================================================="
echo "==> [SHM-AI Build] Step 3/5: Installing application dependencies..."
echo "===================================================================="
pip install --no-cache-dir -r requirements.txt

echo "===================================================================="
echo "==> [SHM-AI Build] Step 4/5: Enforcing headless OpenCV..."
echo "===================================================================="
# Ultralytics PyPI package declares 'opencv-python' which installs GUI bindings
# that require libGL.so.1 (absent in headless cloud containers).
# Uninstall both to eliminate any mixed file state, then install headless cleanly.
pip uninstall -y opencv-python opencv-python-headless || true
pip install --no-cache-dir opencv-python-headless
python -c "import cv2; print('cv2 headless import verified:', cv2.__version__)"

echo "===================================================================="
echo "==> [SHM-AI Build] Step 5/5: Provisioning YOLO model weights..."
echo "===================================================================="
python scripts/download_weights.py --yes

echo "===================================================================="
echo "==> [SHM-AI Build] Verification: Validating vision environment..."
echo "===================================================================="
python scripts/verify_vision_environment.py

echo "===================================================================="
echo "==> [SHM-AI Build] BUILD SUCCESSFUL — Vision pipeline is ready."
echo "===================================================================="
