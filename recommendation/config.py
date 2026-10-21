"""
Phase 5 Recommendation Decision Engine — Tunable Configuration Tables.

All recommendation rules and cost-rate coefficients live here as frozen
dataclasses, matching the pattern established in degradation/config.py.

NOTE: The default values in this module are reasonable starting points for a
deterministic, configuration-driven recommendation engine.  They are NOT
derived from a specific engineering code or standard, nor have they been
calibrated against real inspection or cost data.  Every entry in every table
below — recommendation rules, failure-mode escalation thresholds, cost rates,
asset-type multipliers, and emergency mobilization cost — requires review and
validation by a qualified structural engineer and a quantity-surveyor or cost
engineer before this module is used for real structural decision-making.

Scope boundary
--------------
This module defines configuration tables only.  It does NOT:
  - Implement any decision logic or cost formulas.
  - Import from backend.app.models (ORM decoupling).
  - Depend on recommendation/schemas.py (avoids circular imports).
"""
from __future__ import annotations

from collections.abc import Mapping  # noqa: TC003
from dataclasses import dataclass

from intelligence.schemas import (  # noqa: TC001
    AssetType,
    DefectCategory,
    FailureModeCategory,
    RiskLevel,
)
from recommendation.schemas import RecommendedActionType  # noqa: TC001

# ---------------------------------------------------------------------------
# Recommendation rules (risk-level → action + inspection interval)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecommendationRule:
    """
    Maps a RiskLevel to a recommended action and next-inspection interval.

    NOTE: action and next_inspection_interval_years values are illustrative
    engineering starting points, not derived from a real cost database,
    maintenance standard, or empirical calibration study.  A structural
    engineer and maintenance planner must review these values before production
    use.

    Attributes:
        action: The recommended maintenance action for this risk band.
        next_inspection_interval_years: Suggested years until next inspection.
    """

    action: RecommendedActionType
    next_inspection_interval_years: float


# NOTE on CRITICAL interval: 0.1 years ≈ 5.2 weeks.  The interval is non-zero
# for schema validity (gt=0.0 on the field), but in practice an
# EMERGENCY_INTERVENTION case should trigger immediate follow-up scheduling
# outside the automated interval system.  Domain experts should review this
# value and whether a separate urgency flag is appropriate.
DEFAULT_RECOMMENDATION_RULES: Mapping[RiskLevel, RecommendationRule] = {
    RiskLevel.LOW: RecommendationRule(
        action=RecommendedActionType.MONITOR,
        next_inspection_interval_years=2.0,
    ),
    RiskLevel.MEDIUM: RecommendationRule(
        action=RecommendedActionType.INSPECT,
        next_inspection_interval_years=1.0,
    ),
    RiskLevel.HIGH: RecommendationRule(
        action=RecommendedActionType.REPAIR,
        next_inspection_interval_years=0.5,
    ),
    RiskLevel.CRITICAL: RecommendationRule(
        action=RecommendedActionType.EMERGENCY_INTERVENTION,
        next_inspection_interval_years=0.1,
    ),
}

# Reverse map: final action tier → interval, for post-escalation lookup.
# The RecommendationEngine re-looks-up the interval from the final escalated
# action rather than the baseline, using this mapping.
ACTION_TO_INTERVAL: Mapping[RecommendedActionType, float] = {
    rule.action: rule.next_inspection_interval_years
    for rule in DEFAULT_RECOMMENDATION_RULES.values()
}


# ---------------------------------------------------------------------------
# Failure-mode escalation configuration (Stage 3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FailureModeEscalationConfig:
    """
    Configuration for Stage 3 (failure-mode) escalation in RecommendationEngine.

    When any failure mode in health_report.failure_modes has a category in
    ``escalation_trigger_modes`` AND its confidence meets or exceeds
    ``confidence_threshold``, the recommended action is escalated to
    EMERGENCY_INTERVENTION if it is not already there.

    NOTE: the set of trigger modes and the confidence threshold below are
    illustrative engineering starting points.  The specific categories
    selected (PUNCHING_SHEAR, COMPRESSION_BUCKLING) represent failure
    mechanisms with sudden, low-warning-sign collapse potential, but the
    full set and the 0.70 threshold must be validated by a qualified
    structural engineer before production use.

    Attributes:
        escalation_trigger_modes: FailureModeCategories that can trigger
            emergency escalation when detected at sufficient confidence.
        confidence_threshold: Minimum detection confidence [0.0, 1.0] required
            for a failure mode to trigger escalation.
    """

    escalation_trigger_modes: frozenset[FailureModeCategory]
    confidence_threshold: float  # [0.0, 1.0]


DEFAULT_FAILURE_MODE_ESCALATION = FailureModeEscalationConfig(
    # Illustrative set — structural engineer review required before production use.
    # PUNCHING_SHEAR and COMPRESSION_BUCKLING represent sudden-failure mechanisms
    # that are commonly flagged as requiring immediate intervention in bridge/building
    # inspection practice.  Other categories (FLEXURAL, SHEAR,
    # CORROSION_INDUCED_SECTION_LOSS) may also warrant inclusion; this is a starting
    # point only.
    escalation_trigger_modes=frozenset({
        FailureModeCategory.PUNCHING_SHEAR,
        FailureModeCategory.COMPRESSION_BUCKLING,
    }),
    confidence_threshold=0.70,
)


