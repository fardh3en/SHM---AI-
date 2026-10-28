"""
Unit tests for recommendation.report_generator.ReportGenerator.

Test strategy
-------------
Tests are organized by scenario type:
  - HTML rendering: render_html produces valid, non-empty HTML with key strings.
  - Determinism: identical inputs produce identical HTML string outputs with fixed timestamp.
  - Config override: custom template_dir / version works.
  - Degradation section handling: present when report supplied, absent when None.
  - WeasyPrint soft dependency: missing weasyprint raises RuntimeError with instructions.
  - PDF generation (optional/conditional): guarded by pytest.importorskip.

All tests are synchronous and self-contained.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from degradation.schemas import (
    CarbonationProjection,
    CorrosionProjection,
    DegradationAssessmentReport,
    InitiationStatus,
    MaintenanceDecision,
)
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
from recommendation.report_generator import ReportGenerator, ReportGeneratorConfig
from recommendation.schemas import RecommendationInput, RecommendationReport

# ---------------------------------------------------------------------------
# Factories & Fixtures
# ---------------------------------------------------------------------------


def _health_report(
    risk_level: RiskLevel = RiskLevel.HIGH,
) -> HealthAssessmentReport:
    return HealthAssessmentReport(
        asset_id="asset-101",
        inspection_id="insp-202",
        health_score=42.5,
        risk_level=risk_level,
        severity_breakdown=[
            DefectSeverityBreakdown(
                defect_category=DefectCategory.CRACK,
                severity=SeverityLevel.MODERATE,
                observation_count=3,
                total_area_mm2=12500.0,
            ),
            DefectSeverityBreakdown(
                defect_category=DefectCategory.SPALLING,
                severity=SeverityLevel.SEVERE,
                observation_count=1,
                total_area_mm2=4500.0,
            ),
        ],
        failure_modes=[
            StructuralFailureMode(
                category=FailureModeCategory.FLEXURAL,
                confidence=0.85,
                description="High flexural crack density near mid-span.",
            )
        ],
    )


def _degradation_report(requires_maintenance: bool = True) -> DegradationAssessmentReport:
    return DegradationAssessmentReport(
        asset_id="asset-101",
        inspection_id="insp-202",
        carbonation=CarbonationProjection(
            depth_mm_now=18.5,
            time_to_depassivation_years=12.0,
            carbonation_rate_mm_per_sqrt_year=3.2,
        ),
        corrosion=CorrosionProjection(
            initiation_status=InitiationStatus.INITIATED,
            years_since_initiation=2.5,
            corrosion_probability_now=0.75,
            propagation_rate_mm_per_year=0.05,
        ),
        maintenance_decision=MaintenanceDecision(
            maintenance_required=requires_maintenance,
            corrosion_index_exceeds_ceiling=True,
            carbonation_exceeds_cover_fraction=False,
            secondary_initiation_triggered=False,
        ),
        requires_maintenance=requires_maintenance,
    )


def _recommendation_input(
    with_degradation: bool = True,
    risk_level: RiskLevel = RiskLevel.HIGH,
) -> RecommendationInput:
    return RecommendationInput(
        asset_id="asset-101",
        inspection_id="insp-202",
        asset_type=AssetType.BRIDGE,
        health_report=_health_report(risk_level=risk_level),
        degradation_report=_degradation_report() if with_degradation else None,
    )


@pytest.fixture
def sample_report_tuple() -> tuple[RecommendationInput, RecommendationReport]:
    inp = _recommendation_input(with_degradation=True)
    service = RecommendationService()
    report = service.assess(inp)
    return inp, report


@pytest.fixture
def generator() -> ReportGenerator:
    return ReportGenerator()


# ---------------------------------------------------------------------------
# HTML Rendering Tests
# ---------------------------------------------------------------------------


class TestRenderHtml:
    def test_render_html_returns_nonempty_string(
        self,
        generator: ReportGenerator,
        sample_report_tuple: tuple[RecommendationInput, RecommendationReport],
    ) -> None:
        inp, report = sample_report_tuple
        html = generator.render_html(inp, report)
        assert isinstance(html, str)
        assert len(html) > 0
        assert "<!DOCTYPE html>" in html

    def test_render_html_contains_asset_and_inspection_ids(
        self,
        generator: ReportGenerator,
        sample_report_tuple: tuple[RecommendationInput, RecommendationReport],
    ) -> None:
        inp, report = sample_report_tuple
        html = generator.render_html(inp, report)
        assert "asset-101" in html
        assert "insp-202" in html
        assert "BRIDGE" in html

    def test_render_html_contains_health_and_decision_data(
        self,
        generator: ReportGenerator,
        sample_report_tuple: tuple[RecommendationInput, RecommendationReport],
    ) -> None:
        inp, report = sample_report_tuple
        html = generator.render_html(inp, report)
        assert "42.5" in html
        assert "HIGH" in html
        assert "REPAIR" in html

    def test_render_html_contains_defect_breakdown(
        self,
        generator: ReportGenerator,
        sample_report_tuple: tuple[RecommendationInput, RecommendationReport],
    ) -> None:
        inp, report = sample_report_tuple
        html = generator.render_html(inp, report)
        assert "Crack" in html or "crack" in html
        assert "Spalling" in html or "spalling" in html
        assert "12,500.0" in html

    def test_render_html_with_degradation_report(
        self,
        generator: ReportGenerator,
        sample_report_tuple: tuple[RecommendationInput, RecommendationReport],
    ) -> None:
        inp, report = sample_report_tuple
        html = generator.render_html(inp, report)
        assert "18.50" in html  # carbonation depth formatted
        assert "12.0 years" in html

    def test_render_html_without_degradation_report(
        self, generator: ReportGenerator
    ) -> None:
        inp = _recommendation_input(with_degradation=False)
        service = RecommendationService()
        report = service.assess(inp)

        html = generator.render_html(inp, report)
        assert "No Phase 4 Degradation Assessment Available" in html


# ---------------------------------------------------------------------------
# Determinism Tests
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_identical_inputs_produce_identical_html(
        self,
        generator: ReportGenerator,
        sample_report_tuple: tuple[RecommendationInput, RecommendationReport],
    ) -> None:
        inp, report = sample_report_tuple
        fixed_time = "2026-07-19 12:00:00 UTC"

        html1 = generator.render_html(inp, report, generated_at_utc=fixed_time)
        html2 = generator.render_html(inp, report, generated_at_utc=fixed_time)

        assert html1 == html2


# ---------------------------------------------------------------------------
# Config Override Tests
# ---------------------------------------------------------------------------


class TestConfigOverride:
    def test_custom_generator_version(
        self, sample_report_tuple: tuple[RecommendationInput, RecommendationReport]
    ) -> None:
        inp, report = sample_report_tuple
        config = ReportGeneratorConfig(generator_version="9.9.9-test")
        gen = ReportGenerator(config=config)

        html = gen.render_html(inp, report)
        assert "9.9.9-test" in html


# ---------------------------------------------------------------------------
# Soft Dependency Tests
# ---------------------------------------------------------------------------


class TestSoftDependency:
    def test_generate_pdf_raises_runtime_error_when_weasyprint_missing(
        self,
        generator: ReportGenerator,
        sample_report_tuple: tuple[RecommendationInput, RecommendationReport],
    ) -> None:
        inp, report = sample_report_tuple

        # Simulate missing WeasyPrint package and no Chromium browser
        with (
            patch("recommendation.report_generator._find_chromium_executable", return_value=None),
            patch.dict("sys.modules", {"weasyprint": None}),
            pytest.raises(RuntimeError, match="PDF generation requires a Chromium-based browser"),
        ):
            generator.generate_pdf(inp, report)


# ---------------------------------------------------------------------------
# PDF Generation Tests (Conditional)
# ---------------------------------------------------------------------------


class TestPdfGeneration:
    def test_generate_pdf_if_engine_available(
        self,
        generator: ReportGenerator,
        sample_report_tuple: tuple[RecommendationInput, RecommendationReport],
    ) -> None:
        inp, report = sample_report_tuple

        try:
            pdf_bytes = generator.generate_pdf(inp, report)
            assert isinstance(pdf_bytes, bytes)
            assert pdf_bytes.startswith(b"%PDF")
        except RuntimeError:
            pytest.skip("Neither Chromium nor WeasyPrint is available in the test environment")

