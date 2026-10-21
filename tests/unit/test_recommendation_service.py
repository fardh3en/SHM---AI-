"""
Unit tests for recommendation.recommendation_service.RecommendationService.

Test strategy
-------------
Tests are organized by scenario type:
  - Orchestration: each engine (RecommendationEngine, CostEstimator) is
    called exactly once, in order, using real objects (no mocking).
  - Output schema validity: RecommendationReport fields are populated correctly.
  - Metadata: service name, version, timestamp, and engine versions appear.
  - DI / config: constructor injection works; custom engines are used.
  - Determinism: identical inputs produce identical reports.
  - Graceful degradation: degradation_report=None works end-to-end.
  - Integration: full pipeline with real engines, real reports.

All tests are synchronous and self-contained.
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock, call

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
    HealthAssessmentReport,
    RiskLevel,
    SeverityLevel,
)
from recommendation.cost_estimator import CostEstimator, CostEstimatorConfig
from recommendation.engine import RecommendationEngine, RecommendationEngineConfig
from recommendation.recommendation_service import (
    RecommendationService,
    RecommendationServiceConfig,
)
from recommendation.schemas import (
    CostEstimate,
    EscalationTrace,
    RecommendationDecision,
    RecommendationInput,
    RecommendationReport,
    RecommendedActionType,
)


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _health_report(
    risk_level: RiskLevel = RiskLevel.MEDIUM,
    severity_breakdown: list[DefectSeverityBreakdown] | None = None,
) -> HealthAssessmentReport:
    return HealthAssessmentReport(
        asset_id="asset-001",
        inspection_id="insp-001",
        health_score=60.0,
        risk_level=risk_level,
        severity_breakdown=severity_breakdown or [],
    )


def _degradation_report(requires_maintenance: bool = False) -> DegradationAssessmentReport:
    carbonation = CarbonationProjection(
        depth_mm_now=10.0,
        time_to_depassivation_years=50.0,
        carbonation_rate_mm_per_sqrt_year=2.0,
    )
    corrosion = CorrosionProjection(
        initiation_status=InitiationStatus.NOT_INITIATED,
        years_since_initiation=None,
        corrosion_probability_now=0.0,
        propagation_rate_mm_per_year=None,
    )
    md = MaintenanceDecision(
        maintenance_required=requires_maintenance,
        corrosion_index_exceeds_ceiling=False,
        carbonation_exceeds_cover_fraction=False,
        secondary_initiation_triggered=False,
    )
    return DegradationAssessmentReport(
        asset_id="asset-001",
        inspection_id="insp-001",
        carbonation=carbonation,
        corrosion=corrosion,
        maintenance_decision=md,
        requires_maintenance=requires_maintenance,
    )


def _recommendation_input(
    risk_level: RiskLevel = RiskLevel.MEDIUM,
    degradation_report: DegradationAssessmentReport | None = None,
    severity_breakdown: list[DefectSeverityBreakdown] | None = None,
) -> RecommendationInput:
    return RecommendationInput(
        asset_id="asset-001",
        inspection_id="insp-001",
        asset_type=AssetType.BUILDING,
        health_report=_health_report(
            risk_level=risk_level,
            severity_breakdown=severity_breakdown,
        ),
        degradation_report=degradation_report,
    )


@pytest.fixture
def service() -> RecommendationService:
    return RecommendationService()


# ---------------------------------------------------------------------------
# Return type validity
# ---------------------------------------------------------------------------


class TestReturnTypeValidity:
    def test_returns_recommendation_report(
        self, service: RecommendationService
    ) -> None:
        inp = _recommendation_input()
        result = service.assess(inp)
        assert isinstance(result, RecommendationReport)

    def test_asset_id_matches_input(self, service: RecommendationService) -> None:
        inp = _recommendation_input()
        result = service.assess(inp)
        assert result.asset_id == "asset-001"

    def test_inspection_id_matches_input(self, service: RecommendationService) -> None:
        inp = _recommendation_input()
        result = service.assess(inp)
        assert result.inspection_id == "insp-001"

    def test_decision_field_is_recommendation_decision(
        self, service: RecommendationService
    ) -> None:
        inp = _recommendation_input()
        result = service.assess(inp)
        assert isinstance(result.decision, RecommendationDecision)

    def test_cost_estimate_field_is_cost_estimate(
        self, service: RecommendationService
    ) -> None:
        inp = _recommendation_input()
        result = service.assess(inp)
        assert isinstance(result.cost_estimate, CostEstimate)

    def test_cost_estimate_low_le_high(self, service: RecommendationService) -> None:
        inp = _recommendation_input()
        result = service.assess(inp)
        assert result.cost_estimate.low <= result.cost_estimate.high


# ---------------------------------------------------------------------------
# Orchestration (real objects, each engine called exactly once, in order)
# ---------------------------------------------------------------------------


class TestOrchestration:
    """
    Verify that each engine is called exactly once and the outputs are
    assembled into the report correctly.

    Uses real engine objects (no mocking of business logic).
    Call-count tracking done via MagicMock wrappers on the decide/estimate
    methods only, not on the whole engine — so the real logic still runs.
    """

    def test_engine_called_exactly_once(self) -> None:
        real_engine = RecommendationEngine()
        real_estimator = CostEstimator()

        # Track calls via wrapping
        original_decide = real_engine.decide
        decide_calls: list[RecommendationInput] = []

        def tracked_decide(input: RecommendationInput) -> RecommendationDecision:
            decide_calls.append(input)
            return original_decide(input)

        real_engine.decide = tracked_decide  # type: ignore[method-assign]

        service = RecommendationService(engine=real_engine, cost_estimator=real_estimator)
        inp = _recommendation_input()
        service.assess(inp)

        assert len(decide_calls) == 1

    def test_cost_estimator_called_exactly_once(self) -> None:
        real_engine = RecommendationEngine()
        real_estimator = CostEstimator()

        original_estimate = real_estimator.estimate
        estimate_calls: list[tuple[RecommendationInput, RecommendationDecision]] = []

        def tracked_estimate(
            input: RecommendationInput, decision: RecommendationDecision
        ) -> CostEstimate:
            estimate_calls.append((input, decision))
            return original_estimate(input, decision)

        real_estimator.estimate = tracked_estimate  # type: ignore[method-assign]

        service = RecommendationService(engine=real_engine, cost_estimator=real_estimator)
        inp = _recommendation_input()
        service.assess(inp)

        assert len(estimate_calls) == 1

    def test_cost_estimator_receives_decision_from_engine(self) -> None:
        """The CostEstimator must receive the actual decision produced by the engine."""
        real_engine = RecommendationEngine()
        real_estimator = CostEstimator()

        captured_decision: list[RecommendationDecision] = []
        original_estimate = real_estimator.estimate

        def tracked_estimate(
            input: RecommendationInput, decision: RecommendationDecision
        ) -> CostEstimate:
            captured_decision.append(decision)
            return original_estimate(input, decision)

        real_estimator.estimate = tracked_estimate  # type: ignore[method-assign]

        service = RecommendationService(engine=real_engine, cost_estimator=real_estimator)
        inp = _recommendation_input()
        report = service.assess(inp)

        # The captured decision must be the same object as the report's decision.
        assert captured_decision[0] is report.decision

    def test_engines_called_in_order_decide_before_estimate(self) -> None:
        """Engine.decide must be called before CostEstimator.estimate."""
        call_order: list[str] = []
        real_engine = RecommendationEngine()
        real_estimator = CostEstimator()

        original_decide = real_engine.decide
        original_estimate = real_estimator.estimate

        def tracked_decide(input: RecommendationInput) -> RecommendationDecision:
            call_order.append("decide")
            return original_decide(input)

        def tracked_estimate(
            input: RecommendationInput, decision: RecommendationDecision
        ) -> CostEstimate:
            call_order.append("estimate")
            return original_estimate(input, decision)

        real_engine.decide = tracked_decide  # type: ignore[method-assign]
        real_estimator.estimate = tracked_estimate  # type: ignore[method-assign]

        service = RecommendationService(engine=real_engine, cost_estimator=real_estimator)
        service.assess(_recommendation_input())

        assert call_order == ["decide", "estimate"]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_metadata_contains_service_name(self, service: RecommendationService) -> None:
        result = service.assess(_recommendation_input())
        assert result.metadata.get("service") == "RecommendationService"

    def test_metadata_contains_service_version(
        self, service: RecommendationService
    ) -> None:
        result = service.assess(_recommendation_input())
        assert "service_version" in result.metadata

    def test_metadata_contains_timestamp(self, service: RecommendationService) -> None:
        result = service.assess(_recommendation_input())
        assert "assessed_at_utc" in result.metadata
        # ISO 8601 format check.
        ts = result.metadata["assessed_at_utc"]
        assert re.match(r"\d{4}-\d{2}-\d{2}T", ts)

    def test_metadata_contains_engine_versions(
        self, service: RecommendationService
    ) -> None:
        result = service.assess(_recommendation_input())
        assert "engine_versions" in result.metadata
        versions = result.metadata["engine_versions"]
        assert "recommendation_engine" in versions
        assert "cost_estimator" in versions

    def test_engine_versions_are_strings(self, service: RecommendationService) -> None:
        result = service.assess(_recommendation_input())
        versions = result.metadata["engine_versions"]
        for key, val in versions.items():
            assert isinstance(val, str), f"Version for {key!r} must be a string"

    def test_custom_service_version_in_metadata(self) -> None:
        config = RecommendationServiceConfig(service_version="99.0.0")
        service = RecommendationService(config=config)
        result = service.assess(_recommendation_input())
        assert result.metadata["service_version"] == "99.0.0"

    def test_include_engine_versions_false_omits_versions(self) -> None:
        config = RecommendationServiceConfig(include_engine_versions=False)
        service = RecommendationService(config=config)
        result = service.assess(_recommendation_input())
        assert "engine_versions" not in result.metadata


# ---------------------------------------------------------------------------
# DI / Config
# ---------------------------------------------------------------------------


class TestDIAndConfig:
    def test_default_construction_works(self) -> None:
        service = RecommendationService()
        result = service.assess(_recommendation_input())
        assert isinstance(result, RecommendationReport)

    def test_injected_engines_are_used(self) -> None:
        """Custom engines are used, not the defaults."""
        custom_engine = RecommendationEngine(
            config=RecommendationEngineConfig(engine_version="test-engine")
        )
        custom_estimator = CostEstimator(
            config=CostEstimatorConfig(engine_version="test-estimator")
        )
        service = RecommendationService(
            engine=custom_engine, cost_estimator=custom_estimator
        )
        result = service.assess(_recommendation_input())
        versions = result.metadata["engine_versions"]
        assert versions["recommendation_engine"] == "test-engine"
        assert versions["cost_estimator"] == "test-estimator"


# ---------------------------------------------------------------------------
# Graceful degradation — no Phase 4 report
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    def test_none_degradation_report_no_error(
        self, service: RecommendationService
    ) -> None:
        inp = _recommendation_input(degradation_report=None)
        result = service.assess(inp)
        assert isinstance(result, RecommendationReport)

    def test_none_degradation_report_baseline_decision(
        self, service: RecommendationService
    ) -> None:
        """Without a degradation report, action is the risk-level baseline."""
        inp = _recommendation_input(risk_level=RiskLevel.LOW, degradation_report=None)
        result = service.assess(inp)
        assert result.decision.recommended_action == RecommendedActionType.MONITOR
        assert result.decision.escalation.degradation_escalation_applied is False


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_identical_inputs_produce_identical_reports(
        self, service: RecommendationService
    ) -> None:
        breakdown = [
            DefectSeverityBreakdown(
                defect_category=DefectCategory.CRACK,
                severity=SeverityLevel.MODERATE,
                observation_count=2,
                total_area_mm2=8_000.0,
            )
        ]
        inp = _recommendation_input(
            risk_level=RiskLevel.HIGH, severity_breakdown=breakdown
        )

        r1 = service.assess(inp)
        r2 = service.assess(inp)

        assert r1.decision.recommended_action == r2.decision.recommended_action
        assert r1.decision.next_inspection_interval_years == (
            r2.decision.next_inspection_interval_years
        )
        assert r1.cost_estimate.low == r2.cost_estimate.low
        assert r1.cost_estimate.high == r2.cost_estimate.high
        assert r1.cost_estimate.basis == r2.cost_estimate.basis


# ---------------------------------------------------------------------------
# Full integration (real engines, real reports, end-to-end)
# ---------------------------------------------------------------------------


class TestIntegration:
    """
    End-to-end tests with real RecommendationEngine and CostEstimator.
    No mocking of business logic.
    """

    def test_low_risk_no_degradation_monitor(self, service: RecommendationService) -> None:
        inp = _recommendation_input(
            risk_level=RiskLevel.LOW, degradation_report=None
        )
        result = service.assess(inp)
        assert result.decision.recommended_action == RecommendedActionType.MONITOR

    def test_high_risk_with_breakdown_report_valid(
        self, service: RecommendationService
    ) -> None:
        breakdown = [
            DefectSeverityBreakdown(
                defect_category=DefectCategory.SPALLING,
                severity=SeverityLevel.SEVERE,
                observation_count=3,
                total_area_mm2=15_000.0,
            )
        ]
        inp = _recommendation_input(
            risk_level=RiskLevel.HIGH, severity_breakdown=breakdown
        )
        result = service.assess(inp)

        assert result.decision.recommended_action == RecommendedActionType.REPAIR
        assert result.cost_estimate.low > 0.0
        assert result.cost_estimate.high >= result.cost_estimate.low

    def test_low_risk_with_maintenance_escalates_to_repair(
        self, service: RecommendationService
    ) -> None:
        """Full pipeline: LOW risk + requires_maintenance → REPAIR."""
        inp = _recommendation_input(
            risk_level=RiskLevel.LOW,
            degradation_report=_degradation_report(requires_maintenance=True),
        )
        result = service.assess(inp)
        assert result.decision.recommended_action == RecommendedActionType.REPAIR

    def test_critical_risk_cost_includes_emergency_mobilization(
        self, service: RecommendationService
    ) -> None:
        """CRITICAL risk → EMERGENCY_INTERVENTION → cost includes mobilization."""
        inp = _recommendation_input(risk_level=RiskLevel.CRITICAL)
        result = service.assess(inp)

        assert result.decision.recommended_action == RecommendedActionType.EMERGENCY_INTERVENTION
        assert "emergency mobilization" in result.cost_estimate.basis.lower()