# ---------------------------------------------------------------------------
# Cost rates per defect category
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CostRate:
    """
    Cost rate for one DefectCategory used by CostEstimator.

    The cost for a defect category is estimated as:
        base_cost = rate_per_unit * total_area_mm2
        low_cost  = base_cost * low_multiplier
        high_cost = base_cost * high_multiplier

    When total_area_mm2 is not available for a category, rate_per_unit is
    used directly as a flat minimum cost for that category.

    NOTE: All values below are illustrative starting points, not derived
    from a real cost database, bill of quantities, or regional pricing study.
    Actual repair costs are highly dependent on asset type, location,
    access constraints, labour rates, and material costs.  A quantity
    surveyor or structural cost engineer must review every entry before
    production use.

    Attributes:
        rate_per_unit: Cost per mm² of affected area (or flat cost if no area).
            Units: USD/mm².
        unit: Description of the unit (for human-readable output).
        low_multiplier: Multiplier for the lower bound of the cost range.
        high_multiplier: Multiplier for the upper bound of the cost range.
    """

    rate_per_unit: float   # USD / mm²  (or USD flat when no area data)
    unit: str              # e.g. "mm2", "flat"
    low_multiplier: float  # e.g. 0.8
    high_multiplier: float  # e.g. 1.5


# NOTE: cost rates below are rough illustrative starting points, not derived
# from any real repair cost database or engineering standard.  They are
# intentionally broad to capture the uncertainty in early-stage estimation.
# A qualified cost engineer must review and recalibrate every entry before
# production use.
DEFAULT_COST_RATES: Mapping[DefectCategory, CostRate] = {
    DefectCategory.CRACK: CostRate(
        rate_per_unit=0.05,   # USD/mm² — crack injection / routing and sealing
        unit="mm2",
        low_multiplier=0.7,
        high_multiplier=1.8,
    ),
    DefectCategory.SPALLING: CostRate(
        rate_per_unit=0.08,   # USD/mm² — patch repair / concrete replacement
        unit="mm2",
        low_multiplier=0.7,
        high_multiplier=2.0,
    ),
    DefectCategory.CORROSION: CostRate(
        rate_per_unit=0.10,   # USD/mm² — surface treatment / cathodic protection prep
        unit="mm2",
        low_multiplier=0.8,
        high_multiplier=2.5,
    ),
    DefectCategory.EXPOSED_REINFORCEMENT: CostRate(
        rate_per_unit=0.20,   # USD/mm² — rust removal + concrete reinstatement
        unit="mm2",
        low_multiplier=0.8,
        high_multiplier=2.5,
    ),
    DefectCategory.DELAMINATION: CostRate(
        rate_per_unit=0.07,   # USD/mm² — saw-cut, remove, patch
        unit="mm2",
        low_multiplier=0.7,
        high_multiplier=2.0,
    ),
    DefectCategory.POTHOLE: CostRate(
        rate_per_unit=0.04,   # USD/mm² — road-surface reinstatement
        unit="mm2",
        low_multiplier=0.6,
        high_multiplier=1.5,
    ),
    DefectCategory.SURFACE_DAMAGE: CostRate(
        rate_per_unit=0.03,   # USD/mm² — surface levelling / coating
        unit="mm2",
        low_multiplier=0.6,
        high_multiplier=1.5,
    ),
    DefectCategory.UNKNOWN: CostRate(
        rate_per_unit=0.10,   # USD/mm² — contingency estimate, high uncertainty
        unit="mm2",
        low_multiplier=0.5,
        high_multiplier=3.0,
    ),
}


# ---------------------------------------------------------------------------
# Asset-type cost multipliers
# ---------------------------------------------------------------------------

# NOTE: multipliers below are illustrative relative scaling factors.  They
# encode broad expectations that bridges and dams tend to require higher
# mobilisation and access costs than buildings or roads, but these ratios are
# not calibrated to real project data.  A structural cost engineer must review
# and adjust these values for every deployment context.
ASSET_TYPE_COST_MULTIPLIER: Mapping[AssetType, float] = {
    AssetType.BRIDGE: 1.8,    # high access/mobilization cost, structural criticality
    AssetType.BUILDING: 1.0,  # baseline
    AssetType.TUNNEL: 2.0,    # confined access, specialist equipment
    AssetType.ROAD: 0.8,      # typically lower per-unit repair cost
    AssetType.DAM: 2.5,       # extreme criticality, specialist work, dewatering
    AssetType.PIPELINE: 1.5,  # trench access, service disruption
    AssetType.OTHER: 1.0,     # default to baseline
}


# ---------------------------------------------------------------------------
# Emergency mobilization cost (added when action == EMERGENCY_INTERVENTION)
# ---------------------------------------------------------------------------

# NOTE: emergency mobilization cost below is a flat placeholder range, not
# derived from any real emergency call-out rate schedule.  It covers 24/7
# mobilization, temporary support structures, and expedited material supply.
# A quantity surveyor must establish a project-specific schedule before use.
EMERGENCY_MOBILIZATION_COST = CostRate(
    rate_per_unit=50_000.0,  # USD flat fee for emergency mobilization
    unit="flat",
    low_multiplier=1.0,
    high_multiplier=3.0,
)
