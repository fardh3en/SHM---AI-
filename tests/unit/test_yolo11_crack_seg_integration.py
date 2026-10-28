"""
Unit and integration tests for the fine-tuned YOLO11 concrete crack segmentation model.

Checkpoint: weights/shm_ai_crack_seg_finetune_15e_best.pt
Task: Instance segmentation
Class: crack ({0: 'crack'})

Verifies:
1. Configuration resolution and alias mapping ('yolo11n-crack-seg' vs filenames).
2. Checkpoint task ('segment'), segmentation support (True), and defect class mapping ({0: 'crack'}).
3. Real inference output: bounding box, binary mask, GeoJSON polygon, and pixel measurements.
4. Schema preservation: image dimensions, model name, class ID, and uncalibrated pixel measurements.
5. Coexistence and backward compatibility: YOLOv8 concrete detector and base YOLO11 models remain unaffected.
6. Database and structural health assessment integration using isolated in-memory sessions (no writes to live data/shm_ai.db).
"""
from pathlib import Path
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
from vision.detectors.base import RawDetection
from vision.detectors.yolo import YOLO11Detector, YOLOv8CrackDetector
from vision.pipeline.cv_pipeline import CVInferencePipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SEG_WEIGHTS_PATH = PROJECT_ROOT / "weights" / "shm_ai_crack_seg_finetune_15e_best.pt"
DET_WEIGHTS_PATH = PROJECT_ROOT / "weights" / "crack_yolov8n_concrete.pt"
BASE_WEIGHTS_PATH = PROJECT_ROOT / "weights" / "yolo11n-seg.pt"
SAMPLE_TEST_IMG = (
    PROJECT_ROOT
    / "datasets"
    / "prepared_crack_seg_v1"
    / "images"
    / "test"
    / "1616.rf.c868709931a671796794fdbb95352c5a.jpg"
)


class TestConfigResolution:
    """Verify configuration model-path resolution, alias mapping, and precedence."""

    def test_default_model_name_defaults_to_yolo11n_seg(self):
        """Default configuration remains backward-compatible with base yolo11n-seg.pt."""
        settings = Settings(MODEL_PATH=None, DEFAULT_MODEL_NAME="yolo11n-seg.pt")
        assert settings.default_model_path == settings.WEIGHTS_DIR / "yolo11n-seg.pt"

    def test_alias_resolution_for_yolo11n_crack_seg(self):
        """Friendly alias 'yolo11n-crack-seg' maps to shm_ai_crack_seg_finetune_15e_best.pt."""
        settings = Settings(DEFAULT_MODEL_NAME="yolo11n-crack-seg")
        expected = settings.WEIGHTS_DIR / "shm_ai_crack_seg_finetune_15e_best.pt"
        assert settings.default_model_path == expected

    def test_direct_filename_resolution(self):
        """Specifying checkpoint filename resolves correctly in weights directory."""
        settings = Settings(DEFAULT_MODEL_NAME="shm_ai_crack_seg_finetune_15e_best.pt")
        expected = settings.WEIGHTS_DIR / "shm_ai_crack_seg_finetune_15e_best.pt"
        assert settings.default_model_path == expected

    def test_explicit_model_path_precedence(self, tmp_path: Path):
        """Explicit MODEL_PATH takes precedence over DEFAULT_MODEL_NAME."""
        dummy_model = tmp_path / "custom_seg_checkpoint.pt"
        dummy_model.write_bytes(b"dummy")
        settings = Settings(
            MODEL_PATH=dummy_model,
            DEFAULT_MODEL_NAME="yolo11n-crack-seg",
        )
        assert settings.default_model_path == dummy_model

    def test_missing_checkpoint_raises_model_not_found(self, tmp_path: Path):
        """Missing configured model path raises ModelNotFoundError with diagnostic message."""
        missing = tmp_path / "nonexistent_seg_model.pt"
        with pytest.raises(ModelNotFoundError) as exc_info:
            YOLO11Detector(model_path=missing, device="cpu")
        assert "nonexistent_seg_model.pt" in str(exc_info.value)
        assert "were not found" in str(exc_info.value)


