"""
Unit and integration tests for the concrete crack YOLOv8 candidate model.

Verifies:
1. Candidate model loading, architecture, and task recognition ('detect').
2. Class mapping ({0: "crack"}) and defect class validation.
3. Valid bounding boxes, coordinates, and confidence values.
4. Clean handling of empty detections.
5. Configuration precedence (MODEL_PATH vs DEFAULT_MODEL_NAME vs WEIGHTS_DIR) and missing file handling.
6. CV inference pipeline compatibility without fabricating crack width, length, or masks.
7. Inspection service and structural health assessment integration.
"""
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings
from backend.app.core.exceptions import ModelNotFoundError
from backend.app.models.asset import AssetType
from backend.app.models.detection import DefectType
from backend.app.models.inspection import InspectionSource, InspectionStatus
from backend.app.schemas.asset import AssetCreate
from backend.app.schemas.inspection import InspectionCreate
from backend.app.services.asset_service import AssetService
from backend.app.services.inspection_service import InspectionService
from backend.app.services.structural_assessment_service import StructuralAssessmentService
from vision.detectors import IDetector, RawDetection, YOLO11Detector, YOLOv8CrackDetector
from vision.pipeline.cv_pipeline import CVInferencePipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WEIGHTS_PATH = PROJECT_ROOT / "weights" / "crack_yolov8n_concrete.pt"


def test_yolov8_crack_detector_alias():
    """Verify YOLOv8CrackDetector alias is functionally identical to YOLO11Detector."""
    assert YOLOv8CrackDetector is YOLO11Detector


class TestConfigModelPathPrecedence:
    """Verify configuration model-path resolution and precedence."""

    def test_default_backward_compatibility(self):
        """Default settings preserve yolo11n-seg.pt inside weights dir."""
        settings = Settings(MODEL_PATH=None, DEFAULT_MODEL_NAME="yolo11n-seg.pt")
        expected = settings.WEIGHTS_DIR / "yolo11n-seg.pt"
        assert settings.default_model_path == expected

    def test_explicit_model_path_absolute(self, tmp_path: Path):
        """Absolute MODEL_PATH takes highest precedence."""
        model_file = tmp_path / "custom_model.pt"
        model_file.write_bytes(b"dummy")
        settings = Settings(MODEL_PATH=model_file)
        assert settings.default_model_path == model_file

    def test_explicit_model_path_relative(self):
        """Relative MODEL_PATH resolves relative to BASE_DIR."""
        settings = Settings(MODEL_PATH=Path("weights/crack_yolov8n_concrete.pt"))
        expected = (settings.BASE_DIR / "weights/crack_yolov8n_concrete.pt").resolve()
        assert settings.default_model_path == expected

    def test_missing_model_path_does_not_silently_fallback(self, tmp_path: Path):
        """Missing configured MODEL_PATH path is preserved and raises ModelNotFoundError."""
        missing = tmp_path / "phantom_weights.pt"
        settings = Settings(MODEL_PATH=missing)
        assert settings.default_model_path == missing
        with pytest.raises(ModelNotFoundError) as exc_info:
            YOLO11Detector(model_path=settings.default_model_path, device="cpu")
        assert "were not found" in str(exc_info.value)
        assert "phantom_weights.pt" in str(exc_info.value)

    def test_default_model_name_as_concrete_model(self):
        """Configuring DEFAULT_MODEL_NAME=crack_yolov8n_concrete.pt resolves to weights dir."""
        settings = Settings(DEFAULT_MODEL_NAME="crack_yolov8n_concrete.pt")
        assert settings.default_model_path == settings.WEIGHTS_DIR / "crack_yolov8n_concrete.pt"


