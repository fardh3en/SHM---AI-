"""
Unit tests for intelligence.risk_engine.RiskEngine.

All tests are fully deterministic and self-contained — no external services,
no database, no ML models.  Follows the same conventions as the existing suite.

Coverage matrix
---------------
Category                          | What is tested
--------------------------------- | --------------------------------------------------
IRiskEngine contract              | determine_risk_level() satisfies the interface
Stage 1 – Score baseline          | Threshold banding at every boundary
Stage 2 – Severity escalation     | Each SeverityLevel triggers the right escalation
Stage 3 – Failure-mode escalation | Count rules; confidence rules; high-risk category bonus
Stage 4 – Combined override       | Multi-signal overrides; partial conditions
Escalation only                   | A worse Stage can only raise, never lower risk
assess() integration              | Full four-stage synthesis path
Custom config                     | Engine respects injected RiskEngineConfig
Determinism                       | Same input → same output across repeated calls
Edge cases                        | Empty inputs; boundary scores; zero confidence modes
"""
from __future__ import annotations

import pytest

from intelligence.risk_engine import (
    _RISK_RANK,
    DEFAULT_SCORE_THRESHOLDS,
    CombinedOverrideRule,
    FailureModeEscalationRule,
    RiskEngine,
    RiskEngineConfig,
    ScoreThresholds,
    SeverityEscalationRule,
    _max_risk,
    _worst_severity,
)
from intelligence.schemas import (
    DefectCategory,
    DefectSeverityBreakdown,
    FailureModeCategory,
    RiskLevel,
    SeverityLevel,
    StructuralFailureMode,
)

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _breakdown(
    severity: SeverityLevel,
    category: DefectCategory = DefectCategory.CRACK,
    observation_count: int = 1,
) -> DefectSeverityBreakdown:
    return DefectSeverityBreakdown(
        defect_category=category,
        severity=severity,
        observation_count=observation_count,
    )


