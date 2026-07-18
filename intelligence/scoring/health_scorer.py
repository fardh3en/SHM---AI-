"""
Health Scoring Engine.

Deterministic, configuration-driven implementation of IHealthScorer. Turns
a set of defect observations into a single composite health score using a
transparent, explainable formula — no machine learning, no LLMs.

Scope boundary (see class docstring on HealthScorer for detail): this module
computes the composite score and, via the convenience `assess()` method,
assembles a schema-valid HealthAssessmentReport around it. It does NOT
perform per-defect severity classification (ISeverityClassifier) or
engineering rule / failure-mode analysis (IEngineeringRulesEngine) — those
remain empty/unpopulated here, to be filled in by their own dedicated
implementations in a later milestone. It also does NOT factor in asset age
or design life; that degradation-over-time modelling is reserved for
Phase 4 (Material Degradation Models), not this scoring engine.

Algorithm
---------
Each observation contributes a "severity" value in [0, 1]:

    severity = base_weight(category) * confidence * magnitude_factor

where `magnitude_factor` is the observation's calibrated physical
measurement (e.g. crack width, defect area) normalised against a
per-category "critical" threshold, saturating at 1.0. If no calibrated
measurement is available for that observation, a configurable neutral
default is used instead.

Individual severities are combined using a complementary product
("noisy-OR"), which is standard for combining independent risk
contributions and has three properties that make it a good fit here:

    health_score = 100 * PRODUCT(1 - severity_i)  for all observations i

  - Naturally bounded to (0, 100] with no ad-hoc clamping artefacts.
  - Zero observations -> score of 100 (no observed defects).
  - Monotonically decreases as more/worse defects are added, but a single
    additional minor defect never swings the score as violently as a
    naive sum would once many defects are already present.

All weights and thresholds live in HealthScorerConfig / DEFAULT_SCORING_RULES
below and can be overridden per instance — adding support for a new defect
category, or retuning an existing one, requires no changes to the scoring
algorithm itself.
"""
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from intelligence.interfaces import IHealthScorer
from intelligence.schemas import (
    DefectCategory,
    DefectObservation,
    HealthAssessmentInput,
    HealthAssessmentReport,
    RiskLevel,
)

# A MagnitudeExtractor reads the single physical measurement that best
# represents "how bad" an observation of a given category is. Explicit
# callables (rather than a string attribute name + getattr) keep this
# fully statically typed.
MagnitudeExtractor = Callable[[DefectObservation], float | None]


@dataclass(frozen=True)
class DefectScoringRule:
    """
    Scoring configuration for a single defect category.

    Attributes:
        base_weight: Maximum severity contribution, in [0, 1], of a single
            observation in this category when confidence is 1.0 and its
            magnitude is at or beyond critical_threshold.
        magnitude_extractor: Reads the relevant physical measurement off a
            DefectObservation (e.g. width_mm for cracks, area_mm2 for
            spalling). Returns None if that measurement isn't available.
        critical_threshold: The magnitude value at which magnitude_factor
            saturates to 1.0. Must be > 0.
    """

    base_weight: float
    magnitude_extractor: MagnitudeExtractor
    critical_threshold: float


# ── Default scoring rules ───────────────────────────────────────────────────
# NOTE: these base_weight and critical_threshold values are reasonable
# starting defaults for a deterministic, explainable scoring model — they
# are NOT derived from a specific engineering code or standard. Domain
# experts should review and retune them (or supply a custom
# HealthScorerConfig) before this score is used for real structural
# decision-making.
DEFAULT_SCORING_RULES: Mapping[DefectCategory, DefectScoringRule] = {
    DefectCategory.CRACK: DefectScoringRule(
        base_weight=0.35,
        magnitude_extractor=lambda o: o.width_mm,
        critical_threshold=5.0,  # mm — wide structural crack
    ),
    DefectCategory.SPALLING: DefectScoringRule(
        base_weight=0.40,
        magnitude_extractor=lambda o: o.area_mm2,
        critical_threshold=50_000.0,  # mm^2 (~ 22cm x 22cm patch)
    ),
    DefectCategory.CORROSION: DefectScoringRule(
        base_weight=0.45,
        magnitude_extractor=lambda o: o.area_mm2,
        critical_threshold=40_000.0,
    ),
    DefectCategory.EXPOSED_REINFORCEMENT: DefectScoringRule(
        base_weight=0.55,
        magnitude_extractor=lambda o: o.area_mm2,
        critical_threshold=20_000.0,
    ),
    DefectCategory.DELAMINATION: DefectScoringRule(
        base_weight=0.40,
        magnitude_extractor=lambda o: o.area_mm2,
        critical_threshold=50_000.0,
    ),
    DefectCategory.POTHOLE: DefectScoringRule(
        base_weight=0.30,
        magnitude_extractor=lambda o: o.area_mm2,
        critical_threshold=100_000.0,
    ),
    DefectCategory.SURFACE_DAMAGE: DefectScoringRule(
        base_weight=0.15,
        magnitude_extractor=lambda o: o.area_mm2,
        critical_threshold=100_000.0,
    ),
    DefectCategory.UNKNOWN: DefectScoringRule(
        base_weight=0.20,
        magnitude_extractor=lambda o: o.area_mm2,
        critical_threshold=50_000.0,
    ),
}