class TestFineTunedSegmentationModelProperties:
    """Verify architecture, task recognition, and classes of the fine-tuned segmentation model."""

    @pytest.fixture(scope="class")
    def seg_detector(self):
        if not SEG_WEIGHTS_PATH.is_file():
            pytest.skip(f"Segmentation weights not found at {SEG_WEIGHTS_PATH}")
        return YOLO11Detector(model_path=SEG_WEIGHTS_PATH, device="cpu")

    def test_task_is_segmentation(self, seg_detector: YOLO11Detector):
        """Model task must be 'segment' with segmentation support enabled."""
        assert seg_detector.task == "segment"
        assert seg_detector.supports_segmentation is True
        assert seg_detector.model_name == "shm_ai_crack_seg_finetune_15e_best.pt"

    def test_crack_class_mapping(self, seg_detector: YOLO11Detector):
        """Model must expose class 0 as 'crack' and validate as a structural defect model."""
        assert seg_detector.model_classes == {0: "crack"}
        assert seg_detector.supported_defect_classes == ["crack"]
        assert seg_detector.is_defect_model is True


class TestInferenceAndPreservationOfSegmentationData:
    """Verify prediction produces complete segmentation data without loss."""

    @pytest.fixture(scope="class")
    def seg_detector(self):
        if not SEG_WEIGHTS_PATH.is_file():
            pytest.skip(f"Segmentation weights not found at {SEG_WEIGHTS_PATH}")
        return YOLO11Detector(model_path=SEG_WEIGHTS_PATH, device="cpu", default_conf=0.25)

    def test_raw_detection_includes_mask_and_class_metadata(self, seg_detector: YOLO11Detector):
        """RawDetection contains binary mask array, bbox, and class metadata."""
        if not SAMPLE_TEST_IMG.is_file():
            pytest.skip(f"Sample test image not found at {SAMPLE_TEST_IMG}")

        from PIL import Image

        pil_img = Image.open(SAMPLE_TEST_IMG).convert("RGB")
        img_np = np.array(pil_img)

        raws = seg_detector.predict(img_np)
        assert len(raws) > 0, "Expected at least 1 detection on known test image."

        raw = raws[0]
        assert raw.defect_type == DefectType.CRACK
        assert raw.class_id == 0
        assert raw.class_name == "crack"
        assert raw.confidence >= 0.25
        assert len(raw.bbox) == 4
        # Mask must be a 2D uint8 numpy array matching input image shape
        assert raw.mask is not None
        assert isinstance(raw.mask, np.ndarray)
        assert raw.mask.shape == img_np.shape[:2]
        assert raw.mask.dtype == np.uint8
        assert raw.mask.max() == 1

    def test_cv_pipeline_preserves_polygon_and_pixel_measurements(
        self, seg_detector: YOLO11Detector
    ):
        """CVInferencePipeline extracts GeoJSON polygon and pixel measurements without fabricating calibration."""
        if not SAMPLE_TEST_IMG.is_file():
            pytest.skip(f"Sample test image not found at {SAMPLE_TEST_IMG}")

        pipeline = CVInferencePipeline(
            detector=seg_detector,
            slice_if_large=False,
            pixel_to_mm_ratio=None,  # Strictly uncalibrated
        )

        results = pipeline.run(SAMPLE_TEST_IMG)
        assert len(results) > 0

        res = results[0]
        assert res.defect_type == DefectType.CRACK
        assert res.class_id == 0
        assert res.model_name == "shm_ai_crack_seg_finetune_15e_best.pt"
        assert res.image_width == 416
        assert res.image_height == 416

        # Normalized bounding box in [0, 1]
        assert 0.0 <= res.bbox_x1 < res.bbox_x2 <= 1.0
        assert 0.0 <= res.bbox_y1 < res.bbox_y2 <= 1.0

        # GeoJSON polygon check
        assert res.mask_polygon is not None
        assert res.mask_polygon.get("type") == "Polygon"
        coords = res.mask_polygon.get("coordinates")
        assert isinstance(coords, list) and len(coords) > 0
        # Exterior ring points
        assert len(coords[0]) >= 3
        for pt in coords[0]:
            assert len(pt) == 2
            assert 0 <= pt[0] <= 416
            assert 0 <= pt[1] <= 416

        # Morphological measurements in pixels
        assert res.measurements.area_px > 0
        assert res.measurements.length_px is not None and res.measurements.length_px > 0
        assert res.measurements.width_px is not None and res.measurements.width_px > 0
        assert res.measurements.orientation_deg is not None

        # Physical calibration fields must remain None when uncalibrated
        assert res.measurements.pixel_to_mm_ratio is None
        assert res.measurements.area_mm2 is None
        assert res.measurements.length_mm is None
        assert res.measurements.width_mm is None


