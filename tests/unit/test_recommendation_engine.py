"""
Unit tests for recommendation.engine.RecommendationEngine.

Test strategy
-------------
Tests are organized by scenario type:
  - Baseline mapping: each RiskLevel → correct action + interval,
    no escalation, when degradation_report=None and no escalating failure modes.
  - Graceful degradation: degradation_report=None never errors.
  - Stage 2 escalation: LOW risk + requires_maintenance=True → REPAIR.
    REAL, UNMOCKED integration test (no mocking of HealthAssessmentReport or
    DegradationAssessmentReport).
  - Stage 3 escalation: LOW risk + escalating failure mode at threshold
    confidence → EMERGENCY_INTERVENTION.
    REAL, UNMOCKED integration test.
  - Monotonicity: escalation never produces an action below the baseline,
    parametrized sweep of risk levels and escalation conditions.
  - Structural decoupling: RecommendationDecision's Pydantic field set
    contains no key with "cost" in its name.
  - Config override: custom rules produce correct output.
  - Determinism: identical inputs produce identical outputs.
  - Escalation trace accuracy: escalation flags and triggering_failure_modes
    are populated correctly.

All tests are synchronous and self-contained.
"""
from __future__ import annotations

import pytest

from degradation.models import ExposureClass, MaterialProperties
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
from recommendation.config import (
    DEFAULT_RECOMMENDATION_RULES,
    FailureModeEscalationConfig,
    RecommendationRule,
)
from recommendation.engine import RecommendationEngine, RecommendationEngineConfig
from recommendation.schemas import (
    RecommendationDecision,
    RecommendationInput,
    RecommendedActionType,
)


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _health_report(
    risk_level: RiskLevel = RiskLevel.LOW,
    failure_modes: list[StructuralFailureMode] | None = None,
    severity_breakdown: list[DefectSeverityBreakdown] | None = None,
) -> HealthAssessmentReport:
    """Build a minimal but fully valid HealthAssessmentReport."""
    return HealthAssessmentReport(
        asset_id="asset-001",
        inspection_id="insp-001",
        health_score=85.0,
        risk_level=risk_level,
        failure_modes=failure_modes or [],
        severity_breakdown=severity_breakdown or [],
    )


def _degradation_report(requires_maintenance: bool) -> DegradationAssessmentReport:
    """Build a minimal but fully valid DegradationAssessmentReport."""
    carbonation = CarbonationProjection(
        depth_mm_now=20.0,
        time_to_depassivation_years=40.0,
        carbonation_rate_mm_per_sqrt_year=4.5,
    )
    corrosion = CorrosionProjection(
        initiation_status=InitiationStatus.NOT_INITIATED,
        years_since_initiation=None,
        corrosion_probability_now=0.0,
        propagation_rate_mm_per_year=None,
    )
    maintenance_decision = MaintenanceDecision(
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
        maintenance_decision=maintenance_decision,
        requires_maintenance=requires_maintenance,
    )


def _recommendation_input(
    risk_level: RiskLevel = RiskLevel.LOW,
    degradation_report: DegradationAssessmentReport | None = None,
    failure_modes: list[StructuralFailureMode] | None = None,
) -> RecommendationInput:
    return RecommendationInput(
        asset_id="asset-001",
        inspection_id="insp-001",
        asset_type=AssetType.BUILDING,
        health_report=_health_report(
            risk_level=risk_level,
            failure_modes=failure_modes,
        ),
        degradation_report=degradation_report,
    )


@pytest.fixture
def engine() -> RecommendationEngine:
    return RecommendationEngine()


# ---------------------------------------------------------------------------
# Baseline mapping (all four risk levels, no escalation)
# ---------------------------------------------------------------------------


