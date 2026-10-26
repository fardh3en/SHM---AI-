"""
Verification utility for SHM-AI vision dependencies and inference runtime.

Can be run:
1. As a CLI build check: `python scripts/verify_vision_environment.py`
   (exits with code 0 on success, code 1 on failure to abort broken deployments)
2. As a module at application startup: `from scripts.verify_vision_environment import verify_vision_environment`

Security:
- Never prints or exposes secrets, tokens, or environment variables.
"""
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def verify_vision_environment(verbose: bool = True) -> dict[str, Any]:
    """
    Verify that all required vision libraries, headless bindings, compute backends,
    and model weights are importable and functional.

    Returns:
        dict with keys:
            healthy: bool
            versions: dict[str, str]
            device: str ('cpu' or 'cuda')
            model_file: str | None
            model_task: str | None
            errors: list[str]
    """
    report: dict[str, Any] = {
        "healthy": True,
        "versions": {},
        "device": "unknown",
        "model_file": None,
        "model_task": None,
        "errors": [],
    }

    # ── 1. NumPy ──
    try:
        import numpy as np
        _arr = np.zeros((8, 8), dtype=np.uint8)
        report["versions"]["numpy"] = np.__version__
    except Exception as exc:
        report["healthy"] = False
        report["errors"].append(f"numpy import failure: {exc}")

    # ── 2. Pillow ──
    try:
        import PIL
        from PIL import Image
        _img = Image.new("RGB", (8, 8), color="red")
        report["versions"]["Pillow"] = getattr(PIL, "__version__", "available")
    except Exception as exc:
        report["healthy"] = False
        report["errors"].append(f"Pillow import failure: {exc}")

    # ── 3. Headless OpenCV (cv2) ──
    try:
        import cv2
        _test_mat = np.zeros((8, 8, 3), dtype=np.uint8) if "numpy" in report["versions"] else None
        if _test_mat is not None:
            _gray = cv2.cvtColor(_test_mat, cv2.COLOR_BGR2GRAY)
        report["versions"]["cv2"] = cv2.__version__
    except Exception as exc:
        report["healthy"] = False
        report["errors"].append(
            f"cv2 (OpenCV) failure: {exc}. Ensure 'opencv-python-headless' is installed "
            "and standard 'opencv-python' is not installed to avoid missing libGL.so.1."
        )

    # ── 4. PyTorch & Torchvision ──
    try:
        import torch
        report["versions"]["torch"] = torch.__version__
        cuda_avail = torch.cuda.is_available()
        report["device"] = "cuda" if cuda_avail else "cpu"
        _tensor = torch.zeros((1, 3, 16, 16), dtype=torch.float32)
        _out = _tensor + 1.0
    except Exception as exc:
        report["healthy"] = False
        report["errors"].append(f"torch failure: {exc}")

    try:
        import torchvision
        report["versions"]["torchvision"] = getattr(torchvision, "__version__", "available")
    except Exception as exc:
        report["healthy"] = False
        report["errors"].append(f"torchvision failure: {exc}")

    # ── 5. Ultralytics YOLO ──
    try:
        import ultralytics
        from ultralytics import YOLO
        report["versions"]["ultralytics"] = getattr(ultralytics, "__version__", "available")
    except Exception as exc:
        report["healthy"] = False
        report["errors"].append(
            f"ultralytics failure: {exc}. If libGL or GUI error, install opencv-python-headless."
        )

    # ── 6. Model Weights & Initialization ──
    from backend.app.config import get_settings
    settings = get_settings()
    weights_path = settings.default_model_path

    if not weights_path.is_file():
        # Attempt auto-provisioning default nano weights
        if weights_path.name == "yolo11n-seg.pt":
            try:
                from scripts.download_weights import download_weights
                if verbose:
                    print(f"Provisioning missing default weights '{weights_path.name}'...")
                download_weights(model_name=weights_path.name, assume_yes=True)
            except Exception as dl_err:
                report["errors"].append(f"Weights auto-provisioning failed: {dl_err}")

    if weights_path.is_file():
        size_bytes = weights_path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        if size_bytes < 1_000_000:
            report["healthy"] = False
            report["errors"].append(
                f"Configured YOLO weights at '{weights_path}' are suspiciously small ({size_mb:.2f} MB). "
                "The file may be empty or truncated. Re-run 'python scripts/download_weights.py --force --yes'."
            )
        else:
            report["model_file"] = str(weights_path)
            report["model_size_mb"] = round(size_mb, 2)
            # Test loading model into YOLO
            if "ultralytics" in report["versions"]:
                try:
                    model = YOLO(str(weights_path))
                    report["model_task"] = getattr(model, "task", "segment")
                except Exception as load_err:
                    report["healthy"] = False
                    report["errors"].append(f"YOLO model load failure on weights '{weights_path}': {load_err}")
    else:
        report["healthy"] = False
        report["errors"].append(
            f"Configured YOLO weights file not found at '{weights_path}'. "
            "Run 'python scripts/download_weights.py --yes' to provision weights."
        )

    # ── Print formatted report if requested ──
    if verbose:
        print("====================================================================")
        print("SHM-AI Vision Runtime Environment Verification")
        print("====================================================================")
        for pkg in ["numpy", "Pillow", "cv2", "torch", "torchvision", "ultralytics"]:
            ver = report["versions"].get(pkg)
            if ver:
                extra = f" (Device: {report['device']})" if pkg == "torch" else ""
                print(f"  [PASS] {pkg:<14} : {ver}{extra}")
            else:
                print(f"  [FAIL] {pkg:<14} : NOT AVAILABLE")

        if report["model_file"]:
            task_str = f" (task: {report['model_task']})" if report["model_task"] else ""
            print(f"  [PASS] Model weights  : {report['model_file']}{task_str}")
        else:
            print("  [FAIL] Model weights  : MISSING")

        print("--------------------------------------------------------------------")
        if report["healthy"]:
            print("  STATUS: HEALTHY - Vision inference pipeline is verified.")
        else:
            print("  STATUS: UNHEALTHY - Mandatory dependencies failed verification.")
            for err in report["errors"]:
                print(f"    - {err}")
        print("====================================================================")

    return report


if __name__ == "__main__":
    result = verify_vision_environment(verbose=True)
    sys.exit(0 if result["healthy"] else 1)
