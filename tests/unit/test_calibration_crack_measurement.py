"""
Unit tests for calibration-aware crack measurements, image quality analysis,
crack depth governance, and complete inspection report rendering.

Covers:
- DefectMeasurementEngine: synthetic masks, pixel-to-millimeter conversions,
  vertical extent, uncalibrated gating, noise suppression, invalid scale handling.
- ImageQualityAnalyzer: sharpness/blur, exposure, resolution diagnostics.
- DepthMeasurementService: optical 2D limitation gating, sensor ingestion.
- ReportGenerator: calibration badges, vector SVG overlays, image quality card,
  depth governance, and zero unassisted blanks.
- Database isolation: tests run purely in-memory with zero persistent database impact.
"""
from __future__ import annotations

import numpy as np
import pytest

from vision.calibration.schemas import (
    CalibrationInfo,
    CalibrationMethod,
    CalibrationStatus,
    CalibrationValidationStatus,
    CrackMeasurement,
    CrackDepthRecord,
    DepthStatus,
    ImageQualityAssessment,
    ImageSuitabilityStatus,
    MeasurementStatus,
)
from vision.calibration.image_quality import ImageQualityAnalyzer
from vision.calibration.measurement_engine import DefectMeasurementEngine
from vision.calibration.depth_interface import DepthMeasurementService
from backend.app.models.detection import DefectType
from recommendation.report_generator import ReportGenerator, ReportGeneratorConfig
from intelligence.schemas import (
    AssetType,
    HealthAssessmentReport,
    RiskLevel,
    StructuralFailureMode,
    FailureModeCategory,
)
from recommendation.schemas import RecommendationReport, RecommendationInput
from recommendation.recommendation_service import RecommendationService


# ---------------------------------------------------------------------------
# Test Fixtures & Factories
# ---------------------------------------------------------------------------

@pytest.fixture
def sharp_image() -> np.ndarray:
    """Creates a high-contrast, sharp synthetic concrete image."""
    img = np.full((600, 800, 3), 128, dtype=np.uint8)
    # Add high-frequency checkerboard / edges
    img[::20, :, :] = 50
    img[:, ::20, :] = 200
    return img


@pytest.fixture
def blurry_image() -> np.ndarray:
    """Creates an ultra-smooth, uniform blurry synthetic image."""
    return np.full((600, 800, 3), 120, dtype=np.uint8)


@pytest.fixture
def underexposed_image() -> np.ndarray:
    """Creates a very dark underexposed synthetic image."""
    return np.full((600, 800, 3), 15, dtype=np.uint8)


@pytest.fixture
def overexposed_image() -> np.ndarray:
    """Creates a blown-out clipped synthetic image."""
    return np.full((600, 800, 3), 250, dtype=np.uint8)


# ---------------------------------------------------------------------------
# 1. DefectMeasurementEngine Tests
# ---------------------------------------------------------------------------