class TestBaselineMapping:
    """Each RiskLevel maps to the correct action and interval, no escalation."""

    @pytest.mark.parametrize(
        ("risk_level", "expected_action", "expected_interval"),
        [
            (RiskLevel.LOW, RecommendedActionType.MONITOR, 2.0),
            (RiskLevel.MEDIUM, RecommendedActionType.INSPECT, 1.0),
            (RiskLevel.HIGH, RecommendedActionType.REPAIR, 0.5),
            (RiskLevel.CRITICAL, RecommendedActionType.EMERGENCY_INTERVENTION, 0.1),
        ],
    )
    def test_baseline_action_and_interval(
        self,
        engine: RecommendationEngine,
        risk_level: RiskLevel,
        expected_action: RecommendedActionType,
        expected_interval: float,
    ) -> None:
        """Verify each RiskLevel produces the correct baseline action and interval."""
        inp = _recommendation_input(risk_level=risk_level, degradation_report=None)
        decision = engine.decide(inp)

        assert decision.recommended_action == expected_action
        assert decision.next_inspection_interval_years == pytest.approx(expected_interval)

    @pytest.mark.parametrize("risk_level", list(RiskLevel))
    def test_no_escalation_flags_when_no_triggers(
        self,
        engine: RecommendationEngine,
        risk_level: RiskLevel,
    ) -> None:
        """No escalation flags set when no escalating inputs are present."""
        inp = _recommendation_input(risk_level=risk_level, degradation_report=None)
        decision = engine.decide(inp)

        assert decision.escalation.degradation_escalation_applied is False
        assert decision.escalation.failure_mode_escalation_applied is False
        assert decision.escalation.triggering_failure_modes == []

    @pytest.mark.parametrize("risk_level", list(RiskLevel))
    def test_baseline_action_matches_escalation_trace(
        self,
        engine: RecommendationEngine,
        risk_level: RiskLevel,
    ) -> None:
        """EscalationTrace.baseline_action matches the expected default for the risk level."""
        inp = _recommendation_input(risk_level=risk_level, degradation_report=None)
        decision = engine.decide(inp)
        expected_baseline = DEFAULT_RECOMMENDATION_RULES[risk_level].action
        assert decision.escalation.baseline_action == expected_baseline


# ---------------------------------------------------------------------------
# Graceful degradation — degradation_report=None
# ---------------------------------------------------------------------------


class TestGracefulDegradationNone:
    """Explicit tests that None degradation_report never errors."""

    def test_none_degradation_report_does_not_error(
        self, engine: RecommendationEngine
    ) -> None:
        inp = _recommendation_input(
            risk_level=RiskLevel.MEDIUM, degradation_report=None
        )
        # Must not raise any exception.
        decision = engine.decide(inp)
        assert isinstance(decision, RecommendationDecision)

    def test_none_degradation_report_produces_baseline_only_decision(
        self, engine: RecommendationEngine
    ) -> None:
        """When degradation_report is None, the result is exactly the baseline decision."""
        inp = _recommendation_input(
            risk_level=RiskLevel.LOW, degradation_report=None
        )
        decision = engine.decide(inp)

        assert decision.recommended_action == RecommendedActionType.MONITOR
        assert decision.escalation.degradation_escalation_applied is False
        assert decision.escalation.failure_mode_escalation_applied is False

    @pytest.mark.parametrize("risk_level", list(RiskLevel))
    def test_none_degradation_report_all_levels(
        self,
        engine: RecommendationEngine,
        risk_level: RiskLevel,
    ) -> None:
        """All risk levels work correctly with degradation_report=None."""
        inp = _recommendation_input(risk_level=risk_level, degradation_report=None)
        decision = engine.decide(inp)
        assert isinstance(decision, RecommendationDecision)
        assert decision.escalation.degradation_escalation_applied is False


# ---------------------------------------------------------------------------
# Stage 2 escalation: real, unmocked integration test
# ---------------------------------------------------------------------------


