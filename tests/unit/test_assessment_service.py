"""
Unit and integration tests for intelligence.assessment_service.AssessmentService.

Test strategy
-------------
Tests are split into three groups:

1. Unit tests — use simple stub implementations of the four interfaces so
   the service's orchestration logic can be verified without any real engine
   running.  Stubs are the minimal concrete classes needed; they carry no
   business logic.

2. Integration tests — wire the real concrete engines (HealthScorer,
   SeverityClassifier, EngineeringRulesEngine, RiskEngine) through the
   service and verify that the assembled report is schema-valid and
   internally consistent.

3. Edge-case tests — empty observations, asset age metadata, custom
   IRiskEngine (not a RiskEngine subclass).

All tests are synchronous and self-contained.
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest

from intelligence.assessment_service import AssessmentService, AssessmentServiceConfig
from intelligence.interfaces import (
    IEngineeringRulesEngine,
    IHealthScorer,
    IRiskEngine,
    ISeverityClassifier,
)
from intelligence.schemas import (
    AssetType,
    DefectCategory,
    DefectObservation,
    DefectSeverityBreakdown,
    FailureModeCategory,
    HealthAssessmentInput,
    HealthAssessmentReport,
    RiskLevel,
    SeverityLevel,
    StructuralFailureMode,
)

# ---------------------------------------------------------------------------
# Stubs (no business logic — only what the interface requires)
# ---------------------------------------------------------------------------


class _FixedScorer(IHealthScorer):
    """Returns a fixed health score."""

    def __init__(self, score: float = 80.0) -> None:
        self._score = score

    def calculate_score(self, assessment_input: HealthAssessmentInput) -> float:
        return self._score


class _FixedClassifier(ISeverityClassifier):
    """Returns a fixed severity breakdown list."""

    def __init__(self, breakdown: list[DefectSeverityBreakdown] | None = None) -> None:
        self._breakdown = breakdown or []

    def classify(
        self, assessment_input: HealthAssessmentInput
    ) -> list[DefectSeverityBreakdown]:
        return self._breakdown


class _FixedRulesEngine(IEngineeringRulesEngine):
    """Returns a fixed failure-mode list."""

    def __init__(self, modes: list[StructuralFailureMode] | None = None) -> None:
        self._modes = modes or []

    def identify_failure_modes(
        self, assessment_input: HealthAssessmentInput
    ) -> list[StructuralFailureMode]:
        return self._modes


class _FixedRiskEngine(IRiskEngine):
    """Returns a fixed RiskLevel — custom engine that does NOT subclass RiskEngine."""

    def __init__(self, level: RiskLevel = RiskLevel.LOW) -> None:
        self._level = level

    def determine_risk_level(self, health_score: float) -> RiskLevel:
        return self._level


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _input(
    *observations: DefectObservation,
    asset_age_years: float | None = None,
) -> HealthAssessmentInput:
    return HealthAssessmentInput(
        asset_id="asset-001",
        asset_type=AssetType.BRIDGE,
        inspection_id="insp-001",
        observations=list(observations),
        asset_age_years=asset_age_years,
    )


def _obs(
    category: DefectCategory = DefectCategory.CRACK,
    confidence: float = 0.85,
    area_mm2: float | None = None,
    width_mm: float | None = None,
) -> DefectObservation:
    return DefectObservation(
        defect_category=category,
        confidence=confidence,
        area_mm2=area_mm2,
        width_mm=width_mm,
    )


def _breakdown(
    severity: SeverityLevel,
    category: DefectCategory = DefectCategory.CRACK,
) -> DefectSeverityBreakdown:
    return DefectSeverityBreakdown(
        defect_category=category,
        severity=severity,
        observation_count=1,
    )


def _mode(
    confidence: float = 0.75,
    category: FailureModeCategory = FailureModeCategory.FLEXURAL,
) -> StructuralFailureMode:
    return StructuralFailureMode(
        category=category,
        description="test mode",
        confidence=confidence,
        related_defect_categories=[],
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_service() -> AssessmentService:
    """Service wired with simple stubs — no real engine runs."""
    return AssessmentService(
        scorer=_FixedScorer(80.0),
        classifier=_FixedClassifier([_breakdown(SeverityLevel.MODERATE)]),
        rules_engine=_FixedRulesEngine([_mode()]),
        risk_engine=_FixedRiskEngine(RiskLevel.MEDIUM),
    )


# ---------------------------------------------------------------------------
# Return-type and schema validity
# ---------------------------------------------------------------------------


class TestReturnTypeAndSchema:
    def test_returns_health_assessment_report(
        self, stub_service: AssessmentService
    ) -> None:
        result = stub_service.assess(_input())
        assert isinstance(result, HealthAssessmentReport)

    def test_asset_id_propagated(self, stub_service: AssessmentService) -> None:
        result = stub_service.assess(_input())
        assert result.asset_id == "asset-001"

    def test_inspection_id_propagated(self, stub_service: AssessmentService) -> None:
        result = stub_service.assess(_input())
        assert result.inspection_id == "insp-001"

    def test_health_score_from_scorer(self) -> None:
        service = AssessmentService(scorer=_FixedScorer(63.5))
        result = service.assess(_input())
        assert result.health_score == 63.5

    def test_risk_level_from_risk_engine(self) -> None:
        service = AssessmentService(
            scorer=_FixedScorer(90.0),
            risk_engine=_FixedRiskEngine(RiskLevel.CRITICAL),
        )
        result = service.assess(_input())
        assert result.risk_level == RiskLevel.CRITICAL

    def test_severity_breakdown_from_classifier(self) -> None:
        expected = [
            _breakdown(SeverityLevel.SEVERE, DefectCategory.CORROSION),
            _breakdown(SeverityLevel.MINOR, DefectCategory.SPALLING),
        ]
        service = AssessmentService(classifier=_FixedClassifier(expected))
        result = service.assess(_input())
        assert result.severity_breakdown == expected

    def test_failure_modes_from_rules_engine(self) -> None:
        expected = [_mode(0.80, FailureModeCategory.SHEAR)]
        service = AssessmentService(rules_engine=_FixedRulesEngine(expected))
        result = service.assess(_input())
        assert result.failure_modes == expected

    def test_health_score_in_valid_range(self) -> None:
        for score in (0.0, 50.0, 100.0):
            service = AssessmentService(scorer=_FixedScorer(score))
            report = service.assess(_input())
            assert 0.0 <= report.health_score <= 100.0


# ---------------------------------------------------------------------------
# Orchestration — engines are each called exactly once
# ---------------------------------------------------------------------------


class TestOrchestration:
    def test_scorer_called_exactly_once(self) -> None:
        mock_scorer = MagicMock(spec=IHealthScorer)
        mock_scorer.calculate_score.return_value = 75.0
        service = AssessmentService(scorer=mock_scorer)
        ai = _input(_obs())
        service.assess(ai)
        mock_scorer.calculate_score.assert_called_once_with(ai)

    def test_classifier_called_exactly_once(self) -> None:
        mock_classifier = MagicMock(spec=ISeverityClassifier)
        mock_classifier.classify.return_value = []
        service = AssessmentService(classifier=mock_classifier)
        ai = _input(_obs())
        service.assess(ai)
        mock_classifier.classify.assert_called_once_with(ai)

    def test_rules_engine_called_exactly_once(self) -> None:
        mock_rules = MagicMock(spec=IEngineeringRulesEngine)
        mock_rules.identify_failure_modes.return_value = []
        service = AssessmentService(rules_engine=mock_rules)
        ai = _input(_obs())
        service.assess(ai)
        mock_rules.identify_failure_modes.assert_called_once_with(ai)

    def test_risk_engine_called_exactly_once_via_interface(self) -> None:
        """Custom IRiskEngine (not a RiskEngine): determine_risk_level is called."""
        mock_risk = MagicMock(spec=IRiskEngine)
        mock_risk.determine_risk_level.return_value = RiskLevel.MEDIUM
        service = AssessmentService(risk_engine=mock_risk)
        service.assess(_input(_obs()))
        mock_risk.determine_risk_level.assert_called_once()

    def test_assessment_input_passed_to_all_engines(self) -> None:
        """Verify the same HealthAssessmentInput reaches every engine."""
        received: dict[str, HealthAssessmentInput] = {}

        class _TrackingScorer(IHealthScorer):
            def calculate_score(self, ai: HealthAssessmentInput) -> float:
                received["scorer"] = ai
                return 80.0

        class _TrackingClassifier(ISeverityClassifier):
            def classify(self, ai: HealthAssessmentInput) -> list[DefectSeverityBreakdown]:
                received["classifier"] = ai
                return []

        class _TrackingRulesEngine(IEngineeringRulesEngine):
            def identify_failure_modes(
                self, ai: HealthAssessmentInput
            ) -> list[StructuralFailureMode]:
                received["rules_engine"] = ai
                return []

        ai = _input(_obs())
        service = AssessmentService(
            scorer=_TrackingScorer(),
            classifier=_TrackingClassifier(),
            rules_engine=_TrackingRulesEngine(),
        )
        service.assess(ai)

        assert received["scorer"] is ai
        assert received["classifier"] is ai
        assert received["rules_engine"] is ai


# ---------------------------------------------------------------------------
# RiskEngine.assess() path vs. determine_risk_level() fallback
# ---------------------------------------------------------------------------


class TestRiskEnginePath:
    def test_concrete_risk_engine_uses_assess_method(self) -> None:
        """
        When the injected engine is a concrete RiskEngine, assess() should
        be called (not determine_risk_level()).  We verify this indirectly:
        a single high-confidence FLEXURAL failure mode with a good health score
        should escalate beyond the score-only baseline.
        """
        from intelligence.risk_engine import RiskEngine

        service = AssessmentService(
            scorer=_FixedScorer(85.0),  # Stage 1 baseline → LOW
            classifier=_FixedClassifier([]),
            rules_engine=_FixedRulesEngine(
                [_mode(0.82, FailureModeCategory.FLEXURAL)]  # high-risk category
            ),
            risk_engine=RiskEngine(),
        )
        result = service.assess(_input())
        # FLEXURAL with conf 0.82 triggers high-risk category bonus → HIGH
        assert result.risk_level == RiskLevel.HIGH

    def test_custom_irisk_engine_uses_determine_risk_level(self) -> None:
        """
        A custom IRiskEngine that is NOT a RiskEngine subclass must have
        determine_risk_level() called, not assess().
        """
        mock_risk = MagicMock(spec=IRiskEngine)
        mock_risk.determine_risk_level.return_value = RiskLevel.MEDIUM

        service = AssessmentService(
            scorer=_FixedScorer(80.0),
            risk_engine=mock_risk,
        )
        service.assess(_input(_obs()))

        mock_risk.determine_risk_level.assert_called_once_with(80.0)
        # assess() should NOT have been called
        assert not mock_risk.assess.called if hasattr(mock_risk, "assess") else True

    def test_score_passed_correctly_to_determine_risk_level(self) -> None:
        """Score from IHealthScorer is forwarded verbatim to IRiskEngine."""
        received_scores: list[float] = []

        class _CapturingRiskEngine(IRiskEngine):
            def determine_risk_level(self, health_score: float) -> RiskLevel:
                received_scores.append(health_score)
                return RiskLevel.LOW

        service = AssessmentService(
            scorer=_FixedScorer(42.7),
            risk_engine=_CapturingRiskEngine(),
        )
        service.assess(_input())
        assert received_scores == [42.7]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_metadata_is_dict(self, stub_service: AssessmentService) -> None:
        result = stub_service.assess(_input())
        assert isinstance(result.metadata, dict)

    def test_metadata_contains_service_key(self, stub_service: AssessmentService) -> None:
        result = stub_service.assess(_input())
        assert result.metadata["service"] == "AssessmentService"

    def test_metadata_contains_service_version(self, stub_service: AssessmentService) -> None:
        result = stub_service.assess(_input())
        assert "service_version" in result.metadata

    def test_metadata_contains_assessed_at_utc(
        self, stub_service: AssessmentService
    ) -> None:
        result = stub_service.assess(_input())
        ts = result.metadata["assessed_at_utc"]
        assert isinstance(ts, str)
        # Must be a valid ISO-8601 UTC timestamp
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts)

    def test_metadata_contains_observation_count(
        self, stub_service: AssessmentService
    ) -> None:
        obs = [_obs(), _obs(DefectCategory.CORROSION)]
        result = stub_service.assess(_input(*obs))
        assert result.metadata["observation_count"] == 2

    def test_metadata_observation_count_zero_for_empty_input(
        self, stub_service: AssessmentService
    ) -> None:
        result = stub_service.assess(_input())
        assert result.metadata["observation_count"] == 0

    def test_metadata_contains_asset_type(self, stub_service: AssessmentService) -> None:
        result = stub_service.assess(_input())
        assert result.metadata["asset_type"] == AssetType.BRIDGE

    def test_metadata_asset_age_present_when_provided(self) -> None:
        service = AssessmentService(scorer=_FixedScorer())
        result = service.assess(_input(asset_age_years=35.0))
        assert result.metadata["asset_age_years"] == 35.0

    def test_metadata_asset_age_absent_when_not_provided(self) -> None:
        service = AssessmentService(scorer=_FixedScorer())
        result = service.assess(_input())
        assert "asset_age_years" not in result.metadata

    def test_metadata_engine_versions_present_with_real_engines(self) -> None:
        """Real engines expose _config.engine_version — verify capture."""
        service = AssessmentService()  # all defaults
        result = service.assess(_input())
        versions = result.metadata.get("engine_versions", {})
        assert isinstance(versions, dict)
        assert len(versions) > 0

    def test_metadata_engine_versions_empty_for_stub_engines(self) -> None:
        """Stubs have no _config attribute — versions dict should be empty."""
        service = AssessmentService(
            scorer=_FixedScorer(),
            classifier=_FixedClassifier(),
            rules_engine=_FixedRulesEngine(),
            risk_engine=_FixedRiskEngine(),
        )
        result = service.assess(_input())
        versions = result.metadata.get("engine_versions", {})
        assert versions == {}

    def test_metadata_engine_versions_suppressed_by_config(self) -> None:
        config = AssessmentServiceConfig(include_engine_versions=False)
        service = AssessmentService(config=config)
        result = service.assess(_input())
        assert "engine_versions" not in result.metadata

    def test_custom_service_version_in_metadata(self) -> None:
        config = AssessmentServiceConfig(service_version="2.3.1")
        service = AssessmentService(config=config)
        result = service.assess(_input())
        assert result.metadata["service_version"] == "2.3.1"


# ---------------------------------------------------------------------------
# Default engine instantiation
# ---------------------------------------------------------------------------


class TestDefaultEngines:
    def test_default_service_instantiates_without_arguments(self) -> None:
        service = AssessmentService()
        assert service is not None

    def test_default_service_returns_valid_report_for_empty_input(self) -> None:
        service = AssessmentService()
        result = service.assess(_input())
        assert isinstance(result, HealthAssessmentReport)
        assert result.health_score == 100.0
        assert result.severity_breakdown == []
        assert result.failure_modes == []

    def test_default_service_produces_consistent_output(self) -> None:
        """Same input → same output (determinism)."""
        service = AssessmentService()
        ai = _input(
            _obs(DefectCategory.CRACK, 0.85, width_mm=2.0),
            _obs(DefectCategory.CORROSION, 0.80, area_mm2=10_000.0),
        )
        r1 = service.assess(ai)
        r2 = service.assess(ai)
        assert r1.health_score == r2.health_score
        assert r1.risk_level == r2.risk_level
        assert len(r1.severity_breakdown) == len(r2.severity_breakdown)
        assert len(r1.failure_modes) == len(r2.failure_modes)


# ---------------------------------------------------------------------------
# Integration — real engines end-to-end
# ---------------------------------------------------------------------------


class TestIntegration:
    """Wire all real concrete engines and verify report coherence."""

    def test_pristine_asset_report(self) -> None:
        service = AssessmentService()
        result = service.assess(_input())
        assert result.health_score == 100.0
        assert result.risk_level == RiskLevel.LOW
        assert result.severity_breakdown == []
        assert result.failure_modes == []

    def test_heavily_degraded_asset_report(self) -> None:
        """
        An asset with many severe defects should produce a high or critical
        risk level, non-empty severity breakdown, and at least one failure mode.
        """
        service = AssessmentService()
        assessment = _input(
            _obs(DefectCategory.CRACK, 0.90, width_mm=3.0),
            _obs(DefectCategory.CRACK, 0.85, width_mm=2.5),
            _obs(DefectCategory.CRACK, 0.80, width_mm=2.0),
            _obs(DefectCategory.SPALLING, 0.88, area_mm2=40_000.0),
            _obs(DefectCategory.CORROSION, 0.85, area_mm2=30_000.0),
            _obs(DefectCategory.EXPOSED_REINFORCEMENT, 0.82, area_mm2=8_000.0),
        )
        result = service.assess(assessment)

        assert result.health_score < 60.0
        assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert len(result.severity_breakdown) > 0
        assert len(result.failure_modes) > 0

    def test_report_ids_match_input(self) -> None:
        service = AssessmentService()
        ai = HealthAssessmentInput(
            asset_id="bridge-007",
            asset_type=AssetType.BRIDGE,
            inspection_id="insp-XYZ-99",
            observations=[],
        )
        result = service.assess(ai)
        assert result.asset_id == "bridge-007"
        assert result.inspection_id == "insp-XYZ-99"

    def test_report_health_score_within_valid_range(self) -> None:
        service = AssessmentService()
        for n_obs in (0, 1, 5, 10):
            observations = [_obs(DefectCategory.CRACK, 0.85, width_mm=1.0)] * n_obs
            result = service.assess(_input(*observations))
            assert 0.0 <= result.health_score <= 100.0

    def test_report_risk_level_is_valid_enum_value(self) -> None:
        service = AssessmentService()
        result = service.assess(_input(_obs(DefectCategory.CORROSION, 0.90, area_mm2=20_000.0)))
        assert result.risk_level in list(RiskLevel)

    def test_severity_breakdown_categories_match_input_categories(self) -> None:
        """Classifier should return exactly the categories present in observations."""
        service = AssessmentService()
        ai = _input(
            _obs(DefectCategory.CRACK, 0.85),
            _obs(DefectCategory.SPALLING, 0.80, area_mm2=5_000.0),
        )
        result = service.assess(ai)
        breakdown_categories = {b.defect_category for b in result.severity_breakdown}
        assert DefectCategory.CRACK in breakdown_categories
        assert DefectCategory.SPALLING in breakdown_categories

    def test_failure_modes_have_valid_confidence(self) -> None:
        service = AssessmentService()
        assessment = _input(
            _obs(DefectCategory.CRACK, 0.90, width_mm=2.0),
            _obs(DefectCategory.EXPOSED_REINFORCEMENT, 0.85, area_mm2=6_000.0),
        )
        result = service.assess(assessment)
        for fm in result.failure_modes:
            assert 0.0 <= fm.confidence <= 1.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_observations_produces_perfect_score(self) -> None:
        service = AssessmentService()
        result = service.assess(_input())
        assert result.health_score == 100.0

    def test_single_observation(self) -> None:
        service = AssessmentService()
        result = service.assess(_input(_obs(DefectCategory.SURFACE_DAMAGE, 0.70)))
        assert isinstance(result, HealthAssessmentReport)

    def test_multiple_assess_calls_are_independent(self) -> None:
        """Calling assess() twice should produce independent reports."""
        service = AssessmentService()
        ai_clean = _input()
        ai_damaged = _input(
            _obs(DefectCategory.CRACK, 0.90, width_mm=4.0),
            _obs(DefectCategory.EXPOSED_REINFORCEMENT, 0.85, area_mm2=10_000.0),
        )
        r_clean = service.assess(ai_clean)
        r_damaged = service.assess(ai_damaged)
        assert r_clean.health_score > r_damaged.health_score
        assert r_clean is not r_damaged

    def test_partial_injection_uses_defaults_for_remaining(self) -> None:
        """Injecting only the scorer should leave the other three as defaults."""
        service = AssessmentService(scorer=_FixedScorer(55.0))
        result = service.assess(_input())
        # Score comes from our stub
        assert result.health_score == 55.0
        # Remaining engines are defaults — report should still be valid
        assert isinstance(result, HealthAssessmentReport)
