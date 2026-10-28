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

    # 5. Assess image quality, dimensions & data URI
    image_quality_dict: dict[str, Any] | None = None
    img_w, img_h = 1000, 1000
    image_data_uri: str | None = None
    if inspection.input_path:
        full_path = (settings.BASE_DIR / inspection.input_path).resolve()
        if not full_path.is_file():
            full_path = (settings.UPLOAD_DIR / "evidence" / Path(inspection.input_path).name).resolve()
        if full_path.is_file():
            try:
                import base64
                import mimetypes
                mime, _ = mimetypes.guess_type(str(full_path))
                mime = mime or "image/jpeg"
                b64 = base64.b64encode(full_path.read_bytes()).decode("ascii")
                image_data_uri = f"data:{mime};base64,{b64}"
            except Exception as e_b64:
                logger.warning(f"Could not encode image to data URI: {e_b64}")

            try:
                from PIL import Image
                with Image.open(full_path) as im:
                    img_w, img_h = im.size
                import cv2
                mat = cv2.imread(str(full_path))
                if mat is not None:
                    from vision.calibration.image_quality import ImageQualityAnalyzer
                    q = ImageQualityAnalyzer.analyze(
                        mat,
                        image_id=full_path.name,
                        image_format=full_path.suffix.lstrip(".").upper(),
                    )
                    image_quality_dict = q.model_dump()
            except Exception as q_err:
                logger.warning(f"Could not compute image quality for report: {q_err}")

    # 5b. Retrieve detections & construct defect gallery
    detections = await detection_repo.get_by_inspection(inspection.id)
    det_dicts: list[dict[str, Any]] = []
    is_any_calibrated = False

    for idx, d in enumerate(detections):
        ref_id = f"CRK-{idx + 1:02d}"
        vert_px = d.vertical_extent_px
        max_w_px = d.max_width_px
        len_mm = d.length_mm
        w_mm = d.width_mm
        max_w_mm = d.max_width_mm
        a_mm2 = d.area_mm2
        cal_status = d.calibration_status
        meas_status = d.measurement_status
        depth_stat = d.depth_status
        depth_val = d.depth_mm

        if cal_status == "calibrated" or w_mm is not None:
            is_any_calibrated = True

        poly_points = ""
        marker_x = None
        marker_y = None
        if d.mask_polygon and "coordinates" in d.mask_polygon:
            coords = d.mask_polygon.get("coordinates")
            if coords and len(coords) > 0 and len(coords[0]) > 0:
                poly_points = " ".join(f"{pt[0]},{pt[1]}" for pt in coords[0])
                pts = coords[0]
                marker_x = round(sum(pt[0] for pt in pts) / len(pts), 1)
                marker_y = round(sum(pt[1] for pt in pts) / len(pts), 1)
        elif d.bbox_x1 is not None and d.bbox_x2 is not None:
            marker_x = round(((d.bbox_x1 + d.bbox_x2) / 2) * img_w, 1)
            marker_y = round(((d.bbox_y1 + d.bbox_y2) / 2) * img_h, 1)

        det_dicts.append(
            {
                "ref_id": ref_id,
                "item_number": idx + 1,
                "marker_x": marker_x,
                "marker_y": marker_y,
                "defect_type": d.defect_type.value,
                "confidence": d.confidence,
                "confidence_pct": f"{d.confidence * 100:.1f}%",
                "bbox_coords": f"[{d.bbox_x1:.3f}, {d.bbox_y1:.3f}] → [{d.bbox_x2:.3f}, {d.bbox_y2:.3f}]",
                "bbox_norm": [d.bbox_x1, d.bbox_y1, d.bbox_x2, d.bbox_y2],
                "area_px": f"{d.area_px:,.0f}" if d.area_px is not None else "—",
                "length_px": f"{d.length_px:.1f}" if d.length_px is not None else "—",
                "width_px": f"{d.width_px:.2f}" if d.width_px is not None else "—",
                "max_width_px": f"{max_w_px:.2f}" if max_w_px is not None else "—",
                "vertical_extent_px": f"{vert_px:.1f}" if vert_px is not None else "—",
                "orientation_deg": f"{d.orientation_deg:.1f}°" if d.orientation_deg is not None else "—",
                "length_mm": f"{len_mm:.1f} mm" if len_mm is not None else "Requires Calibration",
                "width_mm": f"{w_mm:.2f} mm" if w_mm is not None else "Requires Calibration",
                "max_width_mm": f"{max_w_mm:.2f} mm" if max_w_mm is not None else "Requires Calibration",
                "area_mm2": f"{a_mm2:,.1f} mm²" if a_mm2 is not None else "Requires Calibration",
                "depth_status": depth_stat,
                "depth_display": f"{depth_val:.1f} mm" if depth_val is not None else "Not Measured (2D Image)",
                "calibration_status": cal_status,
                "measurement_status": meas_status,
                "unavailability_reasons": d.unavailability_reasons or (
                    ["Uncalibrated optical photograph; no Ground Sampling Distance or reference marker provided."]
                    if not is_any_calibrated else []
                ),
                "polygon_points": poly_points,
            }
        )

    # 5c. Calibration summary
    calibration_dict: dict[str, Any] = {
        "status": "calibrated" if is_any_calibrated else "uncalibrated",
        "method": "ground_sampling_distance" if is_any_calibrated else "none",
        "pixel_to_mm_ratio": None,
        "reference_object": None,
        "limitations": [
            "2D surface visual observation only. Internal concrete reinforcement, voiding, and tendon condition unassessed.",
            "Absence of optical reference scale prevents certified millimeter conversion without metric camera calibration.",
        ] if not is_any_calibrated else [],
        "guidance": (
            "To obtain certified millimeter dimensions, include a physical reference marker (e.g. 50mm calibration disc or scale ruler) "
            "coplanar with the structural surface, or provide camera focal length and sensor Ground Sampling Distance (GSD)."
        ),
    }

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
            "model_name": assessment.model_name or "shm_ai_crack_seg_finetune_15e_best.pt",
        },
        image_quality=image_quality_dict,
        calibration_info=calibration_dict,
        model_name=assessment.model_name or "shm_ai_crack_seg_finetune_15e_best.pt",
        image_width=img_w,
        image_height=img_h,
        image_data_uri=image_data_uri,
    )

    # 7. Persist report file (HTML and PDF)
    report_id = str(uuid.uuid4())
    base_stem = f"report_{asset.id[:8]}_{inspection.id[:8]}_{timestamp_str}"
    filename = f"{base_stem}.html"
    pdf_filename = f"{base_stem}.pdf"
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = settings.REPORTS_DIR / filename
    pdf_output_path = settings.REPORTS_DIR / pdf_filename

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except OSError as exc:
        logger.error(f"Failed to persist report file {output_path}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save report to server filesystem.",
        )

    # Attempt PDF generation
    pdf_available = False
    try:
        pdf_bytes = generator.generate_pdf_from_html(html_content)
        pdf_output_path.write_bytes(pdf_bytes)
        pdf_available = True
        logger.info(f"Engineering report PDF generated successfully: {pdf_filename} ({len(pdf_bytes)} bytes)")
    except Exception as pdf_exc:
        logger.warning(f"Server-side PDF generation skipped or failed: {pdf_exc}")

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
        pdf_available=pdf_available,
        pdf_filename=pdf_filename if pdf_available else None,
        notes=inspection.notes,
    )