class TestDegradationEscalation:
    """
    REAL, UNMOCKED integration tests for Stage 2 escalation.

    HealthAssessmentReport and DegradationAssessmentReport are constructed
    with real Pydantic models — no mocking.  This is the direct lesson from
    the Phase 4 bug: escalation interactions must be tested end-to-end.
    """

    def test_low_risk_requires_maintenance_escalates_to_repair(
        self, engine: RecommendationEngine
    ) -> None:
        """LOW risk + requires_maintenance=True must escalate to at least REPAIR."""
        inp = _recommendation_input(
            risk_level=RiskLevel.LOW,
            degradation_report=_degradation_report(requires_maintenance=True),
        )
        decision = engine.decide(inp)

        assert decision.recommended_action == RecommendedActionType.REPAIR
        assert decision.escalation.degradation_escalation_applied is True
        assert decision.escalation.baseline_action == RecommendedActionType.MONITOR

    def test_medium_risk_requires_maintenance_escalates_to_repair(
        self, engine: RecommendationEngine
    ) -> None:
        """MEDIUM risk + requires_maintenance=True must escalate to REPAIR."""
        inp = _recommendation_input(
            risk_level=RiskLevel.MEDIUM,
            degradation_report=_degradation_report(requires_maintenance=True),
        )
        decision = engine.decide(inp)

        assert decision.recommended_action == RecommendedActionType.REPAIR
        assert decision.escalation.degradation_escalation_applied is True

    def test_high_risk_requires_maintenance_no_further_escalation(
        self, engine: RecommendationEngine
    ) -> None:
        """HIGH risk baseline = REPAIR; requires_maintenance doesn't raise further."""
        inp = _recommendation_input(
            risk_level=RiskLevel.HIGH,
            degradation_report=_degradation_report(requires_maintenance=True),
        )
        decision = engine.decide(inp)

        # Already at REPAIR — degradation stage shouldn't apply flag.
        assert decision.recommended_action == RecommendedActionType.REPAIR
        assert decision.escalation.degradation_escalation_applied is False

    def test_requires_maintenance_false_no_escalation(
        self, engine: RecommendationEngine
    ) -> None:
        """requires_maintenance=False must not trigger Stage 2 escalation."""
        inp = _recommendation_input(
            risk_level=RiskLevel.LOW,
            degradation_report=_degradation_report(requires_maintenance=False),
        )
        decision = engine.decide(inp)

        assert decision.recommended_action == RecommendedActionType.MONITOR
        assert decision.escalation.degradation_escalation_applied is False

    def test_escalation_interval_from_final_action(
        self, engine: RecommendationEngine
    ) -> None:
        """Interval is from the final escalated action (REPAIR), not baseline (MONITOR)."""
        inp = _recommendation_input(
            risk_level=RiskLevel.LOW,
            degradation_report=_degradation_report(requires_maintenance=True),
        )
        decision = engine.decide(inp)

        assert decision.next_inspection_interval_years == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Stage 3 escalation: real, unmocked integration test
# ---------------------------------------------------------------------------


class TestFailureModeEscalation:
    """
    REAL, UNMOCKED integration tests for Stage 3 failure-mode escalation.

    StructuralFailureMode and HealthAssessmentReport built with real Pydantic
    models — no mocking.
    """

    def test_low_risk_with_escalating_failure_mode_goes_to_emergency(
        self, engine: RecommendationEngine
    ) -> None:
        """
        LOW risk, no degradation escalation, but a failure_mode in the
        escalation set at sufficient confidence → EMERGENCY_INTERVENTION.
        """
        failure_modes = [
            StructuralFailureMode(
                category=FailureModeCategory.PUNCHING_SHEAR,
                description="Punching shear risk detected.",
                confidence=0.85,  # above 0.70 threshold
            )
        ]
        inp = _recommendation_input(
            risk_level=RiskLevel.LOW,
            degradation_report=None,
            failure_modes=failure_modes,
        )
        decision = engine.decide(inp)

        assert decision.recommended_action == RecommendedActionType.EMERGENCY_INTERVENTION
        assert decision.escalation.failure_mode_escalation_applied is True
        assert FailureModeCategory.PUNCHING_SHEAR in decision.escalation.triggering_failure_modes

    def test_triggering_failure_modes_populated(
        self, engine: RecommendationEngine
    ) -> None:
        """triggering_failure_modes list contains the mode that fired."""
        failure_modes = [
            StructuralFailureMode(
                category=FailureModeCategory.COMPRESSION_BUCKLING,
                description="Compression buckling risk.",
                confidence=0.90,
            )
        ]
        inp = _recommendation_input(failure_modes=failure_modes)
        decision = engine.decide(inp)

        assert FailureModeCategory.COMPRESSION_BUCKLING in (
            decision.escalation.triggering_failure_modes
        )

    def test_non_escalating_failure_mode_category_no_stage3(
        self, engine: RecommendationEngine
    ) -> None:
        """A failure mode NOT in escalation_trigger_modes does not trigger Stage 3."""
        failure_modes = [
            StructuralFailureMode(
                category=FailureModeCategory.FLEXURAL,  # not in default trigger set
                description="Flexural risk.",
                confidence=0.95,
            )
        ]
        inp = _recommendation_input(
            risk_level=RiskLevel.LOW, failure_modes=failure_modes
        )
        decision = engine.decide(inp)

        assert decision.recommended_action == RecommendedActionType.MONITOR
        assert decision.escalation.failure_mode_escalation_applied is False

    def test_low_confidence_escalating_mode_does_not_trigger(
        self, engine: RecommendationEngine
    ) -> None:
        """A matching category below confidence_threshold does NOT escalate."""
        failure_modes = [
            StructuralFailureMode(
                category=FailureModeCategory.PUNCHING_SHEAR,
                description="Low confidence punching shear.",
                confidence=0.50,  # below 0.70 threshold
            )
        ]
        inp = _recommendation_input(
            risk_level=RiskLevel.LOW, failure_modes=failure_modes
        )
        decision = engine.decide(inp)

        assert decision.recommended_action == RecommendedActionType.MONITOR
        assert decision.escalation.failure_mode_escalation_applied is False

    def test_stage3_interval_from_emergency_action(
        self, engine: RecommendationEngine
    ) -> None:
        """When Stage 3 escalates to EMERGENCY, interval is 0.1 years."""
        failure_modes = [
            StructuralFailureMode(
                category=FailureModeCategory.PUNCHING_SHEAR,
                description="High-confidence punching shear.",
                confidence=0.80,
            )
        ]
        inp = _recommendation_input(failure_modes=failure_modes)
        decision = engine.decide(inp)

        assert decision.next_inspection_interval_years == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# Monotonicity