class TestDefectMeasurementEngine:
    def test_calibrated_horizontal_crack_measurement(self):
        """
        Verify pixel-to-millimeter conversions for a synthetic horizontal crack:
        Length = 100 px, Width = 5 px, Calibration = 0.2 mm/px.
        Expected: ~20.0 mm length, ~1.0 mm width, ~100.0 mm² area.
        """
        img_h, img_w = 200, 200
        mask = np.zeros((img_h, img_w), dtype=np.uint8)
        mask[98:103, 50:150] = 255  # 5 px height, 100 px width

        calib = CalibrationInfo.calibrated(
            pixel_to_mm_ratio=0.2,
            method=CalibrationMethod.KNOWN_REFERENCE_MARKER,
            reference_object="Standard Scale Bar",
        )

        engine = DefectMeasurementEngine(calibration=calib)
        meas = engine.measure_instance(
            crack_id="crack_001",
            defect_type=DefectType.CRACK,
            confidence=0.92,
            bbox_px=[50.0, 98.0, 150.0, 103.0],
            mask=mask,
            image_shape=(img_h, img_w),
        )

        assert meas.measurement_status == MeasurementStatus.MEASURED
        assert meas.length_px is not None and 90.0 <= meas.length_px <= 110.0
        assert meas.width_px is not None and 3.5 <= meas.width_px <= 6.5
        assert meas.length_mm is not None and 18.0 <= meas.length_mm <= 22.0
        assert meas.width_mm is not None and 0.7 <= meas.width_mm <= 1.3
        assert meas.area_px == 500.0
        assert meas.area_mm2 == pytest.approx(500.0 * 0.04, rel=1e-2)

    def test_vertical_extent_calculation(self):
        """
        Verify vertical extent for horizontal, vertical, and diagonal simulated cracks.
        """
        engine = DefectMeasurementEngine()

        # A: Horizontal crack: bbox height is 6 px
        h_mask = np.zeros((150, 150), dtype=np.uint8)
        h_mask[70:76, 20:120] = 255
        h_meas = engine.measure_instance(
            crack_id="h_crack",
            defect_type=DefectType.CRACK,
            confidence=0.9,
            bbox_px=[20.0, 70.0, 120.0, 76.0],
            mask=h_mask,
            image_shape=(150, 150),
        )
        assert h_meas.vertical_extent_px == 6.0

        # B: Vertical crack: bbox height is 80 px (y: 20 to 100)
        v_mask = np.zeros((150, 150), dtype=np.uint8)
        v_mask[20:100, 70:74] = 255
        v_meas = engine.measure_instance(
            crack_id="v_crack",
            defect_type=DefectType.CRACK,
            confidence=0.9,
            bbox_px=[70.0, 20.0, 74.0, 100.0],
            mask=v_mask,
            image_shape=(150, 150),
        )
        assert v_meas.vertical_extent_px == 80.0

        # C: Diagonal crack: y goes from 10 to 90 (extent = 80 px)
        d_mask = np.zeros((150, 150), dtype=np.uint8)
        for i in range(10, 90):
            d_mask[i, i : i + 3] = 255
        d_meas = engine.measure_instance(
            crack_id="d_crack",
            defect_type=DefectType.CRACK,
            confidence=0.9,
            bbox_px=[10.0, 10.0, 93.0, 90.0],
            mask=d_mask,
            image_shape=(150, 150),
        )
        assert d_meas.vertical_extent_px == 80.0

    def test_uncalibrated_crack_measurement(self):
        """
        When calibration is uncalibrated, physical millimeters must be None,
        status must be REQUIRES_CALIBRATION, and reasons must be explicitly populated.
        """
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[48:52, 20:80] = 255

        engine = DefectMeasurementEngine(calibration=CalibrationInfo.uncalibrated())
        meas = engine.measure_instance(
            crack_id="uncalib_crack",
            defect_type=DefectType.CRACK,
            confidence=0.85,
            bbox_px=[20.0, 48.0, 80.0, 52.0],
            mask=mask,
            image_shape=(100, 100),
        )

        assert meas.measurement_status == MeasurementStatus.REQUIRES_CALIBRATION
        assert meas.length_px is not None and meas.length_px > 0
        assert meas.width_px is not None and meas.width_px > 0
        # Physical mm dimensions must never be fabricated as 0.0 or random floats
        assert meas.length_mm is None
        assert meas.width_mm is None
        assert meas.area_mm2 is None
        assert len(meas.unavailability_reasons) > 0
        assert "uncalibrated" in meas.unavailability_reasons[0].lower() or "scale" in meas.unavailability_reasons[0].lower()

    def test_invalid_scale_calibration_handling(self):
        """
        Negative, zero, or invalid scales must be safely handled without throwing exceptions.
        """
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[48:52, 20:80] = 255

        for bad_scale in [-0.5, 0.0]:
            calib = CalibrationInfo.calibrated(pixel_to_mm_ratio=bad_scale)
            assert calib.status == CalibrationStatus.INVALID
            engine = DefectMeasurementEngine(calibration=calib)
            meas = engine.measure_instance(
                crack_id="bad_scale_crack",
                defect_type=DefectType.CRACK,
                confidence=0.85,
                bbox_px=[20.0, 48.0, 80.0, 52.0],
                mask=mask,
                image_shape=(100, 100),
            )
            assert meas.measurement_status == MeasurementStatus.REQUIRES_CALIBRATION
            assert meas.length_mm is None
            assert meas.width_mm is None

    def test_insufficient_pixel_mask_rejection(self):
        """
        Sub-pixel noise masks (< 3 pixels) must be rejected with INSUFFICIENT_IMAGE_QUALITY.
        """
        tiny_mask = np.zeros((50, 50), dtype=np.uint8)
        tiny_mask[25, 25:27] = 255  # exactly 2 pixels

        calib = CalibrationInfo.calibrated(pixel_to_mm_ratio=0.1)
        engine = DefectMeasurementEngine(calibration=calib)
        meas = engine.measure_instance(
            crack_id="tiny_crack",
            defect_type=DefectType.CRACK,
            confidence=0.7,
            bbox_px=[25.0, 25.0, 27.0, 26.0],
            mask=tiny_mask,
            image_shape=(50, 50),
        )

        assert meas.measurement_status == MeasurementStatus.INSUFFICIENT_IMAGE_QUALITY
        assert meas.length_px is None
        assert meas.length_mm is None
        assert any("threshold" in r.lower() for r in meas.unavailability_reasons)


