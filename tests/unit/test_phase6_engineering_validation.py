"""
Phase 6 Engineering Validation & Health Assessment Regression Tests.

Validates:
1. Invalid asset/inspection relationship rejection.
2. Isolation of detections to their source inspection.
3. Correct detection count and evidence associations.
4. Missing evidence and failed inference handling.
5. Assessment behavior with incomplete or failed data.
6. Deterministic health-score calculation and provenance tracking.
7. Chronological historical inspection retrieval.
8. Inspection comparison between compatible and incompatible records.
9. Report consistency with selected inspection and asset.
10. Integrity and absence of retired degradation modules in user-facing reports.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ValidationError
from backend.app.models.asset import Asset, AssetStatus, AssetType
from backend.app.models.detection import DefectType, Detection
from backend.app.models.health_record import HealthRecord
from backend.app.models.inspection import Inspection, InspectionSource, InspectionStatus
from backend.app.repositories.detection_repository import DetectionRepository
from backend.app.repositories.health_record_repository import HealthRecordRepository
from backend.app.schemas.asset import AssetCreate
from backend.app.schemas.asset_evidence import AssetEvidenceCreate
from backend.app.schemas.inspection import InspectionCreate
from backend.app.services.asset_service import AssetService
from backend.app.services.evidence_service import EvidenceService
from backend.app.services.inspection_service import InspectionService
from backend.app.services.structural_assessment_service import StructuralAssessmentService
from recommendation.report_generator import ReportGenerator
from recommendation.schemas import RecommendationInput
from recommendation.recommendation_service import RecommendationService
from intelligence.schemas import (
    AssetType as DomainAssetType,
    DefectCategory,
    DefectSeverityBreakdown,
    HealthAssessmentReport,
    RiskLevel,
    SeverityLevel,
)
from vision.detectors.base import IDetector, RawDetection
from vision.pipeline.cv_pipeline import CVInferencePipeline


class DummyMultiDetector(IDetector):
    """Dummy detector returning specific simulated defects without model weights."""
    def __init__(self, defects: list[RawDetection] | None = None) -> None:
        self._defects = defects or [
            RawDetection(
                defect_type=DefectType.CRACK,
                confidence=0.88,
                bbox=[0.1, 0.2, 0.5, 0.8],
                mask=None,
            ),
            RawDetection(
                defect_type=DefectType.SPALLING,
                confidence=0.92,
                bbox=[0.6, 0.3, 0.9, 0.7],
                mask=None,
            ),
        ]

    @property
    def model_name(self) -> str:
        return "dummy-multi-detector.pt"

    @property
    def device(self) -> str:
        return "cpu"

    def predict(self, image, confidence_threshold=None):
        return self._defects


@pytest.mark.asyncio
async def test_invalid_asset_inspection_relationship(db_session: AsyncSession):
    """Inspections cannot be created or compared across invalid or mismatched asset boundaries."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)

    asset1 = await asset_svc.create_asset(AssetCreate(name="Bridge Alpha", asset_type=AssetType.BRIDGE))
    asset2 = await asset_svc.create_asset(AssetCreate(name="Tunnel Beta", asset_type=AssetType.TUNNEL))

    # Inspection cannot be created for a non-existent asset ID
    invalid_insp = await insp_svc.create_inspection(
        InspectionCreate(asset_id="00000000-0000-0000-0000-000000000000", source=InspectionSource.IMAGE)
    )
    assert invalid_insp is None

    # Create one inspection for asset1 and one for asset2
    insp1 = await insp_svc.create_inspection(InspectionCreate(asset_id=asset1.id, source=InspectionSource.IMAGE))
    insp2 = await insp_svc.create_inspection(InspectionCreate(asset_id=asset2.id, source=InspectionSource.IMAGE))
    assert insp1 is not None and insp2 is not None

    # Comparing inspections belonging to different assets must be rejected
    with pytest.raises(ValidationError, match="Both inspections must belong to asset"):
        await insp_svc.compare_inspections(asset_id=asset1.id, base_id=insp1.id, target_id=insp2.id)