# ---------------------------------------------------------------------------


class TestMonotonicity:
    """
    Escalation can only raise the action, never lower it.

    Parametrized over all risk levels and all escalation combinations.
    """

    @pytest.mark.parametrize("risk_level", list(RiskLevel))
    @pytest.mark.parametrize("requires_maintenance", [True, False])
    def test_degradation_escalation_never_lowers_action(
        self,
        engine: RecommendationEngine,
        risk_level: RiskLevel,
        requires_maintenance: bool,
    ) -> None:
        baseline_inp = _recommendation_input(
            risk_level=risk_level, degradation_report=None
        )
        baseline_decision = engine.decide(baseline_inp)

        escalated_inp = _recommendation_input(
            risk_level=risk_level,
            degradation_report=_degradation_report(requires_maintenance),
        )
        escalated_decision = engine.decide(escalated_inp)

        from recommendation.engine import _ACTION_RANK

        assert _ACTION_RANK[escalated_decision.recommended_action] >= _ACTION_RANK[
            baseline_decision.recommended_action
        ]

    @pytest.mark.parametrize("risk_level", list(RiskLevel))
    def test_failure_mode_escalation_never_lowers_action(
        self,
        engine: RecommendationEngine,
        risk_level: RiskLevel,
    ) -> None:
        baseline_inp = _recommendation_input(risk_level=risk_level)
        baseline_decision = engine.decide(baseline_inp)

        failure_modes = [
            StructuralFailureMode(
                category=FailureModeCategory.PUNCHING_SHEAR,
                description="High-confidence punching shear.",
                confidence=0.99,
            )
        ]
        escalated_inp = _recommendation_input(
            risk_level=risk_level, failure_modes=failure_modes
        )
        escalated_decision = engine.decide(escalated_inp)

        from recommendation.engine import _ACTION_RANK

        assert _ACTION_RANK[escalated_decision.recommended_action] >= _ACTION_RANK[
            baseline_decision.recommended_action
        ]


# ---------------------------------------------------------------------------
# Structural decoupling test (enforcement test for the hard constraint)
# ---------------------------------------------------------------------------