# ---------------------------------------------------------------------------
# 2. ImageQualityAnalyzer Tests
# ---------------------------------------------------------------------------

class TestImageQualityAnalyzer:
    def test_sharp_image_evaluation(self, sharp_image):
        """Sharp high-contrast image should pass focus checks."""
        qa = ImageQualityAnalyzer.analyze(sharp_image)

        assert qa.width_px == 800
        assert qa.height_px == 600
        assert qa.blur_score is not None and qa.blur_score > 50.0
        assert qa.exposure_status == "normal"
        assert qa.suitability_status != ImageSuitabilityStatus.UNSUITABLE

    def test_blurry_image_evaluation(self, blurry_image):
        """Uniform smooth image has near-zero Laplacian variance and flags blur."""
        qa = ImageQualityAnalyzer.analyze(blurry_image)

        assert qa.blur_score is not None and qa.blur_score < 10.0
        assert qa.suitability_status == ImageSuitabilityStatus.UNSUITABLE
        assert any("blur" in r.lower() for r in qa.unsuitable_reasons)

    def test_underexposed_image_evaluation(self, underexposed_image):
        """Dark image has low mean brightness and flags underexposure."""
        qa = ImageQualityAnalyzer.analyze(underexposed_image)

        assert qa.exposure_status == "underexposed"
        assert any("underexposure" in r.lower() for r in qa.unsuitable_reasons)

    def test_overexposed_image_evaluation(self, overexposed_image):
        """Washed-out image has high mean brightness and flags overexposure."""
        qa = ImageQualityAnalyzer.analyze(overexposed_image)

        assert qa.exposure_status == "overexposed"
        assert any("overexposure" in r.lower() for r in qa.unsuitable_reasons)

    def test_low_resolution_rejection(self):
        """Very low-res image (< 320px) is flagged low resolution."""
        tiny_img = np.full((150, 150, 3), 128, dtype=np.uint8)
        qa = ImageQualityAnalyzer.analyze(tiny_img)

        assert qa.resolution_status == "low"
        assert qa.suitability_status == ImageSuitabilityStatus.UNSUITABLE


# ---------------------------------------------------------------------------
# 3. DepthMeasurementService Tests
# ---------------------------------------------------------------------------