class TestCandidateModelProperties:
    """Verify properties of the candidate YOLOv8 concrete crack model."""

    @pytest.fixture(scope="class")
    def detector(self):
        if not WEIGHTS_PATH.is_file():
            pytest.skip(f"Staged candidate weights not found at {WEIGHTS_PATH}")
        return YOLOv8CrackDetector(model_path=WEIGHTS_PATH, device="cpu")

    def test_model_task_and_segmentation_support(self, detector: YOLOv8CrackDetector):
        """Candidate model must be a detection model (task='detect', supports_segmentation=False)."""
        assert detector.task == "detect"
        assert detector.supports_segmentation is False
        assert detector.model_name == "crack_yolov8n_concrete.pt"

    def test_model_classes_and_defect_validation(self, detector: YOLOv8CrackDetector):
        """Model must expose single crack class and validate as a structural defect model."""
        assert detector.model_classes == {0: "crack"}
        assert detector.supported_defect_classes == ["crack"]
        assert detector.is_defect_model is True

    def test_predict_returns_valid_raw_detections(self, detector: YOLOv8CrackDetector):
        """Predict on synthetic image returns RawDetection with bbox, valid confidence, and mask=None."""
        synthetic_img = np.full((640, 640, 3), 128, dtype=np.uint8)
        detections = detector.predict(synthetic_img, confidence_threshold=0.25)
        assert isinstance(detections, list)
        for det in detections:
            assert isinstance(det, RawDetection)
            assert det.defect_type == DefectType.CRACK
            assert 0.0 <= det.confidence <= 1.0
            assert len(det.bbox) == 4
            x1, y1, x2, y2 = det.bbox
            assert x1 <= x2
            assert y1 <= y2
            # Detection-only model must NOT produce masks
            assert det.mask is None

    def test_empty_detections_on_blank_canvas(self, detector: YOLOv8CrackDetector):
        """Clean uniform image produces empty detection list without crashing."""
        blank_img = np.zeros((640, 640, 3), dtype=np.uint8)
        detections = detector.predict(blank_img, confidence_threshold=0.50)
        assert isinstance(detections, list)


class TestCVPipelineWithCandidateModel:
    """Verify CVInferencePipeline behavior with the candidate detection model."""

    def test_pipeline_preserves_measurements_without_fabrication(self, tmp_path: Path):
        """Detection-only model outputs must not fabricate crack length, width, or polygon."""
        if not WEIGHTS_PATH.is_file():
            pytest.skip(f"Candidate weights not found at {WEIGHTS_PATH}")

        detector = YOLOv8CrackDetector(model_path=WEIGHTS_PATH, device="cpu")
        pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

        # Mock RawDetection output to test pipeline conversion deterministically
        mock_raw = RawDetection(
            defect_type=DefectType.CRACK,
            confidence=0.88,
            bbox=[100.0, 150.0, 300.0, 200.0],
            mask=None,
        )

        fake_rgb = np.zeros((640, 640, 3), dtype=np.uint8)
        test_file = tmp_path / "test_beam.jpg"
        test_file.write_bytes(b"image")

        with patch("vision.preprocessing.loader.ImageLoader.load_image", return_value=fake_rgb):
            with patch.object(detector, "predict", return_value=[mock_raw]):
                results = pipeline.run(test_file)

        assert len(results) == 1
        res = results[0]
        assert res.defect_type == DefectType.CRACK
        assert pytest.approx(res.confidence, 1e-4) == 0.88

        # Normalized coordinates [100/640, 150/640, 300/640, 200/640]
        assert pytest.approx(res.bbox_x1, 1e-3) == 100.0 / 640.0
        assert pytest.approx(res.bbox_y1, 1e-3) == 150.0 / 640.0
        assert pytest.approx(res.bbox_x2, 1e-3) == 300.0 / 640.0
        assert pytest.approx(res.bbox_y2, 1e-3) == 200.0 / 640.0

        # Measurements must NOT fabricate skeletonized metrics
        assert res.measurements.length_px is None
        assert res.measurements.width_px is None
        assert res.measurements.max_width_px is None
        assert res.measurements.orientation_deg is None
        assert res.mask_polygon is None

        # Area reflects bounding box envelope: 200 * 50 = 10,000 px^2
        expected_area = (300.0 - 100.0) * (200.0 - 150.0)
        assert pytest.approx(res.measurements.area_px, 1.0) == expected_area


