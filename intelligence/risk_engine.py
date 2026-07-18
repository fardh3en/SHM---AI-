"""
Risk Engine.

Deterministic, configuration-driven implementation of IRiskEngine.  Produces
a discrete RiskLevel from intelligence already computed by the rest of the
Phase 3 layer — no machine learning, no LLMs, no re-scoring, no re-classifying.

Interface contract
------------------
IRiskEngine.determine_risk_level(health_score: float) -> RiskLevel

The abstract interface accepts only a health score.  This is the single
mandatory entry-point and is satisfied exactly as defined in interfaces.py.
No changes are made to interfaces.py or schemas.py.

Extended synthesis (convenience method)
----------------------------------------
The ``assess()`` convenience method accepts the full intelligence outputs
(health score + severity breakdown + failure modes) and synthesises them into
one RiskLevel.  This is NOT part of the abstract interface; it is a concrete
addition on this class following the same pattern as HealthScorer.assess().

When only a health score is available, call ``determine_risk_level()``.
When the richer outputs are available, call ``assess()`` to get a RiskLevel
that reflects the complete picture.

Assessment strategy
-------------------
Risk is computed in four ordered stages, each of which can only raise (never
lower) the risk level:

  Stage 1 – Score baseline
    The health score is mapped to an initial RiskLevel using configurable
    threshold bands (default: ≥75 LOW, ≥50 MEDIUM, ≥25 HIGH, <25 CRITICAL).
    This exactly matches the bands used by HealthScorer._score_to_risk_level(),
    but the constants are not imported from there — the two modules are
    intentionally independent.

  Stage 2 – Severity escalation
    The severity breakdown is scanned for the worst SeverityLevel present.
    Pre-configured escalation rules lift the current risk level when a
    sufficiently severe defect category is observed.  For example, a single
    CRITICAL defect always escalates to at least HIGH risk; SEVERE defects
    escalate to at least MEDIUM risk.

  Stage 3 – Failure-mode escalation
    The failure mode list is inspected for count and maximum confidence.
    Rules lift risk level based on number of active failure modes and the
    combined weight of their evidence.  For example, two or more high-confidence
    failure modes always escalate to at least HIGH; a single high-confidence
    failure mode escalates to at least MEDIUM.

  Stage 4 – Combined evidence override
    A separate set of override rules can force CRITICAL or HIGH risk when
    multiple aggravating signals coincide (e.g. failure modes present AND
    CRITICAL-severity defects AND score below a threshold), catching edge cases
    where each individual stage alone would underestimate the overall risk.

Escalation only: each stage can only raise the level, never lower it.
This is conservative by design — when in doubt, escalate.

NOTE: all thresholds and escalation rules are configurable via
RiskEngineConfig.  The defaults are reasonable engineering starting points,
not values derived from a specific standard or code.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from intelligence.interfaces import IRiskEngine
from intelligence.schemas import (
    DefectSeverityBreakdown,
    FailureModeCategory,
    RiskLevel,
    SeverityLevel,
    StructuralFailureMode,
)

# ---------------------------------------------------------------------------
# Risk-level ordering helpers
# ---------------------------------------------------------------------------

# Integer rank for each RiskLevel (higher = worse).  Used to enforce
# "escalation only" without hard-coding comparison chains.
_RISK_RANK: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}

_RANK_TO_RISK: dict[int, RiskLevel] = {v: k for k, v in _RISK_RANK.items()}


def _max_risk(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    """Return whichever RiskLevel is higher (or equal)."""
    return _RANK_TO_RISK[max(_RISK_RANK[a], _RISK_RANK[b])]


# ---------------------------------------------------------------------------
# Configuration data-classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoreThresholds:
    """
    Health-score boundaries that map to each RiskLevel (Stage 1).

    A score >= ``low`` is LOW.
    A score >= ``medium`` (but < ``low``) is MEDIUM.
    A score >= ``high`` (but < ``medium``) is HIGH.
    A score < ``high`` is CRITICAL.

    All values must satisfy: 100 >= low > medium > high >= 0.
    """

    low: float = 75.0
    medium: float = 50.0
    high: float = 25.0

    def classify(self, score: float) -> RiskLevel:
        """Map a health score to its baseline RiskLevel."""
        if score >= self.low:
            return RiskLevel.LOW
        if score >= self.medium:
            return RiskLevel.MEDIUM
        if score >= self.high:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL


@dataclass(frozen=True)
class SeverityEscalationRule:
    """
    A single severity-based escalation rule (Stage 2).

    When the worst observed SeverityLevel is >= ``min_severity``, the risk
    level is raised to at least ``escalate_to``.

    Attributes:
        min_severity: Minimum SeverityLevel that triggers this rule.
        escalate_to: The minimum RiskLevel to enforce when triggered.
    """

    min_severity: SeverityLevel
    escalate_to: RiskLevel


@dataclass(frozen=True)
class FailureModeEscalationRule:
    """
    A single failure-mode-based escalation rule (Stage 3).

    When the number of detected failure modes >= ``min_failure_modes`` AND
    the maximum confidence across those modes >= ``min_confidence``, the risk
    level is raised to at least ``escalate_to``.

    Attributes:
        min_failure_modes: Minimum number of failure modes required.
        min_confidence: Minimum confidence of any single mode required.
        escalate_to: The minimum RiskLevel to enforce when triggered.
    """

    min_failure_modes: int
    min_confidence: float
    escalate_to: RiskLevel


@dataclass(frozen=True)
class CombinedOverrideRule:
    """
    A combined-evidence override rule (Stage 4).

    Fires when ALL of:
      - failure mode count >= ``min_failure_modes``
      - worst severity >= ``min_severity``
      - health score <= ``max_score``

    When all conditions hold, the risk is raised to at least ``escalate_to``.
    This catches scenarios where each individual stage would underestimate risk
    due to thresholds not quite being exceeded individually.

    A field value of None means that condition is not checked.

    Attributes:
        min_failure_modes: Required failure mode count (None = not checked).
        min_severity: Required minimum severity (None = not checked).
        max_score: Required maximum health score (None = not checked).
        escalate_to: The minimum RiskLevel to enforce when triggered.
    """

    escalate_to: RiskLevel
    min_failure_modes: int | None = None
    min_severity: SeverityLevel | None = None
    max_score: float | None = None


# ── Severity ordering ────────────────────────────────────────────────────────

_SEVERITY_RANK: dict[SeverityLevel, int] = {
    SeverityLevel.NEGLIGIBLE: 0,
    SeverityLevel.MINOR: 1,
    SeverityLevel.MODERATE: 2,
    SeverityLevel.SEVERE: 3,
    SeverityLevel.CRITICAL: 4,
}


def _worst_severity(
    breakdowns: list[DefectSeverityBreakdown],
) -> SeverityLevel | None:
    """Return the highest SeverityLevel found in a severity breakdown list."""
    if not breakdowns:
        return None
    return max(breakdowns, key=lambda b: _SEVERITY_RANK[b.severity]).severity


def _severity_gte(a: SeverityLevel, b: SeverityLevel) -> bool:
    """True if severity a is greater than or equal to severity b."""
    return _SEVERITY_RANK[a] >= _SEVERITY_RANK[b]


# ---------------------------------------------------------------------------
# Default escalation tables
# ---------------------------------------------------------------------------

# NOTE: ordered from weakest to strongest so they can all be evaluated; the
# _max_risk() combinator ensures only genuine escalation occurs.

DEFAULT_SCORE_THRESHOLDS = ScoreThresholds(low=75.0, medium=50.0, high=25.0)

DEFAULT_SEVERITY_ESCALATION_RULES: tuple[SeverityEscalationRule, ...] = (
    # A MODERATE defect lifts the floor to at least MEDIUM risk.
    SeverityEscalationRule(
        min_severity=SeverityLevel.MODERATE,
        escalate_to=RiskLevel.MEDIUM,
    ),
    # A SEVERE defect lifts the floor to at least HIGH risk.
    SeverityEscalationRule(
        min_severity=SeverityLevel.SEVERE,
        escalate_to=RiskLevel.HIGH,
    ),
    # A CRITICAL defect always forces at least HIGH risk (not CRITICAL by
    # itself — a single critical defect with a good overall score may still
    # be HIGH rather than CRITICAL).
    SeverityEscalationRule(
        min_severity=SeverityLevel.CRITICAL,
        escalate_to=RiskLevel.HIGH,
    ),
)

DEFAULT_FAILURE_MODE_ESCALATION_RULES: tuple[FailureModeEscalationRule, ...] = (
    # Any single failure mode with meaningful confidence lifts to at least MEDIUM.
    FailureModeEscalationRule(
        min_failure_modes=1,
        min_confidence=0.50,
        escalate_to=RiskLevel.MEDIUM,
    ),
    # A high-confidence failure mode lifts to at least HIGH.
    FailureModeEscalationRule(
        min_failure_modes=1,
        min_confidence=0.75,
        escalate_to=RiskLevel.HIGH,
    ),
    # Two or more failure modes of any confidence lifts to at least HIGH.
    FailureModeEscalationRule(
        min_failure_modes=2,
        min_confidence=0.0,
        escalate_to=RiskLevel.HIGH,
    ),
    # Three or more failure modes with high overall confidence forces CRITICAL.
    FailureModeEscalationRule(
        min_failure_modes=3,
        min_confidence=0.65,
        escalate_to=RiskLevel.CRITICAL,
    ),
)

# High-risk failure-mode categories that carry extra structural significance.
# When any of these categories is detected, an additional escalation applies.
HIGH_RISK_FAILURE_CATEGORIES: frozenset[FailureModeCategory] = frozenset({
    FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS,
    FailureModeCategory.FLEXURAL,
    FailureModeCategory.SHEAR,
    FailureModeCategory.COMPRESSION_BUCKLING,
})

DEFAULT_COMBINED_OVERRIDE_RULES: tuple[CombinedOverrideRule, ...] = (
    # CRITICAL defects + any failure mode + degraded score → HIGH.
    CombinedOverrideRule(
        min_failure_modes=1,
        min_severity=SeverityLevel.CRITICAL,
        max_score=60.0,
        escalate_to=RiskLevel.HIGH,
    ),
    # CRITICAL defects + multiple failure modes + poor score → CRITICAL.
    CombinedOverrideRule(
        min_failure_modes=2,
        min_severity=SeverityLevel.CRITICAL,
        max_score=50.0,
        escalate_to=RiskLevel.CRITICAL,
    ),
    # Many failure modes + SEVERE defects + poor score → CRITICAL.
    CombinedOverrideRule(
        min_failure_modes=3,
        min_severity=SeverityLevel.SEVERE,
        max_score=40.0,
        escalate_to=RiskLevel.CRITICAL,
    ),
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskEngineConfig:
    """
    Full configuration for a RiskEngine instance.

    Every escalation threshold is exposed here so the engine can be retuned
    without code changes — just supply a custom config.

    Attributes:
        score_thresholds: Stage 1 health-score-to-RiskLevel banding.
        severity_escalation_rules: Stage 2 severity-based escalation rules,
            evaluated in order. All matching rules are applied (escalation only).
        failure_mode_escalation_rules: Stage 3 failure-mode-based escalation
            rules, evaluated in order.
        combined_override_rules: Stage 4 combined-evidence override rules.
        high_risk_failure_categories: FailureModeCategories that carry an
            extra escalation when detected (raises to HIGH independently).
        engine_version: Recorded in assessment metadata for traceability.
    """

    score_thresholds: ScoreThresholds = field(
        default_factory=lambda: DEFAULT_SCORE_THRESHOLDS
    )
    severity_escalation_rules: tuple[SeverityEscalationRule, ...] = field(
        default_factory=lambda: DEFAULT_SEVERITY_ESCALATION_RULES
    )
    failure_mode_escalation_rules: tuple[FailureModeEscalationRule, ...] = field(
        default_factory=lambda: DEFAULT_FAILURE_MODE_ESCALATION_RULES
    )
    combined_override_rules: tuple[CombinedOverrideRule, ...] = field(
        default_factory=lambda: DEFAULT_COMBINED_OVERRIDE_RULES
    )
    high_risk_failure_categories: frozenset[FailureModeCategory] = field(
        default_factory=lambda: HIGH_RISK_FAILURE_CATEGORIES
    )
    engine_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RiskEngine(IRiskEngine):
    """
    Deterministic, configurable implementation of IRiskEngine.

    See module docstring for the four-stage assessment strategy and the
    explicit scope boundary (no re-scoring, no re-classifying, no
    re-identifying failure modes).

    Usage — interface contract only::

        engine = RiskEngine()
        risk = engine.determine_risk_level(health_score=72.4)

    Usage — full intelligence synthesis::

        engine = RiskEngine()
        risk = engine.assess(
            health_score=42.0,
            severity_breakdown=classifier.classify(assessment_input),
            failure_modes=rules_engine.identify_failure_modes(assessment_input),
        )

    To customise thresholds, supply a RiskEngineConfig::

        config = RiskEngineConfig(
            score_thresholds=ScoreThresholds(low=80.0, medium=55.0, high=30.0),
            engine_version="2.0.0",
        )
        engine = RiskEngine(config=config)
    """

    def __init__(self, config: RiskEngineConfig | None = None) -> None:
        self._config = config or RiskEngineConfig()

    # ── IRiskEngine contract ────────────────────────────────────────────────

    def determine_risk_level(self, health_score: float) -> RiskLevel:
        """
        Map a composite health score to a discrete RiskLevel.

        Satisfies the IRiskEngine abstract interface.  Uses Stage 1
        (score threshold banding) only — severity and failure modes are
        not available through this interface.

        Args:
            health_score: Composite health score in [0, 100].

        Returns:
            Corresponding discrete RiskLevel.
        """
        return self._config.score_thresholds.classify(health_score)

    # ── Extended synthesis (convenience method) ─────────────────────────────

    def assess(
        self,
        health_score: float,
        severity_breakdown: list[DefectSeverityBreakdown] | None = None,
        failure_modes: list[StructuralFailureMode] | None = None,
    ) -> RiskLevel:
        """
        Synthesise a RiskLevel from all available intelligence outputs.

        This is NOT part of the IRiskEngine interface.  It is a concrete
        addition that accepts the richer outputs produced by the rest of the
        Phase 3 intelligence layer to produce a more informed assessment.

        Stages applied (each can only raise the risk level):
          1. Score baseline — health score threshold banding.
          2. Severity escalation — worst observed SeverityLevel rules.
          3. Failure-mode escalation — failure mode count and confidence rules.
          4. Combined-evidence override — multi-signal override rules.

        Args:
            health_score: Composite health score in [0, 100], from IHealthScorer.
            severity_breakdown: Per-category severity breakdowns, from
                ISeverityClassifier.  Pass [] or None when unavailable.
            failure_modes: Identified structural failure modes, from
                IEngineeringRulesEngine.  Pass [] or None when unavailable.

        Returns:
            Synthesised RiskLevel reflecting all provided intelligence.
        """
        breakdowns: list[DefectSeverityBreakdown] = severity_breakdown or []
        modes: list[StructuralFailureMode] = failure_modes or []

        # Stage 1: score baseline
        risk = self._stage1_score_baseline(health_score)

        # Stage 2: severity escalation
        risk = self._stage2_severity_escalation(risk, breakdowns)

        # Stage 3: failure-mode escalation
        risk = self._stage3_failure_mode_escalation(risk, modes)

        # Stage 4: combined-evidence override
        risk = self._stage4_combined_override(risk, health_score, breakdowns, modes)

        return risk

    # ── Stage implementations ───────────────────────────────────────────────

    def _stage1_score_baseline(self, health_score: float) -> RiskLevel:
        """Stage 1: map health score to initial RiskLevel via threshold bands."""
        return self._config.score_thresholds.classify(health_score)

    def _stage2_severity_escalation(
        self,
        current: RiskLevel,
        breakdowns: list[DefectSeverityBreakdown],
    ) -> RiskLevel:
        """
        Stage 2: raise risk based on the worst observed SeverityLevel.

        Evaluates all configured SeverityEscalationRules against the worst
        severity in the breakdown list.  Multiple rules can fire; each only
        raises, never lowers.
        """
        worst = _worst_severity(breakdowns)
        if worst is None:
            return current

        for rule in self._config.severity_escalation_rules:
            if _severity_gte(worst, rule.min_severity):
                current = _max_risk(current, rule.escalate_to)

        return current

    def _stage3_failure_mode_escalation(
        self,
        current: RiskLevel,
        modes: list[StructuralFailureMode],
    ) -> RiskLevel:
        """
        Stage 3: raise risk based on failure mode count, confidence, and category.

        Two sub-steps:
          a. Evaluate FailureModeEscalationRules (count + confidence thresholds).
          b. Raise to HIGH if any high-risk FailureModeCategory is detected.
        """
        if not modes:
            return current

        mode_count = len(modes)
        max_confidence = max(m.confidence for m in modes)

        # 3a: count + confidence rules
        for rule in self._config.failure_mode_escalation_rules:
            if (
                mode_count >= rule.min_failure_modes
                and max_confidence >= rule.min_confidence
            ):
                current = _max_risk(current, rule.escalate_to)

        # 3b: high-risk category bonus
        detected_categories = {m.category for m in modes}
        if detected_categories & self._config.high_risk_failure_categories:
            current = _max_risk(current, RiskLevel.HIGH)

        return current

    def _stage4_combined_override(
        self,
        current: RiskLevel,
        health_score: float,
        breakdowns: list[DefectSeverityBreakdown],
        modes: list[StructuralFailureMode],
    ) -> RiskLevel:
        """
        Stage 4: apply combined-evidence override rules.

        Each CombinedOverrideRule specifies a conjunction of conditions
        (failure mode count, worst severity, health score ceiling).  When all
        active conditions are satisfied the rule fires and risk is escalated.
        """
        if not self._config.combined_override_rules:
            return current

        mode_count = len(modes)
        worst = _worst_severity(breakdowns)

        for rule in self._config.combined_override_rules:
            if not self._combined_rule_fires(rule, mode_count, worst, health_score):
                continue
            current = _max_risk(current, rule.escalate_to)

        return current

    @staticmethod
    def _combined_rule_fires(
        rule: CombinedOverrideRule,
        mode_count: int,
        worst_severity: SeverityLevel | None,
        health_score: float,
    ) -> bool:
        """
        Return True when all active conditions on a CombinedOverrideRule hold.

        A condition field of None means it is not checked (always satisfied).
        """
        if rule.min_failure_modes is not None and mode_count < rule.min_failure_modes:
            return False
        if rule.min_severity is not None:
            if worst_severity is None:
                return False
            if not _severity_gte(worst_severity, rule.min_severity):
                return False
        return not (rule.max_score is not None and health_score > rule.max_score)