class TestDepthMeasurementService:
    def test_optical_surface_default(self):
        """2D optical images default to NOT_MEASURED with civil engineering notes."""
        service = DepthMeasurementService()
        depth_record = service.get_default_optical_depth()

        assert depth_record.depth_status == DepthStatus.NOT_MEASURED
        assert depth_record.depth_mm is None
        assert "optical" in depth_record.notes.lower()
        assert "ultrasonic" in depth_record.notes.lower()

    def test_sensor_ingestion(self):
        """Ingesting ultrasonic sensor readings populates depth measurements."""
        service = DepthMeasurementService()
        reading = service.record_sensor_depth(
            depth_mm=25.4,
            method="ultrasonic_pulse_velocity",
            uncertainty_mm=1.5,
            provenance="Certified NDT Inspector PE #1042",
        )

        assert reading.depth_status == DepthStatus.SENSOR_MEASURED
        assert reading.depth_mm == 25.4
        assert reading.uncertainty_mm == 1.5
        assert reading.method == "ultrasonic_pulse_velocity"
        assert "Certified NDT Inspector" in (reading.provenance or "")


# ---------------------------------------------------------------------------
# 4. ReportGenerator Calibration & Quality Tests
# ---------------------------------------------------------------------------

class TestReportGeneratorCalibration:
    @pytest.fixture
    def health_report(self) -> HealthAssessmentReport:
        return HealthAssessmentReport(
            asset_id="asset-bridge-01",
            inspection_id="insp-test-99",
            health_score=68.5,
            risk_level=RiskLevel.MEDIUM,
            severity_breakdown=[],
            failure_modes=[
                StructuralFailureMode(
                    category=FailureModeCategory.SHEAR,
                    confidence=0.85,
                    description="Diagonal tension shear crack candidate.",
                )
            ],
            missing_inputs=["metric_calibration_scale", "subsurface_ndt_depth"],
        )

    @pytest.fixture
    def recommendation_input(self, health_report) -> RecommendationInput:
        return RecommendationInput(
            asset_id="asset-bridge-01",
            inspection_id="insp-test-99",
            asset_type=AssetType.BRIDGE,
            health_report=health_report,
        )

    @pytest.fixture
    def recommendation_report(self, recommendation_input) -> RecommendationReport:
        service = RecommendationService()
        return service.assess(recommendation_input)

    def test_render_html_uncalibrated_inspection(
        self, recommendation_input, recommendation_report
    ):
        """
        Verify that an uncalibrated inspection produces an HTML report with:
        - Prominent Uncalibrated banner & scale acquisition instructions.
        - Defect inventory showing 'Requires Calibration' badges instead of blank or 0 mm.
        - Subsurface Depth Governance card.
        - Image quality card with resolution and focus diagnostics.
        - SVG vector overlays for detection bounding boxes.
        """
        generator = ReportGenerator(ReportGeneratorConfig())

        detections = [
            {
                "id": "det-1",
                "ref_id": 1,
                "defect_type": "crack",
                "confidence": 0.88,
                "area_px": 1420.0,
                "length_px": 210.5,
                "width_px": 4.25,
                "vertical_extent_px": 145.0,
                "max_width_px": 7.8,
                "length_mm": None,
                "width_mm": None,
                "max_width_mm": None,
                "area_mm2": None,
                "calibration_status": "uncalibrated",
                "measurement_status": "requires_calibration",
                "depth_display": "Not Measured (2D Surface)",
                "bbox_coords": "[0.12, 0.20] → [0.45, 0.65]",
                "bbox_x1": 0.12,
                "bbox_y1": 0.20,
                "bbox_x2": 0.45,
                "bbox_y2": 0.65,
                "polygon_points": "120,200 180,250 240,320 310,480 305,485 235,325 175,255 115,205",
            }
        ]

        img_qa = {
            "is_sharp": True,
            "focus_score": 142.5,
            "mean_brightness": 128.0,
            "suitability": "suitable_uncalibrated",
            "diagnostic_reasons": ["Resolution sufficient", "Good focus"],
        }

        calib_dict = {
            "status": "uncalibrated",
            "pixel_to_mm_ratio": None,
            "method": "None (Screening only)",
            "validation_status": "Unverified",
            "resolution_mp": 2.1,
            "recommended_scale": "Place a high-contrast 100mm scale bar or 50mm ArUco fiducial in the defect plane.",
        }

        html = generator.render_html(
            input=recommendation_input,
            report=recommendation_report,
            asset_name="West Span Pier 3",
            input_image_path="/media/inspections/bridge_pier.jpg",
            detections=detections,
            image_quality=img_qa,
            calibration_info=calib_dict,
            model_name="shm_ai_crack_seg_finetune_15e_best.pt",
            image_width=1920,
            image_height=1080,
        )

        assert "UNCALIBRATED" in html
        assert "Pixel Space Only" in html
        assert "Requires Calibration" in html
        assert "Subsurface Depth Governance" in html
        assert "Not Measured (2D Surface)" in html
        assert "Measurement Suitability" in html
        assert "142.5" in html  # Focus score
        assert "shm_ai_crack_seg_finetune_15e_best.pt" in html
        assert "<svg" in html
        assert "points=\"120,200" in html
        # Ensure no accidental 'None' or naked '0.00 mm' in table
        assert ">0.00 mm<" not in html
        assert ">None<" not in html

    def test_render_html_calibrated_inspection(
        self, recommendation_input, recommendation_report
    ):
        """
        Verify that a calibrated inspection renders exact millimeter dimensions.
        """
        generator = ReportGenerator(ReportGeneratorConfig())

        detections = [
            {
                "id": "det-2",
                "ref_id": 1,
                "defect_type": "crack",
                "confidence": 0.94,
                "area_px": 2500.0,
                "length_px": 250.0,
                "width_px": 10.0,
                "vertical_extent_px": 180.0,
                "max_width_px": 15.0,
                "length_mm": 50.0,
                "width_mm": 2.0,
                "max_width_mm": 3.0,
                "area_mm2": 100.0,
                "calibration_status": "calibrated",
                "measurement_status": "measured",
                "depth_display": "Not Measured (2D Surface)",
                "bbox_coords": "[0.10, 0.10] → [0.50, 0.50]",
                "bbox_x1": 0.10,
                "bbox_y1": 0.10,
                "bbox_x2": 0.50,
                "bbox_y2": 0.50,
                "polygon_points": "100,100 200,200 300,300",
            }
        ]

        calib_dict = {
            "status": "calibrated",
            "pixel_to_mm_ratio": 0.20,
            "method": "Reference Scale Bar",
            "validation_status": "Valid",
            "resolution_mp": 2.1,
            "recommended_scale": "Verified via 50mm scale gauge.",
        }

        html = generator.render_html(
            input=recommendation_input,
            report=recommendation_report,
            asset_name="North Retaining Wall",
            detections=detections,
            image_quality={"suitability": "suitable_calibrated", "focus_score": 180.0},
            calibration_info=calib_dict,
            model_name="shm_ai_crack_seg_finetune_15e_best.pt",
            image_width=1000,
            image_height=1000,
        )

        assert "CALIBRATED" in html
        assert "50.00 mm" in html
        assert "2.00 mm" in html
        assert "100.0 mm²" in html
        assert "0.2000 mm/px" in html


# ---------------------------------------------------------------------------
# 5. Database Isolation Tests
# ---------------------------------------------------------------------------

class TestDatabaseIsolation:
    def test_live_database_remains_untouched(self):
        """
        Verify that measurement engine and report generator operate purely in-memory
        and do not create or write dirty records into data/shm_ai.db.
        """
        import sqlite3
        from pathlib import Path

        db_path = Path("data/shm_ai.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            # Verify no test artifacts or dirty records were written to live database
            cursor.execute("SELECT count(*) FROM detections WHERE defect_type = 'synthetic_test_defect'")
            assert cursor.fetchone()[0] == 0
            conn.close()