@router.get(
    "/{filename}/pdf",
    summary="Download report as PDF",
    description="Retrieve or dynamically convert an engineering report to PDF.",
    responses={
        404: {"description": "Report file not found"},
    },
)
async def get_report_pdf(filename: str, settings: AppSettings):
    """Serve or dynamically generate a PDF version of an engineering report."""
    safe_name = os.path.basename(filename)
    stem = os.path.splitext(safe_name)[0]
    pdf_name = f"{stem}.pdf"
    pdf_path = (settings.REPORTS_DIR / pdf_name).resolve()
    html_path = (settings.REPORTS_DIR / f"{stem}.html").resolve()

    if not pdf_path.is_file():
        if not html_path.is_file() or not html_path.is_relative_to(settings.REPORTS_DIR.resolve()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report file '{safe_name}' not found.",
            )
        try:
            generator = ReportGenerator()
            html_content = html_path.read_text(encoding="utf-8")
            pdf_bytes = generator.generate_pdf_from_html(html_content)
            pdf_path.write_bytes(pdf_bytes)
        except Exception as exc:
            logger.error(f"On-demand PDF conversion failed for {safe_name}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate PDF from report: {exc}",
            )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_name,
        headers={"Content-Disposition": f'attachment; filename="{pdf_name}"'},
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

    is_html = safe_name.endswith(".html")
    media_type = "text/html; charset=utf-8" if is_html else "application/pdf"
    content_disposition_type = "inline" if is_html else "attachment"
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=safe_name,
        content_disposition_type=content_disposition_type,
    )
