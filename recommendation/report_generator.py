"""
Report Generator — Phase 5b & Phase 6 Engineering Dossier.

Renders a RecommendationReport and its corresponding RecommendationInput
into a styled HTML document (via Jinja2) and optionally into a PDF byte
stream (via WeasyPrint).

Traceability:
- Asset details, inspection media, and persisted detections.
- Deterministic health score, risk classification, and failure modes.
- Engineering methodology, provenance, assumptions, and limitations.
"""
from __future__ import annotations

import datetime
import base64
import mimetypes
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from jinja2 import Environment, FileSystemLoader

from recommendation.schemas import (  # noqa: TC001
    RecommendationInput,
    RecommendationReport,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

#: Default template directory — shipped alongside this module.
_DEFAULT_TEMPLATE_DIR: Path = Path(__file__).parent / "templates"

#: Hex colours for each RiskLevel value (Architectural Olive & Sand visual identity).
_RISK_LEVEL_COLORS: dict[str, str] = {
    "low": "#66765A",       # Sage
    "medium": "#B68A48",    # Muted ochre
    "high": "#9D3E32",      # Deep rust
    "critical": "#9D3E32",  # Deep rust
}

#: Hex colours for each RecommendedActionType value (Architectural Olive & Sand visual identity).
_ACTION_COLORS: dict[str, str] = {
    "monitor": "#66765A",                # Sage
    "inspect": "#B68A48",                # Muted ochre
    "repair": "#A65D42",                 # Muted terracotta
    "emergency_intervention": "#9D3E32", # Deep rust
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportGeneratorConfig:
    """
    Configuration for a ReportGenerator instance.

    Attributes:
        template_dir: Directory containing the Jinja2 template(s).
        generator_version: Recorded in every report's metadata section.
    """

    template_dir: Path = field(default_factory=lambda: _DEFAULT_TEMPLATE_DIR)
    generator_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Context builder (private)
# ---------------------------------------------------------------------------


def _build_context(
    input: RecommendationInput,
    report: RecommendationReport,
    generator_version: str,
    generated_at_utc: str | None = None,
    asset_name: str | None = None,
    input_image_path: str | None = None,
    detections: list[dict[str, Any]] | None = None,
    assessment_meta: dict[str, Any] | None = None,
    image_quality: dict[str, Any] | None = None,
    calibration_info: dict[str, Any] | None = None,
    model_name: str | None = None,
    image_width: int = 1000,
    image_height: int = 1000,
    image_data_uri: str | None = None,
) -> dict[str, Any]:
    """
    Build the Jinja2 template context dict from domain objects.
    """
    decision = report.decision
    cost = report.cost_estimate
    esc = decision.escalation
    health = input.health_report

    # Resolve image data URI if not directly provided
    if not image_data_uri and input_image_path:
        candidate_paths = [
            Path(input_image_path),
            Path("data") / input_image_path,
            Path("data/uploads/evidence") / Path(input_image_path).name,
            Path("uploads/evidence") / Path(input_image_path).name,
        ]
        for cp in candidate_paths:
            if cp.is_file():
                try:
                    mime, _ = mimetypes.guess_type(str(cp))
                    mime = mime or "image/jpeg"
                    b64 = base64.b64encode(cp.read_bytes()).decode("ascii")
                    image_data_uri = f"data:{mime};base64,{b64}"
                    break
                except Exception:
                    pass

    # ── Severity breakdown ────────────────────────────────────────────────
    severity_breakdown: list[dict[str, Any]] = []
    for b in health.severity_breakdown:
        severity_breakdown.append(
            {
                "category": b.defect_category.value,
                "severity": b.severity.value,
                "observation_count": b.observation_count,
                "area_formatted": (
                    f"{b.total_area_mm2:,.1f}" if b.total_area_mm2 is not None else None
                ),
            }
        )

    # ── Failure modes ─────────────────────────────────────────────────────
    failure_modes: list[dict[str, Any]] = []
    for m in health.failure_modes:
        failure_modes.append(
            {
                "category": m.category.value,
                "confidence_pct": f"{m.confidence * 100:.0f}%",
                "description": m.description,
            }
        )

    # ── Degradation section (suppressed / optional for retired module) ─────
    deg = input.degradation_report
    if deg is not None:
        ttd = deg.carbonation.time_to_depassivation_years
        degradation: dict[str, Any] | None = {
            "carbonation_depth_formatted": f"{deg.carbonation.depth_mm_now:.2f}",
            "time_to_depassivation": (
                f"{ttd:.1f} years" if ttd is not None else "Already depassivated"
            ),
            "corrosion_initiated": deg.corrosion.initiation_status.value == "initiated",
            "corrosion_index_formatted": f"{deg.corrosion.corrosion_probability_now:.3f}",
            "requires_maintenance": deg.requires_maintenance,
        }
        has_degradation = True
    else:
        degradation = None
        has_degradation = False

    # ── Engine versions from report metadata ──────────────────────────────
    engine_versions: dict[str, str] = {}
    ev = report.metadata.get("engine_versions")
    if isinstance(ev, dict):
        engine_versions = {k: str(v) for k, v in ev.items()}

    # ── Timestamp ─────────────────────────────────────────────────────────
    ts = generated_at_utc or datetime.datetime.now(datetime.UTC).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    # ── Provenance & Methodology ──────────────────────────────────────────
    ass_meta = assessment_meta or health.metadata or {}
    assessment_method = ass_meta.get(
        "assessment_method", "SHM-AI Deterministic Rules Engine v1.0"
    )
    data_sources = ass_meta.get(
        "data_sources",
        [
            "Ultralytics YOLO11 Instance Segmentation",
            "Morphological Skeletonization & NetworkX Crack Topology",
            "Deterministic Structural Rules Engine (ACI 224R / Eurocode 2)",
        ],
    )
    assumptions = ass_meta.get(
        "assumptions",
        [
            "Observations reflect 2D optical surface findings; internal voiding or unexposed rebar section loss requires NDT validation.",
            "Composite structural health score is calculated via noisy-OR complementary product bounded to (0, 100]. Zero observed defects yields 100.0 baseline score.",
            "Model detection confidence reflects visual classification certainty, not structural hazard severity.",
        ],
    )
    limitations = ass_meta.get(
        "limitations",
        [
            "Indicative preliminary screening and prioritization tool; not a certified structural engineering seal.",
            "Uninspected structural members remain unassessed; overall asset score reflects supplied photographic evidence.",
        ],
    )
    missing_inputs = ass_meta.get("missing_inputs", [])

    # ── Enrich Detections with Numbered Markers ───────────────────────────
    enriched_detections: list[dict[str, Any]] = []
    for idx, d in enumerate(detections or []):
        det_item = dict(d)
        det_item["item_number"] = idx + 1
        if not det_item.get("ref_id"):
            det_item["ref_id"] = f"CRK-{idx + 1:02d}"

        if det_item.get("marker_x") is None:
            poly_str = det_item.get("polygon_points", "")
            if poly_str:
                try:
                    pairs = [tuple(map(float, pt.split(","))) for pt in poly_str.strip().split() if "," in pt]
                    if pairs:
                        det_item["marker_x"] = round(sum(p[0] for p in pairs) / len(pairs), 1)
                        det_item["marker_y"] = round(sum(p[1] for p in pairs) / len(pairs), 1)
                except Exception:
                    pass
            if det_item.get("marker_x") is None and det_item.get("bbox_norm"):
                try:
                    bx1, by1, bx2, by2 = det_item["bbox_norm"]
                    det_item["marker_x"] = round(((bx1 + bx2) / 2) * image_width, 1)
                    det_item["marker_y"] = round(((by1 + by2) / 2) * image_height, 1)
                except Exception:
                    pass
        enriched_detections.append(det_item)

    return {
        # Asset identity
        "asset_id": input.asset_id,
        "asset_name": asset_name or input.asset_id,
        "inspection_id": input.inspection_id,
        "asset_type": input.asset_type.value,
        "generated_at_utc": ts,
        "generator_version": generator_version,
        # Health assessment
        "health_score_formatted": f"{health.health_score:.1f}",
        "risk_level": health.risk_level.value,
        "risk_level_color": _RISK_LEVEL_COLORS.get(health.risk_level.value, "#77766D"),
        # Defects
        "severity_breakdown": severity_breakdown,
        "failure_modes": failure_modes,
        # Decision
        "recommended_action": decision.recommended_action.value,
        "action_color": _ACTION_COLORS.get(decision.recommended_action.value, "#77766D"),
        "next_inspection_formatted": f"{decision.next_inspection_interval_years:.2f}",
        # Escalation trace
        "baseline_action": esc.baseline_action.value,
        "degradation_escalation_applied": esc.degradation_escalation_applied,
        "failure_mode_escalation_applied": esc.failure_mode_escalation_applied,
        "triggering_failure_modes": [c.value for c in esc.triggering_failure_modes],
        # Cost
        "cost_currency": cost.currency,
        "cost_low_formatted": f"{cost.low:,.0f}",
        "cost_high_formatted": f"{cost.high:,.0f}",
        "cost_basis": cost.basis,
        # Photographic Evidence & Defect Inventory
        "input_image_path": input_image_path,
        "image_data_uri": image_data_uri,
        "detections": enriched_detections,
        "defect_count": len(enriched_detections),
        "counting_method": "Instance segmentation connected components with morphological skeletonization",
        "image_width": image_width,
        "image_height": image_height,
        "image_quality": image_quality or {},
        "calibration": calibration_info or {},
        "model_name": model_name or ass_meta.get("model_name", "shm_ai_crack_seg_finetune_15e_best.pt"),
        "depth_disclosure": (
            "Subsurface crack depth cannot be measured from 2D optical surface photography. "
            "Ultrasonic pulse velocity (UPV) or impact-echo non-destructive testing is required to quantify penetration."
        ),
        # Methodology & Governance
        "assessment_method": assessment_method,
        "data_sources": data_sources,
        "assumptions": assumptions,
        "limitations": limitations,
        "missing_inputs": missing_inputs,
        # Degradation (excluded by default from UI)
        "has_degradation": has_degradation,
        "degradation": degradation,
        # Metadata
        "service_version": str(report.metadata.get("service_version", "1.0.0")),
        "engine_versions": engine_versions,
    }


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------


def _find_chromium_executable() -> Path | None:
    """Find a local Chromium-based browser (Edge, Chrome, Chromium) for headless PDF export."""
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / r"Microsoft\Edge\Application\msedge.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / r"Microsoft\Edge\Application\msedge.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / r"Google\Chrome\Application\chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / r"Google\Chrome\Application\chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / r"Microsoft\Edge\Application\msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / r"Google\Chrome\Application\chrome.exe",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    for name in ("msedge", "chrome", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


class ReportGenerator:
    """
    Converts a RecommendationReport into an HTML string or PDF bytes.
    """

    TEMPLATE_NAME: str = "report.html.j2"

    def __init__(self, config: ReportGeneratorConfig | None = None) -> None:
        self._config = config or ReportGeneratorConfig()
        self._env = Environment(
            loader=FileSystemLoader(str(self._config.template_dir)),
            autoescape=True,
        )

    def render_html(
        self,
        input: RecommendationInput,
        report: RecommendationReport,
        generated_at_utc: str | None = None,
        asset_name: str | None = None,
        input_image_path: str | None = None,
        detections: list[dict[str, Any]] | None = None,
        assessment_meta: dict[str, Any] | None = None,
        image_quality: dict[str, Any] | None = None,
        calibration_info: dict[str, Any] | None = None,
        model_name: str | None = None,
        image_width: int = 1000,
        image_height: int = 1000,
        image_data_uri: str | None = None,
    ) -> str:
        """Render the report as an HTML string."""
        template = self._env.get_template(self.TEMPLATE_NAME)
        context = _build_context(
            input=input,
            report=report,
            generator_version=self._config.generator_version,
            generated_at_utc=generated_at_utc,
            asset_name=asset_name,
            input_image_path=input_image_path,
            detections=detections,
            assessment_meta=assessment_meta,
            image_quality=image_quality,
            calibration_info=calibration_info,
            model_name=model_name,
            image_width=image_width,
            image_height=image_height,
            image_data_uri=image_data_uri,
        )
        return template.render(**context)

    def generate_pdf_from_html(self, html: str) -> bytes:
        """Convert a rendered HTML report string into high-fidelity PDF bytes."""
        # 1. Prefer headless Chromium / Edge (fast, pixel-perfect modern CSS/SVG support)
        browser_exe = _find_chromium_executable()
        if browser_exe:
            with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
                f.write(html)
                tmp_html = Path(f.name)
            tmp_pdf = tmp_html.with_suffix(".pdf")
            try:
                cmd = [
                    str(browser_exe),
                    "--headless",
                    "--disable-gpu",
                    "--no-pdf-header-footer",
                    f"--print-to-pdf={tmp_pdf}",
                    tmp_html.as_uri(),
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
                if proc.returncode == 0 and tmp_pdf.is_file():
                    return tmp_pdf.read_bytes()
            finally:
                if tmp_html.is_file():
                    try:
                        tmp_html.unlink()
                    except OSError:
                        pass
                if tmp_pdf.is_file():
                    try:
                        tmp_pdf.unlink()
                    except OSError:
                        pass

        # 2. Fallback to WeasyPrint if installed
        try:
            import weasyprint
            return cast("bytes", weasyprint.HTML(string=html).write_pdf())
        except ImportError:
            pass

        raise RuntimeError(
            "PDF generation requires a Chromium-based browser (Microsoft Edge or Google Chrome) "
            "or the WeasyPrint Python package."
        )

    def generate_pdf(
        self,
        input: RecommendationInput,
        report: RecommendationReport,
        **kwargs: Any,
    ) -> bytes:
        """Render the report as a PDF byte stream."""
        html = self.render_html(input=input, report=report, **kwargs)
        return self.generate_pdf_from_html(html)