class TestStructuralDecoupling:
    """
    Enforce the architectural constraint: RecommendationDecision must have
    no field with 'cost' in its name.

    This is a schema-level structural test — it verifies the design contract
    by inspecting the Pydantic field set, not just engine behavior.
    """

    def test_recommendation_decision_has_no_cost_field(self) -> None:
        """
        RecommendationDecision's Pydantic field set must contain no key
        with 'cost' in its name.  This is the enforcement test for the
        engine/cost separation architectural constraint.
        """
        field_names = set(RecommendationDecision.model_fields.keys())
        cost_fields = {name for name in field_names if "cost" in name.lower()}
        assert cost_fields == set(), (
            f"RecommendationDecision must not contain cost-related fields, "
            f"but found: {cost_fields!r}.  Cost data belongs on CostEstimate only."
        )

    def test_engine_py_does_not_import_cost_estimator(self) -> None:
        """
        Verify at the source level that engine.py has no import of cost_estimator.

        Checks only executable import statements (lines starting with
        'import ' or 'from ') — not docstring mentions.  This catches
        accidental imports even if test isolation would otherwise mask
        the violation.
        """
        import pathlib
        import re

        engine_path = pathlib.Path(__file__).parent.parent.parent / "recommendation" / "engine.py"
        source = engine_path.read_text(encoding="utf-8")
        # Match any line that is a Python import statement referencing cost_estimator.
        import_lines = [
            line.strip()
            for line in source.splitlines()
            if re.match(r"^\s*(import|from)\s+.*cost_estimator", line)
        ]
        assert import_lines == [], (
            f"engine.py must not contain import statements for cost_estimator — "
            f"only recommendation_service.py is allowed to import both. "
            f"Found: {import_lines!r}"
        )


# ---------------------------------------------------------------------------
# Config override
# ---------------------------------------------------------------------------


class TestConfigOverride:
    """Custom config produces correct output without touching default tables."""

    def test_custom_rules_applied(self) -> None:
        """A custom LOW rule maps to REPAIR/1.5yr."""
        from intelligence.schemas import RiskLevel

        custom_rules = {
            RiskLevel.LOW: RecommendationRule(
                action=RecommendedActionType.REPAIR,
                next_inspection_interval_years=1.5,
            ),
            RiskLevel.MEDIUM: RecommendationRule(
                action=RecommendedActionType.REPAIR,
                next_inspection_interval_years=1.0,
            ),
            RiskLevel.HIGH: RecommendationRule(
                action=RecommendedActionType.EMERGENCY_INTERVENTION,
                next_inspection_interval_years=0.25,
            ),
            RiskLevel.CRITICAL: RecommendationRule(
                action=RecommendedActionType.EMERGENCY_INTERVENTION,
                next_inspection_interval_years=0.05,
            ),
        }
        config = RecommendationEngineConfig(rules=custom_rules)
        engine = RecommendationEngine(config=config)
        inp = _recommendation_input(risk_level=RiskLevel.LOW)
        decision = engine.decide(inp)

        assert decision.recommended_action == RecommendedActionType.REPAIR
        assert decision.next_inspection_interval_years == pytest.approx(1.5)

    def test_custom_failure_mode_escalation_threshold(self) -> None:
        """Lower confidence_threshold triggers escalation at lower confidence."""
        custom_fm_config = FailureModeEscalationConfig(
            escalation_trigger_modes=frozenset({FailureModeCategory.FLEXURAL}),
            confidence_threshold=0.40,
        )
        config = RecommendationEngineConfig(failure_mode_escalation=custom_fm_config)
        engine = RecommendationEngine(config=config)

        failure_modes = [
            StructuralFailureMode(
                category=FailureModeCategory.FLEXURAL,
                description="Flexural risk.",
                confidence=0.50,  # above new 0.40 threshold
            )
        ]
        inp = _recommendation_input(failure_modes=failure_modes)
        decision = engine.decide(inp)

        assert decision.recommended_action == RecommendedActionType.EMERGENCY_INTERVENTION
        assert decision.escalation.failure_mode_escalation_applied is True


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Identical inputs always produce identical outputs."""

    @pytest.mark.parametrize("risk_level", list(RiskLevel))
    def test_deterministic_output(
        self, engine: RecommendationEngine, risk_level: RiskLevel
    ) -> None:
        inp = _recommendation_input(risk_level=risk_level)
        d1 = engine.decide(inp)
        d2 = engine.decide(inp)

        assert d1.recommended_action == d2.recommended_action
        assert d1.next_inspection_interval_years == d2.next_inspection_interval_years
        assert d1.escalation == d2.escalation
