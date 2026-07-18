"""
Engineering Rules Engine.

Deterministic, configuration-driven implementation of IEngineeringRulesEngine.
Applies structural engineering rules to DefectObservation data contained in
HealthAssessmentInput to identify potential StructuralFailureMode instances —
no machine learning, no LLMs, no external services, no probabilistic inference.

Scope boundary
--------------
This module answers "which structural failure mechanisms might be occurring
given the observed defects?" It deliberately does NOT:

  - Compute or consume a composite health score (IHealthScorer).
  - Consume DefectSeverityBreakdown output from ISeverityClassifier.
    EngineeringRules and SeverityClassifier are parallel consumers of the
    same HealthAssessmentInput; they are not dependent stages.
  - Assign risk levels (IRiskEngine).
  - Generate maintenance recommendations.
  - Orchestrate a full HealthAssessmentReport.

Architecture
------------
Rules are structured as independent, self-contained EngineeringRule objects.
Each rule:

  1. Receives the full set of category-grouped observations as a
     CategorySummary mapping (pre-computed once per call, not per rule).
  2. Returns a StructuralFailureMode if triggered, or None if not.
  3. Derives its confidence deterministically from observed measurements
     and rule satisfaction degree — no random or learned values.

Adding a new failure mode = adding one EngineeringRule instance to
DEFAULT_RULES. No changes to the algorithm or the engine class are required.

Confidence derivation
---------------------
Confidence is computed as a weighted combination of:
  - Base confidence: a rule-specific floor representing minimum certainty
    when all triggering conditions are satisfied.
  - Category confidence boost: the mean detection confidence of the
    triggering observations, scaled by a rule-defined weight.
  - Measurement evidence boost: a normalised magnitude signal (crack width,
    affected area) scaled by a rule-defined weight.

All three components are clipped to [0, 1] and the final result is
min(base + boost, ceiling) to ensure no rule overstates certainty.

NOTE: thresholds, base confidences, and weights are reasonable engineering
starting points for a deterministic explainable engine. They are NOT derived
from a specific engineering code or standard. Domain experts should review
and retune (or supply a custom EngineeringRulesConfig) before using this
engine for real structural decision-making.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import NamedTuple

from intelligence.interfaces import IEngineeringRulesEngine
from intelligence.schemas import (
    DefectCategory,
    DefectObservation,
    FailureModeCategory,
    HealthAssessmentInput,
    StructuralFailureMode,
)

# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


class CategorySummary(NamedTuple):
    """
    Pre-aggregated statistics for one DefectCategory across all its
    observations in a single HealthAssessmentInput.

    Populated once per identify_failure_modes() call and shared across
    all rules — avoids re-scanning observations inside each rule.
    """

    observations: list[DefectObservation]
    observation_count: int
    mean_confidence: float  # mean detection confidence across observations
    total_area_mm2: float | None  # sum of area_mm2, None if none calibrated
    max_width_mm: float | None  # largest max_width_mm, None if none calibrated
    max_crack_width_mm: float | None  # largest width_mm (crack-specific)


# A RuleEvaluator receives the pre-built category map and returns a
# StructuralFailureMode if the rule fires, else None.
RuleEvaluator = Callable[
    [Mapping[DefectCategory, CategorySummary]],
    StructuralFailureMode | None,
]


@dataclass(frozen=True)
class EngineeringRule:
    """
    A single, self-contained structural failure-mode rule.

    Attributes:
        name: Human-readable identifier (used in developer logs / metadata).
        evaluator: Pure function that inspects the category summary map and
            returns a StructuralFailureMode if the rule is satisfied.
    """

    name: str
    evaluator: RuleEvaluator


# ---------------------------------------------------------------------------
# Confidence helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _confidence(
    *,
    base: float,
    ceiling: float,
    category_summaries: Sequence[CategorySummary],
    obs_weight: float = 0.20,
    magnitude: float = 0.0,
    magnitude_weight: float = 0.10,
) -> float:
    """
    Compute a deterministic, explainable confidence value.

    Args:
        base: Rule-specific floor confidence when all conditions are met.
        ceiling: Maximum allowed confidence for this rule.
        category_summaries: Summaries of the categories that triggered the
            rule. Their mean detection confidence boosts the result.
        obs_weight: Weight applied to the mean detection confidence boost.
        magnitude: Normalised [0, 1] measurement signal (e.g. crack width
            fraction of a critical threshold, area fraction).
        magnitude_weight: Weight applied to the magnitude boost.

    Returns:
        Confidence in [base, ceiling].
    """
    mean_obs_confidence = _mean([s.mean_confidence for s in category_summaries])
    boost = obs_weight * mean_obs_confidence + magnitude_weight * _clamp(magnitude)
    return _clamp(base + boost, lo=base, hi=ceiling)


# ---------------------------------------------------------------------------
# Measurement normalisation helpers
# ---------------------------------------------------------------------------

# Thresholds used to normalise raw measurements into a [0, 1] magnitude signal.
# These mirror the "critical" values in DEFAULT_SCORING_RULES (health_scorer.py)
# but are intentionally not imported from there — the two modules are independent.
_CRACK_CRITICAL_WIDTH_MM: float = 5.0  # mm — structural crack threshold
_AREA_CRITICAL_MM2: float = 100_000.0  # mm² — ~316 mm × 316 mm patch


def _crack_width_magnitude(summary: CategorySummary) -> float:
    """Normalise the maximum observed crack width against the critical threshold."""
    w = summary.max_crack_width_mm
    if w is None:
        return 0.5  # neutral default when calibration is unavailable
    return _clamp(w / _CRACK_CRITICAL_WIDTH_MM)


def _area_magnitude(summary: CategorySummary) -> float:
    """Normalise the total affected area against the critical area threshold."""
    a = summary.total_area_mm2
    if a is None:
        return 0.5
    return _clamp(a / _AREA_CRITICAL_MM2)


def _multi_area_magnitude(summaries: Sequence[CategorySummary]) -> float:
    """Combined, saturating area magnitude across multiple categories."""
    areas = [s.total_area_mm2 for s in summaries if s.total_area_mm2 is not None]
    if not areas:
        return 0.5
    return _clamp(sum(areas) / _AREA_CRITICAL_MM2)


# ---------------------------------------------------------------------------
# Individual rule implementations
# ---------------------------------------------------------------------------


def _rule_severe_cracking_with_exposed_rebar(
    cats: Mapping[DefectCategory, CategorySummary],
) -> StructuralFailureMode | None:
    """
    Flexural or shear failure indicator: wide cracks co-occurring with
    exposed reinforcement suggest concrete cover has failed and load-path
    integrity is at risk.

    Triggers when:
      - CRACK observations are present with max crack width ≥ 1.0 mm, OR
        ≥ 2 crack observations with no width data.
      - EXPOSED_REINFORCEMENT observations are present.
    """
    crack = cats.get(DefectCategory.CRACK)
    rebar = cats.get(DefectCategory.EXPOSED_REINFORCEMENT)
    if crack is None or rebar is None:
        return None

    width = crack.max_crack_width_mm
    # Require measurable wide cracking or multiple crack instances
    crack_qualifies = (width is not None and width >= 1.0) or (
        width is None and crack.observation_count >= 2
    )
    if not crack_qualifies:
        return None

    mag = _crack_width_magnitude(crack)
    conf = _confidence(
        base=0.65,
        ceiling=0.90,
        category_summaries=[crack, rebar],
        obs_weight=0.15,
        magnitude=mag,
        magnitude_weight=0.10,
    )

    return StructuralFailureMode(
        category=FailureModeCategory.FLEXURAL,
        description=(
            "Wide cracking (max width "
            f"{f'{width:.2f} mm' if width is not None else 'unmeasured'}) "
            "co-occurring with exposed reinforcement indicates loss of concrete "
            "cover and potential flexural or shear failure mechanism."
        ),
        confidence=round(conf, 3),
        related_defect_categories=[
            DefectCategory.CRACK,
            DefectCategory.EXPOSED_REINFORCEMENT,
        ],
    )


def _rule_corrosion_with_exposed_rebar(
    cats: Mapping[DefectCategory, CategorySummary],
) -> StructuralFailureMode | None:
    """
    Corrosion-induced section loss: active corrosion combined with visible
    reinforcement indicates rebar cross-section is being lost, reducing
    load-carrying capacity.

    Triggers when:
      - CORROSION observations are present.
      - EXPOSED_REINFORCEMENT observations are present.
    """
    corrosion = cats.get(DefectCategory.CORROSION)
    rebar = cats.get(DefectCategory.EXPOSED_REINFORCEMENT)
    if corrosion is None or rebar is None:
        return None

    combined_area = sum(
        a
        for a in [corrosion.total_area_mm2, rebar.total_area_mm2]
        if a is not None
    )
    mag = _clamp(combined_area / _AREA_CRITICAL_MM2) if combined_area > 0 else 0.5

    conf = _confidence(
        base=0.70,
        ceiling=0.92,
        category_summaries=[corrosion, rebar],
        obs_weight=0.15,
        magnitude=mag,
        magnitude_weight=0.07,
    )

    corrosion_area_str = (
        f"{corrosion.total_area_mm2:.0f} mm²"
        if corrosion.total_area_mm2 is not None
        else "unmeasured area"
    )
    return StructuralFailureMode(
        category=FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS,
        description=(
            f"Active corrosion ({corrosion_area_str}) co-occurring with exposed "
            "reinforcement. Electrochemical corrosion is reducing effective rebar "
            "cross-section, compromising tensile capacity and structural integrity."
        ),
        confidence=round(conf, 3),
        related_defect_categories=[
            DefectCategory.CORROSION,
            DefectCategory.EXPOSED_REINFORCEMENT,
        ],
    )


def _rule_extensive_spalling(
    cats: Mapping[DefectCategory, CategorySummary],
) -> StructuralFailureMode | None:
    """
    Compression / punching-shear indicator: large-area spalling removes
    the compressive zone of a structural section, reducing axial and
    bending capacity.

    Triggers when:
      - SPALLING total_area_mm2 ≥ 30 000 mm², OR
        ≥ 3 spalling observations with no area data.
    """
    spalling = cats.get(DefectCategory.SPALLING)
    if spalling is None:
        return None

    area = spalling.total_area_mm2
    qualifies = (area is not None and area >= 30_000.0) or (
        area is None and spalling.observation_count >= 3
    )
    if not qualifies:
        return None

    mag = _area_magnitude(spalling)
    conf = _confidence(
        base=0.55,
        ceiling=0.85,
        category_summaries=[spalling],
        obs_weight=0.20,
        magnitude=mag,
        magnitude_weight=0.10,
    )

    area_str = f"{area:.0f} mm²" if area is not None else f"{spalling.observation_count} instances"
    return StructuralFailureMode(
        category=FailureModeCategory.COMPRESSION_BUCKLING,
        description=(
            f"Extensive spalling ({area_str}) detected. Loss of concrete in the "
            "compressive zone reduces the effective section depth and may indicate "
            "an emerging compression or punching-shear failure mechanism."
        ),
        confidence=round(conf, 3),
        related_defect_categories=[DefectCategory.SPALLING],
    )


def _rule_multiple_major_defects(
    cats: Mapping[DefectCategory, CategorySummary],
) -> StructuralFailureMode | None:
    """
    Combined degradation / unknown failure mode: the simultaneous presence
    of three or more distinct structurally significant defect categories
    indicates a multi-mechanism deterioration state that cannot be attributed
    to a single failure mode.

    Structurally significant categories (excludes SURFACE_DAMAGE, POTHOLE,
    UNKNOWN which are lower structural concern in isolation):
      CRACK, SPALLING, CORROSION, EXPOSED_REINFORCEMENT, DELAMINATION.

    Triggers when ≥ 3 of those categories are observed.
    """
    significant = [
        DefectCategory.CRACK,
        DefectCategory.SPALLING,
        DefectCategory.CORROSION,
        DefectCategory.EXPOSED_REINFORCEMENT,
        DefectCategory.DELAMINATION,
    ]
    present = [c for c in significant if c in cats]
    if len(present) < 3:
        return None

    present_summaries = [cats[c] for c in present]
    mag = _multi_area_magnitude(present_summaries)
    conf = _confidence(
        base=0.60,
        ceiling=0.88,
        category_summaries=present_summaries,
        obs_weight=0.15,
        magnitude=mag,
        magnitude_weight=0.13,
    )

    category_names = ", ".join(c.value for c in present)
    return StructuralFailureMode(
        category=FailureModeCategory.UNKNOWN,
        description=(
            f"Multiple co-occurring structural defect categories ({category_names}) "
            "indicate a multi-mechanism deterioration state. Combined degradation "
            "pathways elevate the risk of a complex failure mode that cannot be "
            "attributed to a single mechanism."
        ),
        confidence=round(conf, 3),
        related_defect_categories=present,
    )


def _rule_widespread_delamination(
    cats: Mapping[DefectCategory, CategorySummary],
) -> StructuralFailureMode | None:
    """
    Delamination-induced failure: large-area delamination indicates
    inter-laminar or concrete-cover debonding, which can progress to
    sudden spalling and loss of structural continuity.

    Triggers when:
      - DELAMINATION total_area_mm2 ≥ 40 000 mm², OR
        ≥ 3 delamination observations with no area data.
    """
    delam = cats.get(DefectCategory.DELAMINATION)
    if delam is None:
        return None

    area = delam.total_area_mm2
    qualifies = (area is not None and area >= 40_000.0) or (
        area is None and delam.observation_count >= 3
    )
    if not qualifies:
        return None

    mag = _area_magnitude(delam)
    conf = _confidence(
        base=0.55,
        ceiling=0.82,
        category_summaries=[delam],
        obs_weight=0.20,
        magnitude=mag,
        magnitude_weight=0.07,
    )

    area_str = f"{area:.0f} mm²" if area is not None else f"{delam.observation_count} instances"
    return StructuralFailureMode(
        category=FailureModeCategory.DELAMINATION_INDUCED,
        description=(
            f"Widespread delamination ({area_str}) observed. Progressive debonding "
            "of concrete layers or structural laminates indicates a delamination-induced "
            "failure mechanism that may lead to sudden loss of load-transfer capacity."
        ),
        confidence=round(conf, 3),
        related_defect_categories=[DefectCategory.DELAMINATION],
    )


def _rule_crack_network_instability(
    cats: Mapping[DefectCategory, CategorySummary],
) -> StructuralFailureMode | None:
    """
    Shear or flexural instability from a crack network: multiple crack
    observations (≥ 3) suggest a developed crack network rather than
    isolated defects, which can indicate structural instability.

    Triggers when:
      - ≥ 3 CRACK observations, AND
      - At least one crack has max_width_mm ≥ 0.5 mm, OR
        none have width data (conservative fallback).
    """
    crack = cats.get(DefectCategory.CRACK)
    if crack is None or crack.observation_count < 3:
        return None

    width = crack.max_crack_width_mm
    qualifies = width is None or width >= 0.5
    if not qualifies:
        return None

    mag = _crack_width_magnitude(crack)
    conf = _confidence(
        base=0.55,
        ceiling=0.83,
        category_summaries=[crack],
        obs_weight=0.20,
        magnitude=mag,
        magnitude_weight=0.08,
    )

    width_str = f"{width:.2f} mm" if width is not None else "unmeasured"
    return StructuralFailureMode(
        category=FailureModeCategory.SHEAR,
        description=(
            f"Crack network detected: {crack.observation_count} crack observations "
            f"(max width {width_str}). Multiple cracks indicate a developed "
            "crack network that may signal shear or flexural structural instability "
            "rather than isolated surface damage."
        ),
        confidence=round(conf, 3),
        related_defect_categories=[DefectCategory.CRACK],
    )


def _rule_significant_material_loss(
    cats: Mapping[DefectCategory, CategorySummary],
) -> StructuralFailureMode | None:
    """
    Compression buckling risk from material loss: spalling and corrosion
    together can represent significant loss of structural cross-section
    material, increasing buckling slenderness ratio.

    Triggers when:
      - Both SPALLING and CORROSION are present, AND
      - Combined total_area_mm2 ≥ 50 000 mm², OR
        at least one category lacks area data (conservative fallback).
    """
    spalling = cats.get(DefectCategory.SPALLING)
    corrosion = cats.get(DefectCategory.CORROSION)
    if spalling is None or corrosion is None:
        return None

    s_area = spalling.total_area_mm2
    c_area = corrosion.total_area_mm2

    if s_area is not None and c_area is not None:
        combined = s_area + c_area
        if combined < 50_000.0:
            return None
        mag = _clamp(combined / _AREA_CRITICAL_MM2)
    else:
        # Conservative: if either lacks calibration, treat as qualifying
        combined_known = sum(a for a in [s_area, c_area] if a is not None)
        mag = _clamp(combined_known / _AREA_CRITICAL_MM2) if combined_known > 0 else 0.5

    conf = _confidence(
        base=0.58,
        ceiling=0.86,
        category_summaries=[spalling, corrosion],
        obs_weight=0.18,
        magnitude=mag,
        magnitude_weight=0.10,
    )

    s_str = f"{s_area:.0f} mm²" if s_area is not None else "unmeasured"
    c_str = f"{c_area:.0f} mm²" if c_area is not None else "unmeasured"
    return StructuralFailureMode(
        category=FailureModeCategory.COMPRESSION_BUCKLING,
        description=(
            f"Significant material loss from combined spalling ({s_str}) and "
            f"corrosion ({c_str}). Reduction of the effective structural cross-section "
            "increases slenderness and the risk of compression or buckling failure."
        ),
        confidence=round(conf, 3),
        related_defect_categories=[DefectCategory.SPALLING, DefectCategory.CORROSION],
    )


def _rule_corrosion_induced_spalling_rebar(
    cats: Mapping[DefectCategory, CategorySummary],
) -> StructuralFailureMode | None:
    """
    Classic corrosion-induced section loss trinity: corrosion causes
    expansive oxide products that crack and spall the cover, ultimately
    exposing and further degrading reinforcement.

    Triggers when all three of CORROSION, SPALLING, and EXPOSED_REINFORCEMENT
    are present simultaneously.
    """
    corrosion = cats.get(DefectCategory.CORROSION)
    spalling = cats.get(DefectCategory.SPALLING)
    rebar = cats.get(DefectCategory.EXPOSED_REINFORCEMENT)
    if corrosion is None or spalling is None or rebar is None:
        return None

    mag = _multi_area_magnitude([corrosion, spalling, rebar])
    conf = _confidence(
        base=0.75,
        ceiling=0.95,
        category_summaries=[corrosion, spalling, rebar],
        obs_weight=0.12,
        magnitude=mag,
        magnitude_weight=0.08,
    )

    return StructuralFailureMode(
        category=FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS,
        description=(
            "Classic corrosion-expansion-spalling-rebar-exposure sequence detected: "
            "CORROSION, SPALLING, and EXPOSED_REINFORCEMENT co-occur. Expansive "
            "corrosion products have cracked and spalled concrete cover, leaving "
            "reinforcement exposed to further electrochemical attack and accelerating "
            "section loss."
        ),
        confidence=round(conf, 3),
        related_defect_categories=[
            DefectCategory.CORROSION,
            DefectCategory.SPALLING,
            DefectCategory.EXPOSED_REINFORCEMENT,
        ],
    )


def _rule_delamination_with_spalling(
    cats: Mapping[DefectCategory, CategorySummary],
) -> StructuralFailureMode | None:
    """
    Punching-shear risk from progressive cover failure: delamination that
    accompanies spalling indicates a two-stage cover failure, where
    delaminated areas are precursors to sudden detachment.

    Triggers when:
      - Both DELAMINATION and SPALLING are present.
      - Combined total area ≥ 25 000 mm² OR either area is unavailable.
    """
    delam = cats.get(DefectCategory.DELAMINATION)
    spalling = cats.get(DefectCategory.SPALLING)
    if delam is None or spalling is None:
        return None

    d_area = delam.total_area_mm2
    s_area = spalling.total_area_mm2

    if d_area is not None and s_area is not None and d_area + s_area < 25_000.0:
        return None

    mag = _multi_area_magnitude([delam, spalling])
    conf = _confidence(
        base=0.57,
        ceiling=0.83,
        category_summaries=[delam, spalling],
        obs_weight=0.18,
        magnitude=mag,
        magnitude_weight=0.10,
    )

    return StructuralFailureMode(
        category=FailureModeCategory.DELAMINATION_INDUCED,
        description=(
            "Delamination co-occurring with spalling indicates progressive concrete "
            "cover failure: delaminated zones are precursors to sudden detachment, "
            "concentrating stress and creating punching-shear risk at transition edges."
        ),
        confidence=round(conf, 3),
        related_defect_categories=[DefectCategory.DELAMINATION, DefectCategory.SPALLING],
    )


# ---------------------------------------------------------------------------
# Default rule set
# ---------------------------------------------------------------------------

DEFAULT_RULES: tuple[EngineeringRule, ...] = (
    EngineeringRule(
        name="severe_cracking_with_exposed_rebar",
        evaluator=_rule_severe_cracking_with_exposed_rebar,
    ),
    EngineeringRule(
        name="corrosion_with_exposed_rebar",
        evaluator=_rule_corrosion_with_exposed_rebar,
    ),
    EngineeringRule(
        name="extensive_spalling",
        evaluator=_rule_extensive_spalling,
    ),
    EngineeringRule(
        name="multiple_major_defects",
        evaluator=_rule_multiple_major_defects,
    ),
    EngineeringRule(
        name="widespread_delamination",
        evaluator=_rule_widespread_delamination,
    ),
    EngineeringRule(
        name="crack_network_instability",
        evaluator=_rule_crack_network_instability,
    ),
    EngineeringRule(
        name="significant_material_loss",
        evaluator=_rule_significant_material_loss,
    ),
    EngineeringRule(
        name="corrosion_induced_spalling_rebar",
        evaluator=_rule_corrosion_induced_spalling_rebar,
    ),
    EngineeringRule(
        name="delamination_with_spalling",
        evaluator=_rule_delamination_with_spalling,
    ),
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EngineeringRulesConfig:
    """
    Full configuration for an EngineeringRulesEngine instance.

    Attributes:
        rules: Ordered sequence of EngineeringRule objects to evaluate.
            Rules are evaluated in declaration order. All triggered rules
            produce output — there is no short-circuit behaviour.
        engine_version: Recorded in output metadata for traceability.
    """

    rules: tuple[EngineeringRule, ...] = field(default_factory=lambda: DEFAULT_RULES)
    engine_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class EngineeringRulesEngine(IEngineeringRulesEngine):
    """
    Deterministic, configurable implementation of IEngineeringRulesEngine.

    See module docstring for algorithm, scope boundary, and confidence
    derivation strategy.

    Usage::

        engine = EngineeringRulesEngine()
        failure_modes = engine.identify_failure_modes(assessment_input)

    To customise the rule set or engine version, supply an
    EngineeringRulesConfig::

        config = EngineeringRulesConfig(
            rules=(my_rule_a, my_rule_b),
            engine_version="2.0.0",
        )
        engine = EngineeringRulesEngine(config=config)
    """

    def __init__(self, config: EngineeringRulesConfig | None = None) -> None:
        self._config = config or EngineeringRulesConfig()

    # ── IEngineeringRulesEngine contract ────────────────────────────────────

    def identify_failure_modes(
        self, assessment_input: HealthAssessmentInput
    ) -> list[StructuralFailureMode]:
        """
        Apply all configured engineering rules to the given input.

        Each rule is evaluated independently against the same pre-aggregated
        category summary map. Rules that are not triggered produce no output.
        All triggered rules contribute to the result — there is no
        short-circuit or priority ordering.

        Output is ordered by the declaration order of DEFAULT_RULES (or the
        custom rule sequence supplied in EngineeringRulesConfig). Rules that
        produce the same FailureModeCategory are both retained, as they may
        have been triggered by different defect evidence.

        Returns:
            List of StructuralFailureMode instances, which may be empty if
            no observations match any rule's trigger conditions.
        """
        if not assessment_input.observations:
            return []

        category_map = self._build_category_map(assessment_input.observations)

        results: list[StructuralFailureMode] = []
        for rule in self._config.rules:
            failure_mode = rule.evaluator(category_map)
            if failure_mode is not None:
                results.append(failure_mode)

        return results

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _build_category_map(
        observations: list[DefectObservation],
    ) -> dict[DefectCategory, CategorySummary]:
        """
        Pre-aggregate all observations by DefectCategory.

        This single-pass aggregation is computed once per
        identify_failure_modes() call and shared across all rule evaluators,
        avoiding repeated iteration over observations inside each rule.
        """
        groups: dict[DefectCategory, list[DefectObservation]] = defaultdict(list)
        for obs in observations:
            groups[obs.defect_category].append(obs)

        category_map: dict[DefectCategory, CategorySummary] = {}
        for category, group in groups.items():
            confidences = [o.confidence for o in group]
            mean_conf = _mean(confidences)

            areas = [o.area_mm2 for o in group if o.area_mm2 is not None]
            total_area: float | None = sum(areas) if areas else None

            max_widths = [o.max_width_mm for o in group if o.max_width_mm is not None]
            max_width: float | None = max(max_widths) if max_widths else None

            crack_widths = [o.width_mm for o in group if o.width_mm is not None]
            max_crack_width: float | None = max(crack_widths) if crack_widths else None

            category_map[category] = CategorySummary(
                observations=group,
                observation_count=len(group),
                mean_confidence=mean_conf,
                total_area_mm2=total_area,
                max_width_mm=max_width,
                max_crack_width_mm=max_crack_width,
            )

        return category_map
