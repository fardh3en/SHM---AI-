"""
Unit tests for vision pipeline dependency configuration and initialization failure handling.

Verifies:
1. All core vision runtime dependencies (numpy, cv2, PIL, shapely, torch, ultralytics)
   are importable.
2. pyproject.toml includes numpy, Pillow, and opencv-python-headless in base dependencies.
3. requirements.txt is configured with CPU torch index and headless OpenCV for Render.
4. YOLO11Detector raises a clean ImportError with instructions when dependencies are missing.
5. InspectionService handles pipeline initialization failure, updates status to FAILED,
   and surfaces the exact failure reason without crashing unhandled.
6. Auto-provisioning logic triggers when default nano weights are missing on disk.
"""
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import InferenceError
from backend.app.models.asset import Asset, AssetStatus, AssetType
from backend.app.models.inspection import Inspection, InspectionStatus
from backend.app.services.inspection_service import InspectionService
from vision.detectors.yolo import YOLO11Detector


def test_runtime_vision_dependencies_importable() -> None:
    """Verify that all packages required by the CV pipeline are present in the environment."""
    import cv2
    import numpy as np
    import PIL
    import shapely
    import skimage
    import torch
    import ultralytics

    assert np is not None
    assert cv2 is not None
    assert PIL is not None
    assert shapely is not None
    assert skimage is not None
    assert torch is not None
    assert ultralytics is not None


def test_pyproject_dependencies_contain_numpy_and_imaging() -> None:
    """Verify pyproject.toml specifies numpy, Pillow, and headless OpenCV in base dependencies."""
    pyproject_path = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    assert pyproject_path.is_file()

    content = pyproject_path.read_text(encoding="utf-8")
    assert '"numpy>=' in content
    assert '"opencv-python-headless>=' in content
    assert '"Pillow>=' in content
    assert '"shapely>=' in content


def test_requirements_txt_configured_for_render() -> None:
    """Verify requirements.txt exists and contains CPU-optimized PyTorch and headless OpenCV."""
    req_path = Path(__file__).resolve().parent.parent.parent / "requirements.txt"
    assert req_path.is_file()

    content = req_path.read_text(encoding="utf-8")
    assert "--extra-index-url https://download.pytorch.org/whl/cpu" in content
    assert "numpy>=" in content
    assert "opencv-python-headless>=" in content
    assert "torch>=" in content
    assert "ultralytics>=" in content


def test_yolo_detector_missing_dependency_raises_import_error(tmp_path: Path) -> None:
    """Verify YOLO11Detector raises an explicit ImportError when dependencies are missing."""
    fake_weights = tmp_path / "model.pt"
    fake_weights.touch()

    with patch("vision.detectors.yolo._ULTRALYTICS_AVAILABLE", False):
        with pytest.raises(ImportError) as exc_info:
            YOLO11Detector(model_path=fake_weights)
        assert "Ultralytics and PyTorch are required" in str(exc_info.value)
        assert ".[vision]" in str(exc_info.value)


