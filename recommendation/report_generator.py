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

#: Hex colours for each RiskLevel value.
_RISK_LEVEL_COLORS: dict[str, str] = {
    "low": "#27ae60",
    "medium": "#e67e22",
    "high": "#e74c3c",
    "critical": "#8e1414",
}

#: Hex colours for each RecommendedActionType value.
_ACTION_COLORS: dict[str, str] = {
    "monitor": "#27ae60",
    "inspect": "#e67e22",
    "repair": "#e74c3c",
    "emergency_intervention": "#8e1414",
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
) -> dict[str, Any]:
    """
    Build the Jinja2 template context dict from domain objects.
    """
    decision = report.decision
    cost = report.cost_estimate
    esc = decision.escalation
    health = input.health_report

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
        "risk_level_color": _RISK_LEVEL_COLORS.get(health.risk_level.value, "#495057"),
        # Defects
        "severity_breakdown": severity_breakdown,
        "failure_modes": failure_modes,
        # Decision
        "recommended_action": decision.recommended_action.value,
        "action_color": _ACTION_COLORS.get(decision.recommended_action.value, "#495057"),
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
        "detections": detections or [],
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
        )
        return template.render(**context)

    def generate_pdf(
        self,
        input: RecommendationInput,
        report: RecommendationReport,
        generated_at_utc: str | None = None,
        asset_name: str | None = None,
        input_image_path: str | None = None,
        detections: list[dict[str, Any]] | None = None,
        assessment_meta: dict[str, Any] | None = None,
    ) -> bytes:
        """Render the report as a PDF byte stream."""
        try:
            import weasyprint
        except ImportError:
            raise RuntimeError(
                "WeasyPrint is required for PDF generation but is not installed.\n"
                "Install it with:  pip install 'shm-ai[reports]'\n"
            ) from None

        html = self.render_html(
            input=input,
            report=report,
            generated_at_utc=generated_at_utc,
            asset_name=asset_name,
            input_image_path=input_image_path,
            detections=detections,
            assessment_meta=assessment_meta,
        )
        return cast("bytes", weasyprint.HTML(string=html).write_pdf())