@pytest.mark.asyncio
class TestInspectionServiceIntegration:
    """Verify inspection execution and structural assessment with candidate model."""

    async def test_end_to_end_inspection_with_candidate_model(
        self, db_session: AsyncSession, tmp_path: Path
    ):
        """Inspection execution with candidate model persists detections and leaves health score unverified."""
        if not WEIGHTS_PATH.is_file():
            pytest.skip(f"Candidate weights not found at {WEIGHTS_PATH}")

        asset_svc = AssetService(db_session)
        insp_svc = InspectionService(db_session)
        assessment_svc = StructuralAssessmentService(db_session)

        # 1. Create asset & inspection
        asset = await asset_svc.create_asset(
            AssetCreate(name="Concrete Shear Wall", asset_type=AssetType.BUILDING)
        )
        test_img = tmp_path / "concrete_shear_wall.jpg"
        test_img.write_bytes(b"dummy jpeg bytes")

        insp = await insp_svc.create_inspection(
            InspectionCreate(
                asset_id=asset.id,
                source=InspectionSource.IMAGE,
                input_path=str(test_img),
            )
        )

        detector = YOLOv8CrackDetector(model_path=WEIGHTS_PATH, device="cpu")
        pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

        # Mock realistic detection from concrete crack model
        mock_raw = RawDetection(
            defect_type=DefectType.CRACK,
            confidence=0.74,
            bbox=[50.0, 80.0, 420.0, 110.0],
            mask=None,
        )

        fake_rgb = np.full((720, 1280, 3), 120, dtype=np.uint8)
        with patch("vision.preprocessing.loader.ImageLoader.load_image", return_value=fake_rgb):
            with patch.object(detector, "predict", return_value=[mock_raw]):
                completed = await insp_svc.run_inspection(insp.id, pipeline=pipeline)

        assert completed is not None
        assert completed.status == InspectionStatus.COMPLETED
        assert completed.defect_count == 1
        # Health score must remain None for detection-only model
        assert completed.health_score is None

        # Verify persisted detections in DB
        db_detections = await insp_svc.get_detections(completed.id)
        assert len(db_detections) == 1
        d = db_detections[0]
        assert d.defect_type == DefectType.CRACK
        assert pytest.approx(d.confidence, 1e-3) == 0.74
        assert d.length_px is None
        assert d.width_px is None
        assert d.mask_polygon is None
        assert d.area_px > 0

        # Verify structural health assessment is unverified
        assessment = await assessment_svc.assess_inspection(
            completed.id, force_reassess=True, detector=detector
        )
        assert assessment is not None
        assert assessment.status == "unverified"
        assert assessment.health_score is None
        assert assessment.risk_level is None
        assert any("Sub-millimeter crack aperture" in lim for lim in assessment.limitations)
        assert "unverified pending segmentation-based width measurements" in (assessment.notes or "")

    async def test_live_sample_image_end_to_end_inspection(
        self, db_session: AsyncSession
    ):
        """End-to-end inspection on sample image 0318fe1ead09_crack_image_sg.jpeg with real candidate model."""
        sample_img = PROJECT_ROOT / "data" / "uploads" / "evidence" / "0318fe1ead09_crack_image_sg.jpeg"
        if not sample_img.is_file() or not WEIGHTS_PATH.is_file():
            pytest.skip("Sample image or candidate weights missing")

        asset_svc = AssetService(db_session)
        insp_svc = InspectionService(db_session)
        assessment_svc = StructuralAssessmentService(db_session)

        asset = await asset_svc.create_asset(
            AssetCreate(name="Severely Cracked Column", asset_type=AssetType.BUILDING)
        )
        insp = await insp_svc.create_inspection(
            InspectionCreate(
                asset_id=asset.id,
                source=InspectionSource.IMAGE,
                input_path=str(sample_img),
            )
        )

        detector = YOLOv8CrackDetector(model_path=WEIGHTS_PATH, device="cpu", default_conf=0.25)
        pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

        # Run REAL inference end-to-end without any mocks
        completed = await insp_svc.run_inspection(insp.id, pipeline=pipeline)

        assert completed is not None
        assert completed.status == InspectionStatus.COMPLETED
        assert completed.defect_count >= 1
        assert completed.health_score is None

        detections = await insp_svc.get_detections(completed.id)
        assert len(detections) >= 1
        central_crack = detections[0]
        assert central_crack.defect_type == DefectType.CRACK
        assert central_crack.confidence >= 0.25
        assert central_crack.length_px is None
        assert central_crack.width_px is None
        assert central_crack.mask_polygon is None
        assert central_crack.area_px > 0

        assessment = await assessment_svc.assess_inspection(
            completed.id, force_reassess=True, detector=detector
        )
        assert assessment is not None
        assert assessment.status == "unverified"
        assert assessment.health_score is None
        assert assessment.risk_level is None
        assert any("Sub-millimeter crack aperture" in lim for lim in assessment.limitations)
