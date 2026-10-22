"""
Report API endpoints.

Generates, lists, and serves formal civil engineering structural health reports.
Integrates StructuralAssessmentService, RecommendationService, and ReportGenerator.
"""
import datetime
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from backend.app.dependencies import AppSettings, DBSession
from backend.app.models.inspection import InspectionStatus
from backend.app.repositories.asset_repository import AssetRepository
from backend.app.repositories.detection_repository import DetectionRepository
from backend.app.repositories.inspection_repository import InspectionRepository
from backend.app.schemas.report import (
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportSummary,
)
from backend.app.services.structural_assessment_service import StructuralAssessmentService
from intelligence.schemas import (
    AssetType,
    DefectCategory,
    DefectSeverityBreakdown,
    FailureModeCategory,
    HealthAssessmentReport,
    RiskLevel,
    SeverityLevel,
    StructuralFailureMode,
)
from recommendation.recommendation_service import RecommendationService
from recommendation.report_generator import ReportGenerator
from recommendation.schemas import RecommendationInput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/",
    response_model=list[ReportSummary],
    summary="List generated engineering reports",
    description="Returns metadata for all persisted engineering reports stored on the server.",
)
async def list_reports(settings: AppSettings) -> list[ReportSummary]:
    """List all persisted reports on disk, newest first."""
    reports_dir = settings.REPORTS_DIR
    if not reports_dir.exists():
        return []

    summaries: list[ReportSummary] = []
    for file_path in reports_dir.glob("report_*"):
        if file_path.suffix.lower() not in (".html", ".pdf"):
            continue
        try:
            stat = file_path.stat()
            created_at = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc)
            parts = file_path.stem.split("_")
            asset_short = parts[1] if len(parts) > 1 else None
            insp_short = parts[2] if len(parts) > 2 else None

            summaries.append(
                ReportSummary(
                    filename=file_path.name,
                    file_path=f"/reports/{file_path.name}",
                    asset_id=asset_short,
                    inspection_id=insp_short,
                    created_at=created_at,
                    size_bytes=stat.st_size,
                    format=file_path.suffix.lstrip(".").lower(),
                )
            )
        except OSError as exc:
            logger.warning(f"Error accessing report file {file_path}: {exc}")
            continue

    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return summaries


