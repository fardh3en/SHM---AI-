"""
Severity Classification Engine.

Deterministic, configuration-driven implementation of ISeverityClassifier.
Groups defect observations by category and maps each group onto a single
SeverityLevel using centralised, per-category threshold bands — no machine
learning, no LLMs, no external services.

Scope boundary: this module answers "how severe is what was observed?" per
defect category. It deliberately does NOT:
  - Compute a composite health score (HealthScorer's responsibility).
  - Populate DefectSeverityBreakdown.contribution_score — that field is
    explicitly scoped to "the scoring engine implementation" per its own
    schema docstring, not to this classifier.
  - Identify structural failure modes (IEngineeringRulesEngine).
  - Determine overall asset risk (IRiskEngine).
  - Orchestrate a full HealthAssessmentReport.

Relationship to HealthScorer (avoiding duplicated logic)
----------------------------------------------------------
Both HealthScorer and this classifier read a category-specific physical
magnitude off each observation (e.g. crack width, defect area) — that
mapping of "which field matters for this category" is a shared engineering
concept, so the *idea* is naturally similar. The *mechanism* is deliberately
different and not shared code:

  - HealthScorer produces a single continuous score by combining
    confidence-weighted, saturating magnitude factors across ALL
    observations via a complementary product.
  - This classifier produces a discrete SeverityLevel PER CATEGORY by
    comparing an aggregated magnitude (max or sum, depending on the
    category — see AggregationMode) against ascending threshold bands.
    Confidence is intentionally not a factor here: severity reflects what
    was physically observed, while weighting by detection confidence is
    HealthScorer's concern when it decides how much to trust that
    observation in the aggregate score.

No code or constants are imported from health_scorer.py, and none of this
module's thresholds are derived from HealthScorer's rule weights.
"""
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from intelligence.interfaces import ISeverityClassifier
from intelligence.schemas import (
    DefectCategory,
    DefectObservation,
    DefectSeverityBreakdown,
    HealthAssessmentInput,
    SeverityLevel,
)

# Reads the single physical measurement used to classify severity for a
# given defect category (e.g. width_mm for cracks, area_mm2 for spalling).
MagnitudeExtractor = Callable[[DefectObservation], float | None]


class AggregationMode(StrEnum):
    """
    How a category's per-observation magnitudes are combined into the
    single driver value used for band lookup.

    MAX: the worst single observation determines severity (appropriate for
         measurements like crack width, where one bad instance matters
         regardless of how many minor ones accompany it).
    SUM: total extent across all observations determines severity
         (appropriate for area-based measurements, where widespread
         moderate damage can be as concerning as one large patch).
    """

    MAX = "max"
    SUM = "sum"


@dataclass(frozen=True)
class SeverityBand:
    """One ascending threshold: magnitudes <= upper_bound map to `severity`."""

    upper_bound: float
    severity: SeverityLevel


@dataclass(frozen=True)
class CategorySeverityRule:
    """
    Severity classification configuration for a single defect category.

    Attributes:
        magnitude_extractor: Reads the relevant physical measurement off a
            DefectObservation. Returns None if unavailable.
        aggregation: How per-observation magnitudes combine into one driver
            value (see AggregationMode).
        bands: Ascending (upper_bound, severity) thresholds. The first band
            whose upper_bound >= the driver value applies. A driver value
            exceeding every band's upper_bound is classified CRITICAL.
        default_severity: Used when NO observation in the group has a
            value for the magnitude field (e.g. calibration wasn't
            available for any of them).
    """

    magnitude_extractor: MagnitudeExtractor
    aggregation: AggregationMode
    bands: tuple[SeverityBand, ...]
    default_severity: SeverityLevel


