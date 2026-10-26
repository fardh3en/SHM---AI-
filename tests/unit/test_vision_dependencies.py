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