@pytest.mark.asyncio
async def test_inspection_service_handles_pipeline_init_failure(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Verify that InspectionService records failure when pipeline fails to initialize."""
    asset = Asset(
        name="Test Pipeline Failure Structure",
        asset_type=AssetType.BUILDING,
        status=AssetStatus.ACTIVE,
    )
    db_session.add(asset)
    await db_session.flush()

    dummy_image = tmp_path / "test_crack.jpg"
    dummy_image.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100)

    insp = Inspection(
        asset_id=asset.id,
        input_path=str(dummy_image),
        status=InspectionStatus.PENDING,
    )
    db_session.add(insp)
    await db_session.flush()

    service = InspectionService(db_session)

    # Simulate get_cv_pipeline raising ImportError: No module named 'numpy'
    with patch(
        "backend.app.dependencies.get_cv_pipeline",
        side_effect=ImportError("No module named 'numpy'"),
    ):
        with pytest.raises(InferenceError) as exc_info:
            await service.run_inspection(insp.id)

        assert "Failed to initialize vision inference pipeline" in str(exc_info.value)
        assert "numpy" in str(exc_info.value)

    # Verify inspection status in database is FAILED with explanatory error message
    updated_insp = await service.get_inspection(insp.id)
    assert updated_insp is not None
    assert updated_insp.status == InspectionStatus.FAILED
    assert "Failed to initialize vision inference pipeline" in updated_insp.error_message
    assert "numpy" in updated_insp.error_message


def test_yolo_detector_auto_provisioning_trigger(tmp_path: Path) -> None:
    """Verify that missing default nano weights trigger auto-download before failing."""
    missing_default_weights = tmp_path / "yolo11n-seg.pt"
    assert not missing_default_weights.is_file()

    # Mock download_weights to simulate successful auto-provisioning
    def fake_download(*args, **kwargs):
        missing_default_weights.touch()
        return True

    with (
        patch("scripts.download_weights.download_weights", side_effect=fake_download) as mock_dl,
        patch("vision.detectors.yolo.YOLO") as mock_yolo,
    ):
        detector = YOLO11Detector(model_path=missing_default_weights, device="cpu")
        assert detector is not None
        mock_dl.assert_called_once()
        mock_yolo.assert_called_once_with(str(missing_default_weights))


def test_yolo_detector_surfaces_underlying_import_error(tmp_path: Path) -> None:
    """Verify that YOLO11Detector preserves and surfaces the exact original import error."""
    fake_weights = tmp_path / "model.pt"
    fake_weights.touch()

    original_error = ImportError("libGL.so.1: cannot open shared object file: No such file or directory")

    with (
        patch("vision.detectors.yolo._ULTRALYTICS_AVAILABLE", False),
        patch("vision.detectors.yolo._ULTRALYTICS_IMPORT_ERROR", original_error),
    ):
        with pytest.raises(ImportError) as exc_info:
            YOLO11Detector(model_path=fake_weights)

        # Must retain original cause and error message
        assert "libGL.so.1" in str(exc_info.value)
        assert exc_info.value.__cause__ is original_error


def test_verify_vision_environment_returns_healthy() -> None:
    """Verify verify_vision_environment utility passes and captures package versions."""
    from scripts.verify_vision_environment import verify_vision_environment

    report = verify_vision_environment(verbose=False)
    assert report["healthy"] is True
    assert "numpy" in report["versions"]
    assert "Pillow" in report["versions"]
    assert "cv2" in report["versions"]
    assert "torch" in report["versions"]
    assert "torchvision" in report["versions"]
    assert "ultralytics" in report["versions"]
    assert report["device"] in ("cpu", "cuda")
    assert report["model_file"] is not None


def test_render_build_script_exists_and_configured() -> None:
    """Verify scripts/render_build.sh exists and contains essential production build steps."""
    script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "render_build.sh"
    assert script_path.is_file()

    content = script_path.read_text(encoding="utf-8")
    assert "download.pytorch.org/whl/cpu" in content
    assert "opencv-python-headless" in content
    assert "opencv-python" in content
    assert "verify_vision_environment.py" in content
    assert "download_weights.py" in content


def test_system_info_endpoint_includes_vision_runtime() -> None:
    """Verify /api/v1/system/info returns safe vision runtime diagnostics without leaking secrets."""
    from starlette.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200

    data = response.json()
    assert "vision_runtime" in data
    vr = data["vision_runtime"]
    assert "healthy" in vr
    assert vr["healthy"] is True
    assert "torch" in vr["versions"]
    assert "ultralytics" in vr["versions"]


def test_verify_vision_environment_rejects_detection_model(tmp_path: Path) -> None:
    """Regression test: verify_vision_environment must reject detection-only models (task != 'segment')."""
    from unittest.mock import MagicMock
    from scripts.verify_vision_environment import verify_vision_environment

    fake_weights = tmp_path / "weights" / "shm_ai_yolo26n_seg_15e_best.pt"
    fake_weights.parent.mkdir(parents=True, exist_ok=True)
    fake_weights.write_bytes(b"\x00" * 1_500_000)

    mock_model = MagicMock()
    mock_model.task = "detect"

    with patch("backend.app.config.get_settings") as mock_settings:
        mock_settings.return_value.default_model_path = fake_weights
        with patch("ultralytics.YOLO", return_value=mock_model):
            report = verify_vision_environment(verbose=False)
            assert report["healthy"] is False
            assert report["model_task"] == "detect"
            assert any("requires an instance segmentation model ('segment')" in e for e in report["errors"])


def test_alias_resolution_for_legacy_best_pt() -> None:
    """Regression test: verify that legacy 'best.pt' and default aliases resolve to YOLO26 segmentation checkpoint."""
    from backend.app.config import Settings

    # Default model setting is now yolo26n-crack-seg
    s_default = Settings()
    assert s_default.DEFAULT_MODEL_NAME == "yolo26n-crack-seg"
    assert s_default.default_model_path.name == "shm_ai_yolo26n_seg_15e_best.pt"

    # Legacy Render dashboard override: DEFAULT_MODEL_NAME=best.pt
    s_best_pt = Settings(DEFAULT_MODEL_NAME="best.pt")
    assert s_best_pt.default_model_path.name == "shm_ai_yolo26n_seg_15e_best.pt"

    # Legacy Render dashboard override: DEFAULT_MODEL_NAME=best
    s_best = Settings(DEFAULT_MODEL_NAME="best")
    assert s_best.default_model_path.name == "shm_ai_yolo26n_seg_15e_best.pt"

    # Explicit segmentation alias
    s_seg = Settings(DEFAULT_MODEL_NAME="yolo26n-crack-seg")
    assert s_seg.default_model_path.name == "shm_ai_yolo26n_seg_15e_best.pt"


def test_verify_vision_environment_missing_weights_and_invalid_alias(tmp_path: Path) -> None:
    """Verify that an unmapped invalid alias or missing model file fails verification cleanly."""
    from scripts.verify_vision_environment import verify_vision_environment

    missing_weights = tmp_path / "weights" / "invalid_nonexistent_model.pt"

    with patch("backend.app.config.get_settings") as mock_settings:
        mock_settings.return_value.default_model_path = missing_weights
        report = verify_vision_environment(verbose=False)
        assert report["healthy"] is False
        assert any("file not found" in e.lower() for e in report["errors"])