# ── Default severity thresholds ─────────────────────────────────────────────
# NOTE: as with HealthScorer's DEFAULT_SCORING_RULES, these band edges and
# defaults are reasonable deterministic starting points for an explainable
# classifier — NOT derived from a specific engineering code or standard.
# Review and retune (or supply a custom SeverityClassifierConfig) before
# using this for real structural decision-making.
DEFAULT_SEVERITY_RULES: Mapping[DefectCategory, CategorySeverityRule] = {
    DefectCategory.CRACK: CategorySeverityRule(
        magnitude_extractor=lambda o: o.width_mm,
        aggregation=AggregationMode.MAX,
        bands=(
            SeverityBand(0.3, SeverityLevel.NEGLIGIBLE),  # hairline
            SeverityBand(1.0, SeverityLevel.MINOR),
            SeverityBand(3.0, SeverityLevel.MODERATE),
            SeverityBand(5.0, SeverityLevel.SEVERE),
        ),  # > 5.0mm -> CRITICAL
        default_severity=SeverityLevel.MODERATE,
    ),
    DefectCategory.SPALLING: CategorySeverityRule(
        magnitude_extractor=lambda o: o.area_mm2,
        aggregation=AggregationMode.SUM,
        bands=(
            SeverityBand(5_000.0, SeverityLevel.NEGLIGIBLE),
            SeverityBand(20_000.0, SeverityLevel.MINOR),
            SeverityBand(50_000.0, SeverityLevel.MODERATE),
            SeverityBand(100_000.0, SeverityLevel.SEVERE),
        ),
        default_severity=SeverityLevel.MODERATE,
    ),
    DefectCategory.CORROSION: CategorySeverityRule(
        magnitude_extractor=lambda o: o.area_mm2,
        aggregation=AggregationMode.SUM,
        bands=(
            SeverityBand(4_000.0, SeverityLevel.NEGLIGIBLE),
            SeverityBand(15_000.0, SeverityLevel.MINOR),
            SeverityBand(40_000.0, SeverityLevel.MODERATE),
            SeverityBand(80_000.0, SeverityLevel.SEVERE),
        ),
        default_severity=SeverityLevel.MODERATE,
    ),
    DefectCategory.EXPOSED_REINFORCEMENT: CategorySeverityRule(
        magnitude_extractor=lambda o: o.area_mm2,
        aggregation=AggregationMode.SUM,
        bands=(
            SeverityBand(2_000.0, SeverityLevel.MINOR),
            SeverityBand(8_000.0, SeverityLevel.MODERATE),
            SeverityBand(20_000.0, SeverityLevel.SEVERE),
        ),  # exposed rebar has no NEGLIGIBLE band — inherently at least minor
        default_severity=SeverityLevel.SEVERE,  # conservative when extent is unknown
    ),
    DefectCategory.DELAMINATION: CategorySeverityRule(
        magnitude_extractor=lambda o: o.area_mm2,
        aggregation=AggregationMode.SUM,
        bands=(
            SeverityBand(5_000.0, SeverityLevel.NEGLIGIBLE),
            SeverityBand(20_000.0, SeverityLevel.MINOR),
            SeverityBand(50_000.0, SeverityLevel.MODERATE),
            SeverityBand(100_000.0, SeverityLevel.SEVERE),
        ),
        default_severity=SeverityLevel.MODERATE,
    ),
    DefectCategory.POTHOLE: CategorySeverityRule(
        magnitude_extractor=lambda o: o.area_mm2,
        aggregation=AggregationMode.SUM,
        bands=(
            SeverityBand(10_000.0, SeverityLevel.NEGLIGIBLE),
            SeverityBand(40_000.0, SeverityLevel.MINOR),
            SeverityBand(100_000.0, SeverityLevel.MODERATE),
            SeverityBand(200_000.0, SeverityLevel.SEVERE),
        ),
        default_severity=SeverityLevel.MODERATE,
    ),
    DefectCategory.SURFACE_DAMAGE: CategorySeverityRule(
        magnitude_extractor=lambda o: o.area_mm2,
        aggregation=AggregationMode.SUM,
        bands=(
            SeverityBand(20_000.0, SeverityLevel.NEGLIGIBLE),
            SeverityBand(60_000.0, SeverityLevel.MINOR),
            SeverityBand(150_000.0, SeverityLevel.MODERATE),
            SeverityBand(300_000.0, SeverityLevel.SEVERE),
        ),
        default_severity=SeverityLevel.MINOR,  # typically the lowest-risk category
    ),
    DefectCategory.UNKNOWN: CategorySeverityRule(
        magnitude_extractor=lambda o: o.area_mm2,
        aggregation=AggregationMode.SUM,
        bands=(
            SeverityBand(5_000.0, SeverityLevel.NEGLIGIBLE),
            SeverityBand(20_000.0, SeverityLevel.MINOR),
            SeverityBand(50_000.0, SeverityLevel.MODERATE),
            SeverityBand(100_000.0, SeverityLevel.SEVERE),
        ),
        default_severity=SeverityLevel.MODERATE,
    ),
}