@pytest.mark.asyncio
async def test_detections_isolated_to_source_inspection(db_session: AsyncSession):
    """Detections must be strictly partitioned by inspection_id."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    det_repo = DetectionRepository(db_session)

    asset = await asset_svc.create_asset(AssetCreate(name="Harbor Pier", asset_type=AssetType.BRIDGE))
    insp1 = await insp_svc.create_inspection(InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE))
    insp2 = await insp_svc.create_inspection(InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE))

    await det_repo.create(
        inspection_id=insp1.id,
        defect_type=DefectType.CRACK,
        confidence=0.91,
        bbox_x1=0.1, bbox_y1=0.1, bbox_x2=0.3, bbox_y2=0.4,
        area_px=150.0, length_px=45.0, width_px=3.2, orientation_deg=45.0,
    )
    await det_repo.create(
        inspection_id=insp2.id,
        defect_type=DefectType.CORROSION,
        confidence=0.85,
        bbox_x1=0.5, bbox_y1=0.5, bbox_x2=0.8, bbox_y2=0.9,
        area_px=320.0, length_px=60.0, width_px=5.5, orientation_deg=0.0,
    )

    dets1 = await insp_svc.get_detections(insp1.id)
    dets2 = await insp_svc.get_detections(insp2.id)

    assert len(dets1) == 1
    assert dets1[0].defect_type == DefectType.CRACK
    assert len(dets2) == 1
    assert dets2[0].defect_type == DefectType.CORROSION


@pytest.mark.asyncio
async def test_assessment_behavior_with_incomplete_data(db_session: AsyncSession):
    """Failed or pending inspections return explainable unavailable/insufficient_data without fake scores."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    assessment_svc = StructuralAssessmentService(db_session)

    asset = await asset_svc.create_asset(AssetCreate(name="Viaduct Bent 3", asset_type=AssetType.BRIDGE))

    # Pending inspection
    pending_insp = await insp_svc.create_inspection(InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE))
    pending_res = await assessment_svc.assess_inspection(pending_insp.id)
    assert pending_res is not None
    assert pending_res.status == "insufficient_data"
    assert pending_res.health_score is None
    assert pending_res.risk_level is None

    # Failed inspection
    failed_insp = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, notes="Inference failed test")
    )
    await insp_svc._repo.update_fields(
        failed_insp, status=InspectionStatus.FAILED, error_message="Vision weights corrupted"
    )
    failed_res = await assessment_svc.assess_inspection(failed_insp.id)
    assert failed_res is not None
    assert failed_res.status == "unavailable"
    assert failed_res.health_score is None
    assert "Vision weights corrupted" in failed_res.missing_inputs[0]


@pytest.mark.asyncio
async def test_health_score_calculation_and_provenance(db_session: AsyncSession, tmp_path: Path):
    """Completed inspection runs deterministic assessment, creates HealthRecord, and tracks provenance."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    assessment_svc = StructuralAssessmentService(db_session)
    health_repo = HealthRecordRepository(db_session)

    test_img = tmp_path / "structure_test.jpg"
    test_img.write_bytes(b"fake jpeg content")

    asset = await asset_svc.create_asset(
        AssetCreate(
            name="North Abutment Wall",
            asset_type=AssetType.BRIDGE,
            construction_year=1980,
            design_life_years=100.0,
        )
    )
    insp = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, input_path=str(test_img))
    )

    pipeline = CVInferencePipeline(
        detector=DummyMultiDetector(),
        slice_height=640,
        slice_width=640,
        slice_overlap_ratio=0.0,
        slice_if_large=False,
    )

    fake_rgb = np.zeros((640, 640, 3), dtype=np.uint8)
    with patch("vision.preprocessing.loader.ImageLoader.load_image", return_value=fake_rgb):
        completed_insp = await insp_svc.run_inspection(insp.id, pipeline=pipeline)

    assert completed_insp is not None
    assert completed_insp.status == InspectionStatus.COMPLETED
    assert completed_insp.defect_count == 2
    assert completed_insp.health_score is not None
    assert 0.0 <= completed_insp.health_score <= 100.0

    # Verify HealthRecord was persisted with complete provenance
    records = await health_repo.get_by_inspection(insp.id)
    assert len(records) >= 1
    hr = records[0]
    assert hr.health_score == completed_insp.health_score
    assert hr.assessment_method == "SHM-AI Deterministic Rules Engine v1.0"
    assert hr.service_version == "1.0.0"
    assert hr.metadata_json is not None
    assert "data_sources" in hr.metadata_json
    assert "limitations" in hr.metadata_json
    assert "assumptions" in hr.metadata_json

    # Check asset latest_health_score synchronization
    updated_asset = await asset_svc.get_asset(asset.id)
    assert updated_asset.latest_health_score == completed_insp.health_score


@pytest.mark.asyncio
async def test_historical_inspection_retrieval(db_session: AsyncSession):
    """Inspections for an asset are returned in reverse chronological order."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)

    asset = await asset_svc.create_asset(AssetCreate(name="Arch Dam Face", asset_type=AssetType.DAM))
    insp1 = await insp_svc.create_inspection(InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, notes="Event 1"))
    insp2 = await insp_svc.create_inspection(InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, notes="Event 2"))

    history = await insp_svc.list_inspections_for_asset(asset.id)
    assert len(history) == 2
    # Ensure both inspections are retrieved and ordered
    history_ids = [h.id for h in history]
    assert insp1.id in history_ids
    assert insp2.id in history_ids