@router.post(
    "/generate",
    response_model=ReportGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a formal structural inspection report",
    description=(
        "Assembles actual asset details, completed inspection telemetry, defect detections, "
        "and runs the explainable assessment and recommendation engine to compile a validated engineering report."
    ),
    responses={
        404: {"description": "Asset or Inspection not found"},
        422: {"description": "Inspection not completed or does not match asset"},
    },
)
async def generate_report(
    data: ReportGenerateRequest,
    session: DBSession,
    settings: AppSettings,
) -> ReportGenerateResponse:
    """Generate and persist an engineering report."""
    asset_repo = AssetRepository(session)
    inspection_repo = InspectionRepository(session)
    detection_repo = DetectionRepository(session)

    # 1. Fetch asset
    asset = await asset_repo.get_by_id(data.asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{data.asset_id}' not found.",
        )

    # 2. Fetch inspection
    inspection = await inspection_repo.get_by_id(data.inspection_id)
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{data.inspection_id}' not found.",
        )

    if inspection.asset_id != asset.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Inspection '{data.inspection_id}' belongs to a different asset, not '{asset.name}'.",
        )

    if inspection.status != InspectionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Inspection is in '{inspection.status.value}' state. Reports require a completed inspection.",
        )

    # 3. Retrieve or compute explainable structural assessment
    assessment_service = StructuralAssessmentService(session)
    assessment = await assessment_service.assess_inspection(inspection.id)
    if assessment is None or assessment.health_score is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Inspection '{data.inspection_id}' cannot be assessed: "
                f"{assessment.notes if assessment else 'No valid assessment data available'}."
            ),
        )

    # 4. Map breakdowns and failure modes from authoritative assessment
    breakdowns: list[DefectSeverityBreakdown] = []
    for item in assessment.severity_breakdown:
        try:
            cat_enum = DefectCategory(item.defect_category)
        except ValueError:
            cat_enum = DefectCategory.UNKNOWN
        try:
            sev_enum = SeverityLevel(item.severity)
        except ValueError:
            sev_enum = SeverityLevel.MODERATE
        breakdowns.append(
            DefectSeverityBreakdown(
                defect_category=cat_enum,
                severity=sev_enum,
                observation_count=item.observation_count,
                total_area_mm2=item.total_area_mm2,
                max_width_mm=item.max_width_mm,
            )
        )

    failure_modes: list[StructuralFailureMode] = []
    for fm in assessment.failure_modes:
        try:
            fcat = FailureModeCategory(fm.category)
        except ValueError:
            fcat = FailureModeCategory.UNKNOWN
        failure_modes.append(
            StructuralFailureMode(
                category=fcat,
                description=fm.description,
                confidence=fm.confidence,
                related_defect_categories=[
                    DefectCategory(d)
                    for d in fm.related_defects
                    if d in [e.value for e in DefectCategory]
                ],
            )
        )

    try:
        risk_enum = RiskLevel(assessment.risk_level)
    except (ValueError, TypeError):
        risk_enum = RiskLevel.LOW

    health_report = HealthAssessmentReport(
        asset_id=asset.id,
        inspection_id=inspection.id,
        health_score=assessment.health_score,
        risk_level=risk_enum,
        severity_breakdown=breakdowns,
        failure_modes=failure_modes,
        metadata={
            "assessment_method": assessment.assessment_method,
            "service_version": assessment.service_version,
            "assessed_at_utc": assessment.assessment_date_utc,
            "data_sources": assessment.data_sources,
            "assumptions": assessment.assumptions,
            "limitations": assessment.limitations,
            "missing_inputs": assessment.missing_inputs,
        },
    )

    try:
        atype = AssetType(asset.asset_type.value)
    except ValueError:
        atype = AssetType.OTHER

    rec_input = RecommendationInput(
        asset_id=asset.id,
        inspection_id=inspection.id,
        asset_type=atype,
        health_report=health_report,
        degradation_report=None,  # Retired degradation module excluded
    )

    rec_service = RecommendationService()
    rec_report = rec_service.assess(rec_input)

    # 5. Retrieve detections & image path for defect gallery
    detections = await detection_repo.get_by_inspection(inspection.id)
    det_dicts = [
        {
            "defect_type": d.defect_type.value,
            "confidence": d.confidence,
            "area_px": f"{d.area_px:,.0f}" if d.area_px is not None else None,
            "length_px": f"{d.length_px:.1f}" if d.length_px is not None else None,
            "width_px": f"{d.width_px:.2f}" if d.width_px is not None else None,
        }
        for d in detections
    ]

    # 6. Render presentation HTML
    generator = ReportGenerator()
    generated_at = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = generated_at.strftime("%Y%m%d_%H%M%S")
    html_content = generator.render_html(
        input=rec_input,
        report=rec_report,
        generated_at_utc=generated_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        asset_name=asset.name,
        input_image_path=inspection.input_path,
        detections=det_dicts,
        assessment_meta={
            "assessment_method": assessment.assessment_method,
            "data_sources": assessment.data_sources,
            "assumptions": assessment.assumptions,
            "limitations": assessment.limitations,
            "missing_inputs": assessment.missing_inputs,
        },
    )

    # 7. Persist report file
    report_id = str(uuid.uuid4())
    filename = f"report_{asset.id[:8]}_{inspection.id[:8]}_{timestamp_str}.html"
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = settings.REPORTS_DIR / filename
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except OSError as exc:
        logger.error(f"Failed to persist report file {output_path}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save report to server filesystem.",
        )

    return ReportGenerateResponse(
        report_id=report_id,
        filename=filename,
        format="html",
        created_at=generated_at,
        asset_id=asset.id,
        asset_name=asset.name,
        inspection_id=inspection.id,
        health_score=assessment.health_score,
        recommended_action=rec_report.decision.recommended_action.value,
        cost_estimate_low=rec_report.cost_estimate.low,
        cost_estimate_high=rec_report.cost_estimate.high,
        currency=rec_report.cost_estimate.currency,
        html_content=html_content,
        pdf_available=False,
        notes=inspection.notes,
    )


@router.get(
    "/{filename}",
    summary="Download or view generated report",
    description="Retrieve a saved engineering report file by filename.",
    responses={
        404: {"description": "Report file not found"},
    },
)
async def get_report_file(filename: str, settings: AppSettings):
    """Serve a generated report file directly."""
    safe_name = os.path.basename(filename)
    file_path = (settings.REPORTS_DIR / safe_name).resolve()

    if not file_path.is_file() or not file_path.is_relative_to(settings.REPORTS_DIR.resolve()):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report file '{safe_name}' not found.",
        )

    media_type = "text/html; charset=utf-8" if safe_name.endswith(".html") else "application/pdf"
    return FileResponse(file_path, media_type=media_type, filename=safe_name)