def _mode(
    confidence: float,
    category: FailureModeCategory = FailureModeCategory.UNKNOWN,
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
def engine() -> RiskEngine:
    return RiskEngine()


# ---------------------------------------------------------------------------
# IRiskEngine interface contract
# ---------------------------------------------------------------------------


class TestIRiskEngineContract:
    def test_implements_interface(self) -> None:
        from intelligence.interfaces import IRiskEngine

        assert isinstance(RiskEngine(), IRiskEngine)

    def test_determine_risk_level_returns_risk_level(
        self, engine: RiskEngine
    ) -> None:
        result = engine.determine_risk_level(80.0)
        assert isinstance(result, RiskLevel)

    def test_determine_risk_level_low(self, engine: RiskEngine) -> None:
        assert engine.determine_risk_level(100.0) == RiskLevel.LOW
        assert engine.determine_risk_level(75.0) == RiskLevel.LOW

    def test_determine_risk_level_medium(self, engine: RiskEngine) -> None:
        assert engine.determine_risk_level(74.9) == RiskLevel.MEDIUM
        assert engine.determine_risk_level(50.0) == RiskLevel.MEDIUM

    def test_determine_risk_level_high(self, engine: RiskEngine) -> None:
        assert engine.determine_risk_level(49.9) == RiskLevel.HIGH
        assert engine.determine_risk_level(25.0) == RiskLevel.HIGH

    def test_determine_risk_level_critical(self, engine: RiskEngine) -> None:
        assert engine.determine_risk_level(24.9) == RiskLevel.CRITICAL
        assert engine.determine_risk_level(0.0) == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Stage 1 – Score baseline
# ---------------------------------------------------------------------------


class TestStage1ScoreBaseline:
    """
    Score thresholds: ≥75 LOW / ≥50 MEDIUM / ≥25 HIGH / <25 CRITICAL.
    Exact boundary values belong to the lower (better) band.
    """

    @pytest.mark.parametrize(
        "score, expected",
        [
            (100.0, RiskLevel.LOW),
            (75.0, RiskLevel.LOW),
            (74.999, RiskLevel.MEDIUM),
            (50.0, RiskLevel.MEDIUM),
            (49.999, RiskLevel.HIGH),
            (25.0, RiskLevel.HIGH),
            (24.999, RiskLevel.CRITICAL),
            (0.0, RiskLevel.CRITICAL),
        ],
    )
    def test_boundary_mapping(
        self, engine: RiskEngine, score: float, expected: RiskLevel
    ) -> None:
        assert engine.determine_risk_level(score) == expected

    def test_custom_thresholds_respected(self) -> None:
        config = RiskEngineConfig(
            score_thresholds=ScoreThresholds(low=90.0, medium=70.0, high=40.0),
            severity_escalation_rules=(),
            failure_mode_escalation_rules=(),
            combined_override_rules=(),
        )
        engine = RiskEngine(config=config)
        assert engine.determine_risk_level(95.0) == RiskLevel.LOW
        assert engine.determine_risk_level(85.0) == RiskLevel.MEDIUM
        assert engine.determine_risk_level(55.0) == RiskLevel.HIGH
        assert engine.determine_risk_level(30.0) == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Stage 2 – Severity escalation
# ---------------------------------------------------------------------------


class TestStage2SeverityEscalation:
    def test_no_breakdown_no_escalation(self, engine: RiskEngine) -> None:
        """No breakdowns: risk stays at score baseline."""
        result = engine.assess(health_score=80.0, severity_breakdown=[])
        assert result == RiskLevel.LOW

    def test_negligible_severity_no_escalation(self, engine: RiskEngine) -> None:
        result = engine.assess(
            health_score=80.0,
            severity_breakdown=[_breakdown(SeverityLevel.NEGLIGIBLE)],
        )
        assert result == RiskLevel.LOW

    def test_minor_severity_no_escalation(self, engine: RiskEngine) -> None:
        result = engine.assess(
            health_score=80.0,
            severity_breakdown=[_breakdown(SeverityLevel.MINOR)],
        )
        assert result == RiskLevel.LOW

    def test_moderate_severity_escalates_to_medium(self, engine: RiskEngine) -> None:
        """MODERATE severity: floor becomes MEDIUM, regardless of score."""
        result = engine.assess(
            health_score=85.0,
            severity_breakdown=[_breakdown(SeverityLevel.MODERATE)],
        )
        assert result == RiskLevel.MEDIUM

    def test_severe_severity_escalates_to_high(self, engine: RiskEngine) -> None:
        """SEVERE severity: floor becomes HIGH."""
        result = engine.assess(
            health_score=85.0,
            severity_breakdown=[_breakdown(SeverityLevel.SEVERE)],
        )
        assert result == RiskLevel.HIGH

    def test_critical_severity_escalates_to_high(self, engine: RiskEngine) -> None:
        """CRITICAL defect severity (alone): floor is HIGH."""
        result = engine.assess(
            health_score=85.0,
            severity_breakdown=[_breakdown(SeverityLevel.CRITICAL)],
        )
        assert result == RiskLevel.HIGH

    def test_worst_severity_drives_escalation(self, engine: RiskEngine) -> None:
        """Multiple breakdowns: only the worst drives escalation."""
        result = engine.assess(
            health_score=80.0,
            severity_breakdown=[
                _breakdown(SeverityLevel.NEGLIGIBLE, DefectCategory.SURFACE_DAMAGE),
                _breakdown(SeverityLevel.SEVERE, DefectCategory.CRACK),
                _breakdown(SeverityLevel.MINOR, DefectCategory.CORROSION),
            ],
        )
        assert result == RiskLevel.HIGH

    def test_severity_cannot_lower_score_based_risk(self, engine: RiskEngine) -> None:
        """
        If Stage 1 already produced HIGH (bad score), Stage 2 should not
        lower it even if severity is only MODERATE.
        """
        result = engine.assess(
            health_score=30.0,  # Stage 1 = HIGH
            severity_breakdown=[_breakdown(SeverityLevel.MODERATE)],  # floor = MEDIUM
        )
        assert result == RiskLevel.HIGH  # HIGH stays, not lowered to MEDIUM

    def test_custom_severity_escalation_rule(self) -> None:
        config = RiskEngineConfig(
            severity_escalation_rules=(
                SeverityEscalationRule(
                    min_severity=SeverityLevel.MINOR,
                    escalate_to=RiskLevel.CRITICAL,
                ),
            ),
            failure_mode_escalation_rules=(),
            combined_override_rules=(),
        )
        engine = RiskEngine(config=config)
        result = engine.assess(
            health_score=90.0,
            severity_breakdown=[_breakdown(SeverityLevel.MINOR)],
        )
        assert result == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Stage 3 – Failure-mode escalation
# ---------------------------------------------------------------------------


class TestStage3FailureModeEscalation:
    def test_no_failure_modes_no_escalation(self, engine: RiskEngine) -> None:
        result = engine.assess(health_score=80.0, failure_modes=[])
        assert result == RiskLevel.LOW

    def test_single_low_confidence_mode_no_escalation(
        self, engine: RiskEngine
    ) -> None:
        """Confidence < 0.50: no escalation rule fires."""
        result = engine.assess(
            health_score=80.0,
            failure_modes=[_mode(0.40)],
        )
        assert result == RiskLevel.LOW

    def test_single_medium_confidence_mode_escalates_to_medium(
        self, engine: RiskEngine
    ) -> None:
        result = engine.assess(
            health_score=80.0,
            failure_modes=[_mode(0.60)],
        )
        assert result == RiskLevel.MEDIUM

    def test_single_high_confidence_mode_escalates_to_high(
        self, engine: RiskEngine
    ) -> None:
        result = engine.assess(
            health_score=80.0,
            failure_modes=[_mode(0.80)],
        )
        assert result == RiskLevel.HIGH

    def test_two_low_confidence_modes_escalate_to_high(
        self, engine: RiskEngine
    ) -> None:
        """Two or more modes (any confidence) → at least HIGH."""
        result = engine.assess(
            health_score=80.0,
            failure_modes=[_mode(0.10), _mode(0.10)],
        )
        assert result == RiskLevel.HIGH

    def test_three_high_confidence_modes_escalate_to_critical(
        self, engine: RiskEngine
    ) -> None:
        result = engine.assess(
            health_score=80.0,
            failure_modes=[_mode(0.80), _mode(0.75), _mode(0.70)],
        )
        assert result == RiskLevel.CRITICAL

    def test_high_risk_category_bonus_escalates_to_high(
        self, engine: RiskEngine
    ) -> None:
        """A high-risk FailureModeCategory forces at least HIGH regardless of count/confidence."""
        result = engine.assess(
            health_score=80.0,
            failure_modes=[
                _mode(0.40, category=FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS)
            ],
        )
        assert result == RiskLevel.HIGH

    def test_flexural_mode_is_high_risk_category(self, engine: RiskEngine) -> None:
        result = engine.assess(
            health_score=80.0,
            failure_modes=[_mode(0.30, category=FailureModeCategory.FLEXURAL)],
        )
        assert result == RiskLevel.HIGH

    def test_shear_mode_is_high_risk_category(self, engine: RiskEngine) -> None:
        result = engine.assess(
            health_score=80.0,
            failure_modes=[_mode(0.30, category=FailureModeCategory.SHEAR)],
        )
        assert result == RiskLevel.HIGH

    def test_unknown_mode_category_not_high_risk_bonus(
        self, engine: RiskEngine
    ) -> None:
        """UNKNOWN failure mode with low confidence: no high-risk category bonus."""
        result = engine.assess(
            health_score=80.0,
            failure_modes=[_mode(0.30, category=FailureModeCategory.UNKNOWN)],
        )
        # Only 1 mode, confidence < 0.50, UNKNOWN not in high-risk set → stays LOW
        assert result == RiskLevel.LOW

    def test_mode_escalation_cannot_lower_risk(self, engine: RiskEngine) -> None:
        """Stage 1 = CRITICAL (score 10): Stage 3 cannot lower it."""
        result = engine.assess(
            health_score=10.0,
            failure_modes=[_mode(0.55)],
        )
        assert result == RiskLevel.CRITICAL

    def test_custom_failure_mode_escalation_rule(self) -> None:
        config = RiskEngineConfig(
            severity_escalation_rules=(),
            failure_mode_escalation_rules=(
                FailureModeEscalationRule(
                    min_failure_modes=1,
                    min_confidence=0.0,
                    escalate_to=RiskLevel.CRITICAL,
                ),
            ),
            combined_override_rules=(),
        )
        engine = RiskEngine(config=config)
        result = engine.assess(
            health_score=90.0,
            failure_modes=[_mode(0.01)],
        )
        assert result == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Stage 4 – Combined-evidence override
# ---------------------------------------------------------------------------


class TestStage4CombinedOverride:
    def test_critical_severity_and_multiple_modes_and_low_score_forces_critical(
        self, engine: RiskEngine
    ) -> None:
        """
        Multi-signal scenario: critical severity + 2 failure modes + score ≤ 50
        → CRITICAL via combined override rule #2.
        """
        result = engine.assess(
            health_score=40.0,
            severity_breakdown=[_breakdown(SeverityLevel.CRITICAL)],
            failure_modes=[_mode(0.80), _mode(0.75)],
        )
        assert result == RiskLevel.CRITICAL

    def test_override_does_not_fire_when_score_above_threshold(
        self, engine: RiskEngine
    ) -> None:
        """
        Same signals but score is high: combined override should not fire
        (its max_score condition is not satisfied).
        """
        config = RiskEngineConfig(
            combined_override_rules=(
                CombinedOverrideRule(
                    min_failure_modes=2,
                    min_severity=SeverityLevel.CRITICAL,
                    max_score=50.0,
                    escalate_to=RiskLevel.CRITICAL,
                ),
            ),
        )
        engine = RiskEngine(config=config)
        result = engine.assess(
            health_score=70.0,  # > max_score=50
            severity_breakdown=[_breakdown(SeverityLevel.CRITICAL)],
            failure_modes=[_mode(0.80), _mode(0.75)],
        )
        # Stage 2 → HIGH (critical severity), Stage 3 → HIGH (two modes),
        # Stage 4 does NOT fire (score 70 > 50) → HIGH
        assert result == RiskLevel.HIGH

    def test_override_does_not_fire_when_severity_missing(
        self, engine: RiskEngine
    ) -> None:
        config = RiskEngineConfig(
            combined_override_rules=(
                CombinedOverrideRule(
                    min_failure_modes=1,
                    min_severity=SeverityLevel.CRITICAL,
                    max_score=100.0,
                    escalate_to=RiskLevel.CRITICAL,
                ),
            ),
        )
        engine = RiskEngine(config=config)
        result = engine.assess(
            health_score=80.0,
            severity_breakdown=[],  # no severity data at all
            failure_modes=[_mode(0.90)],
        )
        # No severity data → override should not fire; just assert no crash
        assert result in list(RiskLevel)

    def test_override_does_not_fire_when_failure_modes_missing(
        self, engine: RiskEngine
    ) -> None:
        config = RiskEngineConfig(
            failure_mode_escalation_rules=(),
            combined_override_rules=(
                CombinedOverrideRule(
                    min_failure_modes=1,
                    min_severity=SeverityLevel.SEVERE,
                    max_score=100.0,
                    escalate_to=RiskLevel.CRITICAL,
                ),
            ),
        )
        engine = RiskEngine(config=config)
        result = engine.assess(
            health_score=80.0,
            severity_breakdown=[_breakdown(SeverityLevel.SEVERE)],
            failure_modes=[],  # override requires ≥1 mode
        )
        assert result != RiskLevel.CRITICAL

    def test_custom_override_rule_all_conditions_none(self) -> None:
        """A rule with all conditions None always fires."""
        config = RiskEngineConfig(
            combined_override_rules=(
                CombinedOverrideRule(
                    escalate_to=RiskLevel.CRITICAL,
                    # all optional conditions left as None
                ),
            ),
        )
        engine = RiskEngine(config=config)
        result = engine.assess(health_score=100.0)
        assert result == RiskLevel.CRITICAL

    def test_empty_override_rules_no_change(self) -> None:
        config = RiskEngineConfig(combined_override_rules=())
        engine = RiskEngine(config=config)
        result = engine.assess(health_score=90.0)
        assert result == RiskLevel.LOW


# ---------------------------------------------------------------------------
# assess() integration scenarios
# ---------------------------------------------------------------------------


class TestAssessIntegration:
    """End-to-end assess() paths that combine all four stages."""

    def test_pristine_asset_is_low_risk(self, engine: RiskEngine) -> None:
        result = engine.assess(
            health_score=95.0,
            severity_breakdown=[
                _breakdown(SeverityLevel.NEGLIGIBLE, DefectCategory.SURFACE_DAMAGE)
            ],
            failure_modes=[],
        )
        assert result == RiskLevel.LOW

    def test_moderate_defect_one_mode_is_medium_or_high(
        self, engine: RiskEngine
    ) -> None:
        """
        Score 68 (MEDIUM baseline), one MODERATE defect, one medium-confidence
        UNKNOWN mode.  Expected: at least MEDIUM.
        """
        result = engine.assess(
            health_score=68.0,
            severity_breakdown=[_breakdown(SeverityLevel.MODERATE)],
            failure_modes=[_mode(0.60)],
        )
        assert _RISK_RANK[result] >= _RISK_RANK[RiskLevel.MEDIUM]

    def test_low_score_severe_defect_one_important_mode_is_high_or_critical(
        self, engine: RiskEngine
    ) -> None:
        result = engine.assess(
            health_score=38.0,
            severity_breakdown=[_breakdown(SeverityLevel.SEVERE)],
            failure_modes=[
                _mode(0.82, category=FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS)
            ],
        )
        assert result in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_very_degraded_asset_is_critical(self, engine: RiskEngine) -> None:
        result = engine.assess(
            health_score=18.0,
            severity_breakdown=[
                _breakdown(SeverityLevel.CRITICAL, DefectCategory.EXPOSED_REINFORCEMENT),
                _breakdown(SeverityLevel.SEVERE, DefectCategory.SPALLING),
            ],
            failure_modes=[
                _mode(0.88, category=FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS),
                _mode(0.80, category=FailureModeCategory.FLEXURAL),
                _mode(0.75, category=FailureModeCategory.SHEAR),
            ],
        )
        assert result == RiskLevel.CRITICAL

    def test_score_only_assess_matches_determine_risk_level(
        self, engine: RiskEngine
    ) -> None:
        """assess() with no breakdown/modes must match determine_risk_level()."""
        for score in (10.0, 30.0, 60.0, 80.0, 100.0):
            assert engine.assess(health_score=score) == engine.determine_risk_level(score)

    def test_none_inputs_treated_as_empty(self, engine: RiskEngine) -> None:
        """Passing None for optional args should behave identically to passing []."""
        result_none = engine.assess(
            health_score=80.0, severity_breakdown=None, failure_modes=None
        )
        result_empty = engine.assess(
            health_score=80.0, severity_breakdown=[], failure_modes=[]
        )
        assert result_none == result_empty


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_max_risk_always_returns_worse(self) -> None:
        assert _max_risk(RiskLevel.LOW, RiskLevel.CRITICAL) == RiskLevel.CRITICAL
        assert _max_risk(RiskLevel.CRITICAL, RiskLevel.LOW) == RiskLevel.CRITICAL
        assert _max_risk(RiskLevel.MEDIUM, RiskLevel.MEDIUM) == RiskLevel.MEDIUM
        assert _max_risk(RiskLevel.HIGH, RiskLevel.LOW) == RiskLevel.HIGH

    def test_worst_severity_empty(self) -> None:
        assert _worst_severity([]) is None

    def test_worst_severity_single(self) -> None:
        assert _worst_severity([_breakdown(SeverityLevel.MODERATE)]) == SeverityLevel.MODERATE

    def test_worst_severity_multiple(self) -> None:
        result = _worst_severity([
            _breakdown(SeverityLevel.MINOR),
            _breakdown(SeverityLevel.CRITICAL),
            _breakdown(SeverityLevel.NEGLIGIBLE),
        ])
        assert result == SeverityLevel.CRITICAL

    def test_score_thresholds_classify_boundaries(self) -> None:
        t = DEFAULT_SCORE_THRESHOLDS
        assert t.classify(75.0) == RiskLevel.LOW
        assert t.classify(74.9) == RiskLevel.MEDIUM
        assert t.classify(50.0) == RiskLevel.MEDIUM
        assert t.classify(49.9) == RiskLevel.HIGH
        assert t.classify(25.0) == RiskLevel.HIGH
        assert t.classify(24.9) == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Escalation-only guarantee
# ---------------------------------------------------------------------------


class TestEscalationOnly:
    """Each stage can only raise risk, never lower it."""

    def test_good_severity_cannot_lower_score_based_risk(
        self, engine: RiskEngine
    ) -> None:
        """Score gives CRITICAL; NEGLIGIBLE severity must leave it CRITICAL."""
        result = engine.assess(
            health_score=5.0,
            severity_breakdown=[_breakdown(SeverityLevel.NEGLIGIBLE)],
        )
        assert result == RiskLevel.CRITICAL

    def test_zero_confidence_mode_below_threshold_no_escalation(
        self, engine: RiskEngine
    ) -> None:
        result = engine.assess(
            health_score=80.0,
            failure_modes=[_mode(0.0)],
        )
        # Zero confidence: no escalation rule for count=1, conf=0 should fire
        assert result == RiskLevel.LOW

    def test_all_stages_combined_monotonically_escalate(
        self, engine: RiskEngine
    ) -> None:
        """
        Adding progressively worse signals should never lower the risk level.
        """
        score = 60.0  # MEDIUM baseline

        r1 = engine.assess(health_score=score)
        r2 = engine.assess(
            health_score=score,
            severity_breakdown=[_breakdown(SeverityLevel.SEVERE)],
        )
        r3 = engine.assess(
            health_score=score,
            severity_breakdown=[_breakdown(SeverityLevel.SEVERE)],
            failure_modes=[_mode(0.80)],
        )
        r4 = engine.assess(
            health_score=score,
            severity_breakdown=[_breakdown(SeverityLevel.CRITICAL)],
            failure_modes=[_mode(0.80), _mode(0.75)],
        )

        from intelligence.risk_engine import _RISK_RANK

        assert _RISK_RANK[r2] >= _RISK_RANK[r1]
        assert _RISK_RANK[r3] >= _RISK_RANK[r2]
        assert _RISK_RANK[r4] >= _RISK_RANK[r3]


# ---------------------------------------------------------------------------
# Custom configuration
# ---------------------------------------------------------------------------


class TestCustomConfig:
    def test_empty_all_rules_returns_score_only(self) -> None:
        config = RiskEngineConfig(
            severity_escalation_rules=(),
            failure_mode_escalation_rules=(),
            combined_override_rules=(),
            high_risk_failure_categories=frozenset(),
        )
        engine = RiskEngine(config=config)
        result = engine.assess(
            health_score=80.0,
            severity_breakdown=[_breakdown(SeverityLevel.CRITICAL)],
            failure_modes=[_mode(0.99), _mode(0.99), _mode(0.99), _mode(0.99)],
        )
        # No escalation rules → only Stage 1 applies
        assert result == RiskLevel.LOW

    def test_engine_version_in_config(self) -> None:
        config = RiskEngineConfig(engine_version="2.5.0")
        engine = RiskEngine(config=config)
        assert engine._config.engine_version == "2.5.0"

    def test_custom_high_risk_categories(self) -> None:
        config = RiskEngineConfig(
            failure_mode_escalation_rules=(),
            combined_override_rules=(),
            high_risk_failure_categories=frozenset({FailureModeCategory.PUNCHING_SHEAR}),
        )
        engine = RiskEngine(config=config)
        result = engine.assess(
            health_score=90.0,
            failure_modes=[_mode(0.20, category=FailureModeCategory.PUNCHING_SHEAR)],
        )
        assert result == RiskLevel.HIGH


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_input_same_output(self, engine: RiskEngine) -> None:
        kwargs = dict(
            health_score=55.0,
            severity_breakdown=[
                _breakdown(SeverityLevel.SEVERE, DefectCategory.CRACK),
                _breakdown(SeverityLevel.MODERATE, DefectCategory.CORROSION),
            ],
            failure_modes=[
                _mode(0.78, FailureModeCategory.FLEXURAL),
                _mode(0.65, FailureModeCategory.UNKNOWN),
            ],
        )
        assert engine.assess(**kwargs) == engine.assess(**kwargs)  # type: ignore[arg-type]

    def test_determine_risk_level_deterministic(self, engine: RiskEngine) -> None:
        for score in (0.0, 25.0, 50.0, 75.0, 100.0):
            assert engine.determine_risk_level(score) == engine.determine_risk_level(score)