class TestModelCoexistenceAndPreservation:
    """Verify that YOLOv8 detection and base YOLO11 segmentation models remain available and functional."""

    def test_yolov8_concrete_detector_still_functional(self):
        """Existing crack_yolov8n_concrete.pt remains loadable and unchanged."""
        if not DET_WEIGHTS_PATH.is_file():
            pytest.skip(f"YOLOv8 weights not found at {DET_WEIGHTS_PATH}")

        detector = YOLOv8CrackDetector(model_path=DET_WEIGHTS_PATH, device="cpu")
        assert detector.task == "detect"
        assert detector.supports_segmentation is False
        assert detector.model_classes == {0: "crack"}
        assert detector.supported_defect_classes == ["crack"]
        assert detector.is_defect_model is True

    def test_base_yolo11n_seg_still_loadable(self):
        """Base yolo11n-seg.pt remains available."""
        if not BASE_WEIGHTS_PATH.is_file():
            pytest.skip(f"Base weights not found at {BASE_WEIGHTS_PATH}")

        detector = YOLO11Detector(model_path=BASE_WEIGHTS_PATH, device="cpu")
        assert detector.task == "segment"
        assert detector.supports_segmentation is True
        assert len(detector.model_classes) == 80
        # Base COCO weights have 0 structural defect classes
        assert detector.is_defect_model is False


class TestDatabaseAndAssessmentIntegration:
    """Verify end-to-end inspection execution and assessment with in-memory database isolation."""

    @pytest.mark.asyncio
    async def test_end_to_end_inspection_with_segmentation_model(
        self, db_session: AsyncSession
    ):
        """
        Verify that:
        1. Inspection completes with fine-tuned segmentation model.
        2. Detections in DB contain length_px, width_px, and mask_polygon.
        3. Structural assessment recognizes segmentation support and generates health assessment.
        4. No synthetic records are written to data/shm_ai.db (db_session is in-memory).
        """
        if not SEG_WEIGHTS_PATH.is_file() or not SAMPLE_TEST_IMG.is_file():
            pytest.skip("Segmentation weights or test image missing")

        asset_svc = AssetService(db_session)
        insp_svc = InspectionService(db_session)
        assessment_svc = StructuralAssessmentService(db_session)

        # Create asset and inspection in in-memory SQLite session
        asset = await asset_svc.create_asset(
            AssetCreate(
                name="Concrete Highway Pier 4",
                asset_type=AssetType.BRIDGE,
                construction_year=1995,
                design_life_years=75,
            )
        )
        insp = await insp_svc.create_inspection(
            InspectionCreate(
                asset_id=asset.id,
                source=InspectionSource.IMAGE,
                input_path=str(SAMPLE_TEST_IMG),
            )
        )

        detector = YOLO11Detector(
            model_path=SEG_WEIGHTS_PATH,
            device="cpu",
            default_conf=0.25,
        )
        pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)

        # Run inspection
        completed = await insp_svc.run_inspection(insp.id, pipeline=pipeline)
        assert completed is not None
        assert completed.status == InspectionStatus.COMPLETED
        assert completed.defect_count >= 1

        # Check persisted detections in DB
        db_detections = await insp_svc.get_detections(completed.id)
        assert len(db_detections) >= 1
        d = db_detections[0]
        assert d.defect_type == DefectType.CRACK
        assert d.confidence >= 0.25
        assert d.area_px is not None and d.area_px > 0
        assert d.length_px is not None and d.length_px > 0
        assert d.width_px is not None and d.width_px > 0
        assert d.mask_polygon is not None
        assert d.mask_polygon.get("type") == "Polygon"

        # Check structural health assessment
        assessment = await assessment_svc.assess_inspection(
            completed.id, force_reassess=True, detector=detector
        )
        assert assessment is not None
        assert assessment.model_name == "shm_ai_crack_seg_finetune_15e_best.pt"
        assert assessment.model_validated is True
        # Since this model supports segmentation, it is NOT blocked by the detection-only check
        assert assessment.health_score is not None
        assert 0 <= assessment.health_score <= 100
        assert assessment.risk_level in ("low", "medium", "high", "critical")