@dataclass(frozen=True)
class SeverityClassifierConfig:
    """
    Full configuration for a SeverityClassifier instance.

    Attributes:
        rules: Per-category classification rules. Categories not present
            here fall back to the UNKNOWN rule.
    """

    rules: Mapping[DefectCategory, CategorySeverityRule] = field(
        default_factory=lambda: DEFAULT_SEVERITY_RULES
    )


class SeverityClassifier(ISeverityClassifier):
    """
    Deterministic, configurable implementation of ISeverityClassifier.

    See module docstring for classification strategy and explicit scope
    boundary relative to HealthScorer.
    """

    def __init__(self, config: SeverityClassifierConfig | None = None) -> None:
        self._config = config or SeverityClassifierConfig()

    # ── ISeverityClassifier contract ────────────────────────────────────────
    def classify(
        self, assessment_input: HealthAssessmentInput
    ) -> list[DefectSeverityBreakdown]:
        """
        Group observations by category and classify each group's severity.

        Output is ordered by DefectCategory's canonical declaration order
        (restricted to categories actually present), independent of the
        order observations appear in the input — this keeps output fully
        deterministic and easy to compare across runs.
        """
        groups: dict[DefectCategory, list[DefectObservation]] = {}
        for observation in assessment_input.observations:
            groups.setdefault(observation.defect_category, []).append(observation)

        breakdowns: list[DefectSeverityBreakdown] = []
        for category in DefectCategory:
            group = groups.get(category)
            if not group:
                continue
            breakdowns.append(self._classify_group(category, group))

        return breakdowns

    # ── Internal helpers ─────────────────────────────────────────────────────
    def _classify_group(
        self, category: DefectCategory, group: list[DefectObservation]
    ) -> DefectSeverityBreakdown:
        rule = self._config.rules.get(category, self._config.rules[DefectCategory.UNKNOWN])

        magnitudes = [
            value
            for observation in group
            if (value := rule.magnitude_extractor(observation)) is not None
        ]

        if magnitudes:
            driver_value = (
                max(magnitudes) if rule.aggregation is AggregationMode.MAX else sum(magnitudes)
            )
            severity = self._band_lookup(driver_value, rule.bands)
        else:
            severity = rule.default_severity

        total_area_mm2 = self._sum_optional(o.area_mm2 for o in group)
        max_width_mm = self._max_optional(o.max_width_mm for o in group)

        return DefectSeverityBreakdown(
            defect_category=category,
            severity=severity,
            observation_count=len(group),
            total_area_mm2=total_area_mm2,
            max_width_mm=max_width_mm,
            contribution_score=None,  # scoring engine's responsibility, not this classifier's
        )

    @staticmethod
    def _band_lookup(driver_value: float, bands: tuple[SeverityBand, ...]) -> SeverityLevel:
        """Return the first band whose upper_bound >= driver_value, else CRITICAL."""
        for band in bands:
            if driver_value <= band.upper_bound:
                return band.severity
        return SeverityLevel.CRITICAL

    @staticmethod
    def _sum_optional(values: Iterable[float | None]) -> float | None:
        present = [v for v in values if v is not None]
        return sum(present) if present else None

    @staticmethod
    def _max_optional(values: Iterable[float | None]) -> float | None:
        present = [v for v in values if v is not None]
        return max(present) if present else None