@dataclass(frozen=True)
class HealthScorerConfig:
    """
    Full configuration for a HealthScorer instance.

    Attributes:
        rules: Per-category scoring rules. Categories not present here fall
            back to the UNKNOWN rule.
        default_magnitude_factor: Used when an observation has no value for
            its category's magnitude field (e.g. calibration wasn't
            available). 0.5 is a neutral "assume moderate" default —
            neither optimistic nor punitive.
        engine_version: Recorded in HealthAssessmentReport.metadata so a
            report can always be traced back to the scoring configuration
            that produced it.
    """

    rules: Mapping[DefectCategory, DefectScoringRule] = field(
        default_factory=lambda: DEFAULT_SCORING_RULES
    )
    default_magnitude_factor: float = 0.5
    engine_version: str = "1.0.0"


class HealthScorer(IHealthScorer):
    """
    Deterministic, configurable implementation of IHealthScorer.

    See module docstring for the scoring algorithm and explicit scope
    boundary (no severity classification, no failure-mode rules, no
    age/degradation modelling).
    """

    def __init__(self, config: HealthScorerConfig | None = None) -> None:
        self._config = config or HealthScorerConfig()

    # ── IHealthScorer contract ──────────────────────────────────────────────
    def calculate_score(self, assessment_input: HealthAssessmentInput) -> float:
        """
        Compute the composite health score for the given input.

        Returns:
            Score in [0, 100]. 100 when there are no observations.
        """
        if not assessment_input.observations:
            return 100.0

        retained_fraction = 1.0
        for observation in assessment_input.observations:
            severity = self._observation_severity(observation)
            retained_fraction *= 1.0 - severity

        score = 100.0 * retained_fraction
        return max(0.0, min(100.0, score))

    # ── Convenience: full report assembly ───────────────────────────────────
    def assess(self, assessment_input: HealthAssessmentInput) -> HealthAssessmentReport:
        """
        Compute the health score and assemble a schema-valid
        HealthAssessmentReport around it.

        severity_breakdown and failure_modes are intentionally left empty —
        populating them is the responsibility of ISeverityClassifier and
        IEngineeringRulesEngine implementations, not this scorer. risk_level
        is filled in using a direct, pure function of the score (see
        _score_to_risk_level) purely so a schema-valid report can be
        returned; it is not a substitute for a dedicated IRiskEngine
        implementation.
        """
        score = self.calculate_score(assessment_input)

        return HealthAssessmentReport(
            asset_id=assessment_input.asset_id,
            inspection_id=assessment_input.inspection_id,
            health_score=score,
            risk_level=self._score_to_risk_level(score),
            severity_breakdown=[],
            failure_modes=[],
            metadata={
                "engine": "HealthScorer",
                "engine_version": self._config.engine_version,
                "observation_count": len(assessment_input.observations),
                "note": (
                    "severity_breakdown and failure_modes are intentionally "
                    "empty in this report; they require dedicated "
                    "ISeverityClassifier / IEngineeringRulesEngine "
                    "implementations not yet built."
                ),
            },
        )

    # ── Internal helpers ─────────────────────────────────────────────────────
    def _observation_severity(self, observation: DefectObservation) -> float:
        """Compute one observation's severity contribution in [0, 1]."""
        rule = self._config.rules.get(
            observation.defect_category, self._config.rules[DefectCategory.UNKNOWN]
        )

        raw_magnitude = rule.magnitude_extractor(observation)
        if raw_magnitude is None:
            magnitude_factor = self._config.default_magnitude_factor
        elif rule.critical_threshold <= 0:
            magnitude_factor = 1.0
        else:
            magnitude_factor = max(0.0, min(1.0, raw_magnitude / rule.critical_threshold))

        severity = rule.base_weight * observation.confidence * magnitude_factor
        return max(0.0, min(1.0, severity))

    @staticmethod
    def _score_to_risk_level(score: float) -> RiskLevel:
        """
        Direct, pure score -> RiskLevel banding, matching the thresholds
        already documented against RiskLevel in
        backend/app/models/health_record.py (75-100 low / 50-74 medium /
        25-49 high / 0-24 critical).

        This exists solely so assess() can return a schema-valid report; it
        deliberately does not consider individual defects and is not a
        substitute for a dedicated IRiskEngine implementation.
        """
        if score >= 75.0:
            return RiskLevel.LOW
        if score >= 50.0:
            return RiskLevel.MEDIUM
        if score >= 25.0:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL
