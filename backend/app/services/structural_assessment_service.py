"""
Structural Assessment Service — authoritative application service for health evaluation.

Orchestrates the transition from raw vision detections and asset metadata
to explainable engineering health assessments, failure mode diagnoses,
and persisted HealthRecord entries with complete data provenance.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.asset import Asset
from backend.app.models.detection import DefectType, Detection
from backend.app.models.health_record import HealthRecord, RiskLevel as PyRiskLevel
from backend.app.models.inspection import Inspection, InspectionStatus
from backend.app.repositories.asset_repository import AssetRepository
from backend.app.repositories.detection_repository import DetectionRepository
from backend.app.repositories.health_record_repository import HealthRecordRepository
from backend.app.repositories.inspection_repository import InspectionRepository
from backend.app.schemas.assessment import (
    FailureModeItem,
    SeverityBreakdownItem,
    StructuralAssessmentResponse,
)
from backend.app.services.base import BaseService
from intelligence.assessment_service import AssessmentService
from intelligence.schemas import (
    AssetType,
    DefectCategory,
    DefectObservation,
    HealthAssessmentInput,
    HealthAssessmentReport,
)

logger = logging.getLogger(__name__)

# Map persistence DefectType to domain DefectCategory
DEFECT_TYPE_MAP: dict[DefectType, DefectCategory] = {
    DefectType.CRACK: DefectCategory.CRACK,
    DefectType.SPALLING: DefectCategory.SPALLING,
    DefectType.CORROSION: DefectCategory.CORROSION,
    DefectType.EXPOSED_REINFORCEMENT: DefectCategory.EXPOSED_REINFORCEMENT,
    DefectType.DELAMINATION: DefectCategory.DELAMINATION,
    DefectType.POTHOLE: DefectCategory.POTHOLE,
    DefectType.SURFACE_DAMAGE: DefectCategory.SURFACE_DAMAGE,
    DefectType.UNKNOWN: DefectCategory.UNKNOWN,
}

# Standard engineering provenance disclosures
STANDARD_DATA_SOURCES = [
    "Ultralytics YOLO11 Instance Segmentation (detections, bounding envelopes, confidence)",
    "Morphological Skeletonization & NetworkX Crack Topology (pixel metrics)",
    "Deterministic Structural Rules Engine (failure mode inference)",
    "ACI 224R-01 / Eurocode 2 (crack durability & structural severity classification)",
]

STANDARD_ASSUMPTIONS = [
    "Observations reflect 2D optical surface findings; internal voiding, tendon rupture, or unexposed rebar section loss require NDT or destructive validation.",
    "Composite structural health score is calculated via noisy-OR complementary product bounded to (0, 100]. Zero observed defects yields 100.0 baseline score.",
    "Model detection confidence reflects visual classification certainty, not structural hazard severity.",
]

STANDARD_LIMITATIONS = [
    "Indicative preliminary screening and prioritization tool; not a certified structural engineering seal.",
    "Uninspected structural members remain unassessed; overall asset score reflects supplied photographic evidence.",
]


class StructuralAssessmentService(BaseService):
    """
    Authoritative service for computing and persisting structural health assessments.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._inspection_repo = InspectionRepository(session)
        self._asset_repo = AssetRepository(session)
        self._detection_repo = DetectionRepository(session)
        self._health_repo = HealthRecordRepository(session)
        self._domain_service = AssessmentService()

    async def assess_inspection(
        self,
        inspection_id: str,
        force_reassess: bool = False,
    ) -> StructuralAssessmentResponse | None:
        """
        Evaluate structural health for a specific inspection.

        Returns None if inspection does not exist.
        Returns explainable unavailable/insufficient-data states if inspection is failed or pending.
        Computes deterministic score and persists HealthRecord for completed inspections.
        """
        inspection = await self._inspection_repo.get_by_id(inspection_id)
        if inspection is None:
            logger.warning(f"Assessment requested for non-existent inspection: {inspection_id}")
            return None

        asset = await self._asset_repo.get_by_id(inspection.asset_id)
        if asset is None:
            logger.error(f"Asset '{inspection.asset_id}' not found for inspection '{inspection_id}'")
            return None

        # ── 1. Handle Failed Inspection State ─────────────────────────────────
        if inspection.status == InspectionStatus.FAILED:
            return StructuralAssessmentResponse(
                status="unavailable",
                asset_id=asset.id,
                asset_name=asset.name,
                inspection_id=inspection.id,
                assessment_date_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                health_score=None,
                risk_level=None,
                data_sources=[],
                assumptions=[],
                limitations=["Cannot perform structural health assessment on a failed inspection."],
                missing_inputs=[
                    f"Inspection marked FAILED: {inspection.error_message or 'Unknown pipeline execution failure'}.",
                    "Attach valid photographic evidence and re-run vision pipeline before requesting assessment.",
                ],
                notes=inspection.error_message,
            )

        # ── 2. Handle Pending / Processing State ──────────────────────────────
        if inspection.status in (InspectionStatus.PENDING, InspectionStatus.PROCESSING):
            return StructuralAssessmentResponse(
                status="insufficient_data",
                asset_id=asset.id,
                asset_name=asset.name,
                inspection_id=inspection.id,
                assessment_date_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                health_score=None,
                risk_level=None,
                data_sources=[],
                assumptions=[],
                limitations=["Inspection has not completed vision model processing."],
                missing_inputs=["Vision inference must be executed to produce defect telemetry."],
                notes="Awaiting vision inference completion.",
            )

        # ── 3. Check for existing HealthRecord if not forcing reassessment ────
        if not force_reassess:
            existing_record = await self._health_repo.get_latest_for_inspection(inspection_id)
            if existing_record is not None:
                return self._record_to_response(existing_record, asset, inspection)

        # ── 4. Retrieve Persisted Detections ──────────────────────────────────
        detections = await self._detection_repo.get_by_inspection(inspection_id)

        # ── 5. Prepare Domain Input ───────────────────────────────────────────
        observations: list[DefectObservation] = []
        for det in detections:
            cat = DEFECT_TYPE_MAP.get(det.defect_type, DefectCategory.UNKNOWN)
            # Detections currently measure in pixel space. Since real-world GSD
            # calibration is uncalibrated unless explicitly provided, we pass None
            # for calibrated mm dimensions and preserve pixel values in metadata.
            observations.append(
                DefectObservation(
                    defect_category=cat,
                    confidence=det.confidence,
                    area_mm2=None,
                    length_mm=None,
                    width_mm=None,
                    max_width_mm=None,
                    orientation_deg=det.orientation_deg,
                )
            )

        current_year = datetime.datetime.now(datetime.timezone.utc).year
        asset_age = (
            float(current_year - asset.construction_year)
            if asset.construction_year is not None
            else None
        )

        try:
            asset_type_enum = AssetType(asset.asset_type.value)
        except ValueError:
            asset_type_enum = AssetType.OTHER

        domain_input = HealthAssessmentInput(
            asset_id=asset.id,
            asset_type=asset_type_enum,
            inspection_id=inspection.id,
            observations=observations,
            asset_age_years=asset_age,
            design_life_years=asset.design_life_years,
        )

        # ── 6. Execute Domain Assessment Engine ───────────────────────────────
        report: HealthAssessmentReport = self._domain_service.assess(domain_input)

        # ── 7. Build Disclosures & Missing Inputs ─────────────────────────────
        missing_inputs: list[str] = []
        if asset.construction_year is None:
            missing_inputs.append("Construction year unrecorded; temporal baseline unverified.")
        if asset.design_life_years is None:
            missing_inputs.append("Design service life unrecorded.")
        if len(detections) > 0:
            missing_inputs.append(
                "Metric camera calibration (Ground Sampling Distance / fiducial) not provided; "
                "defect geometry evaluated in pixel space with standard neutral scaling."
            )

        assessed_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
        method_name = "SHM-AI Deterministic Rules Engine v1.0"
        version_str = "1.0.0"

        # ── 8. Persist HealthRecord in Database ────────────────────────────────
        severity_dict: dict[str, Any] = {
            b.defect_category.value: {
                "severity": b.severity.value,
                "count": b.observation_count,
                "max_width_mm": b.max_width_mm,
                "total_area_mm2": b.total_area_mm2,
            }
            for b in report.severity_breakdown
        }

        failure_modes_list: list[dict[str, Any]] = [
            {
                "category": fm.category.value,
                "confidence": fm.confidence,
                "description": fm.description,
                "related_defects": [d.value for d in fm.related_defect_categories],
            }
            for fm in report.failure_modes
        ]

        metadata_dict: dict[str, Any] = {
            "data_sources": STANDARD_DATA_SOURCES,
            "assumptions": STANDARD_ASSUMPTIONS,
            "limitations": STANDARD_LIMITATIONS,
            "missing_inputs": missing_inputs,
            "assessed_at_utc": assessed_date,
            "calibration_status": "uncalibrated_pixel_space",
            "observation_count": len(observations),
        }

        try:
            py_risk = PyRiskLevel(report.risk_level.value)
        except ValueError:
            py_risk = PyRiskLevel.LOW

        health_record = await self._health_repo.create(
            inspection_id=inspection.id,
            health_score=report.health_score,
            risk_level=py_risk,
            severity_details=severity_dict,
            failure_modes=failure_modes_list,
            assessment_method=method_name,
            service_version=version_str,
            metadata_json=metadata_dict,
            notes=f"Assessed {len(detections)} defect instances via {method_name}.",
        )

        # ── 9. Sync Denormalized Health Scores ─────────────────────────────────
        await self._inspection_repo.update_fields(
            inspection,
            health_score=report.health_score,
        )
        await self._asset_repo.update_health_score(
            asset.id,
            report.health_score,
        )

        logger.info(
            f"Health assessment completed for inspection {inspection_id!r}: "
            f"score={report.health_score:.1f} risk={report.risk_level.value}"
        )

        return self._record_to_response(health_record, asset, inspection)

    def _record_to_response(
        self,
        record: HealthRecord,
        asset: Asset,
        inspection: Inspection,
    ) -> StructuralAssessmentResponse:
        """Convert a persisted HealthRecord ORM model to a validated API response schema."""
        meta = record.metadata_json or {}
        severity_items: list[SeverityBreakdownItem] = []
        if record.severity_details:
            for cat_str, val in record.severity_details.items():
                if isinstance(val, dict):
                    severity_items.append(
                        SeverityBreakdownItem(
                            defect_category=cat_str,
                            severity=val.get("severity", "moderate"),
                            observation_count=val.get("count", 0),
                            max_width_mm=val.get("max_width_mm"),
                            total_area_mm2=val.get("total_area_mm2"),
                        )
                    )

        failure_items: list[FailureModeItem] = []
        if record.failure_modes:
            for fm in record.failure_modes:
                if isinstance(fm, dict):
                    failure_items.append(
                        FailureModeItem(
                            category=fm.get("category", "unknown"),
                            description=fm.get("description", ""),
                            confidence=fm.get("confidence", 0.5),
                            related_defects=fm.get("related_defects", []),
                        )
                    )

        return StructuralAssessmentResponse(
            status="completed",
            asset_id=asset.id,
            asset_name=asset.name,
            inspection_id=inspection.id,
            assessment_date_utc=meta.get(
                "assessed_at_utc",
                record.created_at.isoformat() if record.created_at else None,
            ),
            health_score=record.health_score,
            risk_level=record.risk_level.value,
            assessment_method=record.assessment_method or "SHM-AI Deterministic Rules Engine v1.0",
            service_version=record.service_version or "1.0.0",
            calibration_status=meta.get("calibration_status", "uncalibrated_pixel_space"),
            data_sources=meta.get("data_sources", STANDARD_DATA_SOURCES),
            assumptions=meta.get("assumptions", STANDARD_ASSUMPTIONS),
            limitations=meta.get("limitations", STANDARD_LIMITATIONS),
            missing_inputs=meta.get("missing_inputs", []),
            severity_breakdown=severity_items,
            failure_modes=failure_items,
            notes=record.notes,
        )