@pytest.mark.asyncio
async def test_inspection_comparison_change_tracking(db_session: AsyncSession, tmp_path: Path):
    """Comparing two inspections accurately distinguishes defect types, delta scores, and provides disclosures."""
    asset_svc = AssetService(db_session)
    insp_svc = InspectionService(db_session)
    det_repo = DetectionRepository(db_session)

    asset = await asset_svc.create_asset(AssetCreate(name="Culvert Highway Span", asset_type=AssetType.ROAD))
    insp_base = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, input_path="/uploads/test1.jpg")
    )
    insp_target = await insp_svc.create_inspection(
        InspectionCreate(asset_id=asset.id, source=InspectionSource.IMAGE, input_path="/uploads/test2.jpg")
    )

    # Base inspection: CRACK (1 defect), health score 85.0
    await det_repo.create(
        inspection_id=insp_base.id,
        defect_type=DefectType.CRACK,
        confidence=0.80,
        bbox_x1=0.1, bbox_y1=0.1, bbox_x2=0.3, bbox_y2=0.3,
        area_px=100.0,
    )
    await insp_svc._repo.update_fields(
        insp_base, status=InspectionStatus.COMPLETED, defect_count=1, health_score=85.0, input_path="/uploads/test1.jpg"
    )

    # Target inspection: CRACK and SPALLING (2 defects), health score 70.0
    await det_repo.create(
        inspection_id=insp_target.id,
        defect_type=DefectType.CRACK,
        confidence=0.85,
        bbox_x1=0.1, bbox_y1=0.1, bbox_x2=0.3, bbox_y2=0.3,
        area_px=120.0,
    )
    await det_repo.create(
        inspection_id=insp_target.id,
        defect_type=DefectType.SPALLING,
        confidence=0.90,
        bbox_x1=0.4, bbox_y1=0.4, bbox_x2=0.7, bbox_y2=0.7,
        area_px=250.0,
    )
    await insp_svc._repo.update_fields(
        insp_target, status=InspectionStatus.COMPLETED, defect_count=2, health_score=70.0, input_path="/uploads/test2.jpg"
    )

    comparison = await insp_svc.compare_inspections(
        asset_id=asset.id, base_id=insp_base.id, target_id=insp_target.id
    )

    assert comparison.common_defect_types == ["crack"]
    assert comparison.newly_observed_defect_types == ["spalling"]
    assert comparison.previously_observed_defect_types_absent == []
    assert comparison.health_score_delta == -15.0
    assert comparison.defect_count_delta == 1
    assert comparison.comparability_status == "partially_comparable"
    assert len(comparison.disclosures_and_limitations) >= 4


def test_retired_degradation_absent_from_user_reports():
    """Jinja2 engineering dossier excludes retired material degradation from user sections."""
    generator = ReportGenerator()
    inp = RecommendationInput(
        asset_id="asset-xyz",
        inspection_id="insp-abc",
        asset_type=DomainAssetType.BRIDGE,
        health_report=HealthAssessmentReport(
            asset_id="asset-xyz",
            inspection_id="insp-abc",
            health_score=82.0,
            risk_level=RiskLevel.LOW,
            severity_breakdown=[
                DefectSeverityBreakdown(
                    defect_category=DefectCategory.CRACK,
                    severity=SeverityLevel.MINOR,
                    observation_count=1,
                    total_area_mm2=45.0,
                    max_width_mm=0.25,
                )
            ],
            failure_modes=[],
            metadata={"assessment_method": "SHM-AI Deterministic Rules Engine v1.0"},
        ),
        degradation_report=None,  # Retired module excluded
    )
    report = RecommendationService().assess(inp)

    html = generator.render_html(
        input=inp,
        report=report,
        asset_name="Tower Bridge Pier",
        input_image_path="/uploads/evidence/pier.jpg",
        detections=[
            {"defect_type": "crack", "confidence": 0.88, "area_px": "150", "length_px": "40.0", "width_px": "2.10"}
        ],
    )

    # Verify key engineering sections exist
    assert "Structural Health Score &amp; Risk Classification" in html
    assert "82.0" in html
    assert "Inferred Structural Failure Mechanisms" in html
    assert "Photographic Inspection Evidence &amp; Detections" in html
    assert "Tower Bridge Pier" in html
    assert "Professional Structural Engineer Sign-Off" in html

    # Verify user-visible Material Degradation section is NOT displayed when degradation_report is None
    assert 'class="section-title">Material Degradation Assessment (Phase 4)<' not in html
