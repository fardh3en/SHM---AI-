"""
Unit tests for Inspection Studio vision pipeline validation and failure recovery.

Verifies:
1. Inspections with no input_path reject inference, update status to FAILED, and explain missing evidence.
2. Inspections with non-existent input_path reject inference and update status to FAILED.
3. Missing model weights raise ModelNotFoundError without triggering automatic downloads.
4. Inspections with valid evidence execute inference and create Detection records.
5. Inspections in FAILED status can be updated with valid evidence and retried successfully.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from backend.app.core.exceptions import ModelNotFoundError, ValidationError
from backend.app.models.asset import Asset, AssetStatus, AssetType
from backend.app.models.detection import DefectType, Detection
from backend.app.models.inspection import Inspection, InspectionSource, InspectionStatus
from backend.app.services.inspection_service import InspectionService
from vision.detectors.base import IDetector, RawDetection
from vision.detectors.yolo import YOLO11Detector
from vision.pipeline.cv_pipeline import CVInferencePipeline


class DummyDetector(IDetector):
    """Simple test detector returning one defect without loading model weights."""
    @property
    def model_name(self) -> str:
        return "dummy-model.pt"

    @property
    def device(self) -> str:
        return "cpu"

    def predict(self, image, confidence_threshold=None):
        return [
            RawDetection(
                defect_type=DefectType.CRACK,
                confidence=0.88,
                bbox=[10.0, 20.0, 50.0, 100.0],
                mask=None,
            )
        ]


@pytest.mark.asyncio
async def test_run_inspection_missing_evidence_fails_gracefully(db_session):
    """An inspection with no input_path must fail with a clear validation error."""
    asset = Asset(
        name="Test Pier Failure Case",
        asset_type=AssetType.BRIDGE,
        status=AssetStatus.ACTIVE,
    )
    db_session.add(asset)
    await db_session.flush()

    insp = Inspection(
        asset_id=asset.id,
        status=InspectionStatus.PENDING,
        source=InspectionSource.IMAGE,
        input_path=None,
    )
    db_session.add(insp)
    await db_session.commit()

    service = InspectionService(db_session)
    with pytest.raises(ValidationError) as exc_info:
        await service.run_inspection(insp.id)

    assert "no photographic evidence" in str(exc_info.value).lower()

    # Verify database record updated to FAILED with explanation
    updated = await service.get_inspection(insp.id)
    assert updated.status == InspectionStatus.FAILED
    assert "no photographic evidence" in updated.error_message.lower()


@pytest.mark.asyncio
async def test_run_inspection_invalid_evidence_path(db_session):
    """An inspection referencing a non-existent file on disk must fail gracefully."""
    asset = Asset(
        name="Test Tunnel Failure Case",
        asset_type=AssetType.TUNNEL,
        status=AssetStatus.ACTIVE,
    )
    db_session.add(asset)
    await db_session.flush()

    insp = Inspection(
        asset_id=asset.id,
        status=InspectionStatus.PENDING,
        source=InspectionSource.IMAGE,
        input_path="/uploads/nonexistent_file_9999.jpg",
    )
    db_session.add(insp)
    await db_session.commit()

    service = InspectionService(db_session)
    with pytest.raises(ValidationError) as exc_info:
        await service.run_inspection(insp.id)

    assert "not found on the server filesystem" in str(exc_info.value)

    updated = await service.get_inspection(insp.id)
    assert updated.status == InspectionStatus.FAILED
    assert "not found on the server filesystem" in updated.error_message


def test_yolo_missing_weights_raises_model_not_found(tmp_path):
    """YOLO11Detector must raise ModelNotFoundError if weights are missing and not auto-download."""
    phantom_weights = tmp_path / "weights" / "missing_yolo.pt"
    assert not phantom_weights.exists()

    with pytest.raises(ModelNotFoundError) as exc_info:
        YOLO11Detector(model_path=phantom_weights)

    assert "not found" in str(exc_info.value).lower()
    assert "download_weights.py" in str(exc_info.value)
    # Ensure no file was created on disk by automatic download
    assert not phantom_weights.exists()


@pytest.mark.asyncio
async def test_run_inspection_successful_inference(db_session, tmp_path):
    """With valid image evidence and a pipeline, inference completes and populates detections."""
    # Create a dummy image
    import cv2
    import numpy as np

    img_file = tmp_path / "test_surface.jpg"
    cv2.imwrite(str(img_file), np.zeros((400, 400, 3), dtype=np.uint8))

    asset = Asset(
        name="Test Deck Success Case",
        asset_type=AssetType.BUILDING,
        status=AssetStatus.ACTIVE,
    )
    db_session.add(asset)
    await db_session.flush()

    insp = Inspection(
        asset_id=asset.id,
        status=InspectionStatus.PENDING,
        source=InspectionSource.IMAGE,
        input_path=str(img_file),
    )
    db_session.add(insp)
    await db_session.commit()

    mock_pipeline = CVInferencePipeline(detector=DummyDetector(), slice_if_large=False)
    service = InspectionService(db_session)

    result = await service.run_inspection(insp.id, pipeline=mock_pipeline)

    assert result.status == InspectionStatus.COMPLETED
    assert result.defect_count == 1
    assert result.processing_time_ms is not None

    detections = await service.get_detections(insp.id)
    assert len(detections) == 1
    assert detections[0].defect_type == DefectType.CRACK


@pytest.mark.asyncio
async def test_run_inspection_retry_recovery_after_failure(db_session, tmp_path):
    """An inspection in FAILED status can be updated with valid evidence and retried successfully."""
    import cv2
    import numpy as np

    img_file = tmp_path / "recovered_evidence.jpg"
    cv2.imwrite(str(img_file), np.zeros((400, 400, 3), dtype=np.uint8))

    asset = Asset(
        name="Test Flyover Recovery Case",
        asset_type=AssetType.ROAD,
        status=AssetStatus.ACTIVE,
    )
    db_session.add(asset)
    await db_session.flush()

    # Initially failed inspection with no evidence
    insp = Inspection(
        asset_id=asset.id,
        status=InspectionStatus.FAILED,
        source=InspectionSource.IMAGE,
        input_path=None,
        error_message="Initial missing evidence failure",
    )
    db_session.add(insp)
    await db_session.commit()

    service = InspectionService(db_session)

    # 1. Update with valid evidence and reset status
    from backend.app.schemas.inspection import InspectionUpdate
    await service.update_inspection(
        insp.id,
        InspectionUpdate(input_path=str(img_file), status=InspectionStatus.PENDING, error_message=None),
    )

    # 2. Retry run
    mock_pipeline = CVInferencePipeline(detector=DummyDetector(), slice_if_large=False)
    recovered = await service.run_inspection(insp.id, pipeline=mock_pipeline)

    assert recovered.status == InspectionStatus.COMPLETED
    assert recovered.defect_count == 1
    assert recovered.error_message is None


@pytest.mark.asyncio
async def test_run_inspection_pipeline_error_marks_failed(db_session, tmp_path):
    """If pipeline.run throws an exception, the inspection is cleanly marked FAILED."""
    import cv2
    import numpy as np

    img_file = tmp_path / "broken_test.jpg"
    cv2.imwrite(str(img_file), np.zeros((200, 200, 3), dtype=np.uint8))

    asset = Asset(name="Fault Test Bridge", asset_type=AssetType.BRIDGE, status=AssetStatus.ACTIVE)
    db_session.add(asset)
    await db_session.flush()

    insp = Inspection(
        asset_id=asset.id,
        status=InspectionStatus.PENDING,
        source=InspectionSource.IMAGE,
        input_path=str(img_file),
    )
    db_session.add(insp)
    await db_session.commit()

    class FaultyPipeline:
        def run(self, path):
            raise RuntimeError("PyTorch tensor allocation crash during inference")

    service = InspectionService(db_session)
    result = await service.run_inspection(insp.id, pipeline=FaultyPipeline())

    assert result.status == InspectionStatus.FAILED
    assert "PyTorch tensor allocation crash" in result.error_message

    # Ensure DB record is also updated
    in_db = await service.get_inspection(insp.id)
    assert in_db.status == InspectionStatus.FAILED
    assert in_db.error_message == result.error_message


@pytest.mark.asyncio
async def test_run_inspection_persistence_error_marks_failed(db_session, tmp_path):
    """If database persistence or assessment fails, the inspection is updated to FAILED rather than left in PROCESSING."""
    import cv2
    import numpy as np

    img_file = tmp_path / "persist_fault_test.jpg"
    cv2.imwrite(str(img_file), np.zeros((200, 200, 3), dtype=np.uint8))

    asset = Asset(name="Persist Fault Bridge", asset_type=AssetType.BRIDGE, status=AssetStatus.ACTIVE)
    db_session.add(asset)
    await db_session.flush()

    insp = Inspection(
        asset_id=asset.id,
        status=InspectionStatus.PENDING,
        source=InspectionSource.IMAGE,
        input_path=str(img_file),
    )
    db_session.add(insp)
    await db_session.commit()

    service = InspectionService(db_session)
    mock_pipeline = CVInferencePipeline(detector=DummyDetector(), slice_if_large=False)

    # Patch detection repo bulk_create to simulate database error
    with patch.object(service._detection_repo, "bulk_create", side_effect=Exception("Database lock error on insert")):
        result = await service.run_inspection(insp.id, pipeline=mock_pipeline)

    assert result.status == InspectionStatus.FAILED
    assert "Database lock error" in result.error_message

    in_db = await service.get_inspection(insp.id)
    assert in_db.status == InspectionStatus.FAILED
    assert "Database lock error" in in_db.error_message
