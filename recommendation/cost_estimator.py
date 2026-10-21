"""
Cost Estimator — Phase 5 Intervention Cost Estimation.

Produces a CostEstimate (low/high range + human-readable basis) from a
RecommendationInput and a RecommendationDecision.  Contains no decision
logic — that is exclusively the responsibility of RecommendationEngine.

Scope boundary
--------------
This module is responsible ONLY for estimating the monetary cost of the
recommended intervention.  It deliberately does NOT:
  - Import engine.py — the import-level decoupling is enforced
    architecturally (only RecommendationService imports both).
  - Construct, mutate, or return a RecommendationDecision.
  - Implement any maintenance-action decision logic.
  - Import from backend.app.models (ORM decoupling).
  - Produce PDF reports, forecasts, or portfolio prioritizations.

The CostEstimator may READ a RecommendationDecision (e.g. to determine
whether emergency mobilization cost applies) but has no way to influence
the decision — it only receives a finished decision object as an argument.

Cost model
----------
For each DefectCategory present in health_report.severity_breakdown:

  1. Retrieve the CostRate for that category from the configured cost_rates
     table.
  2. If total_area_mm2 is available on the DefectSeverityBreakdown entry,
     compute:
         base_cost = rate_per_unit * total_area_mm2
     Otherwise use rate_per_unit directly as a flat minimum cost.
  3. Apply low_multiplier / high_multiplier to obtain the range for that
     category.
  4. Sum across all categories.
  5. Scale by asset_multipliers[input.asset_type].
  6. If decision.recommended_action == EMERGENCY_INTERVENTION, add the
     flat emergency mobilization cost range on top (after asset scaling).

All values are in USD (currency field on CostEstimate).
"""
from __future__ import annotations

from collections.abc import Mapping  # noqa: TC003
from dataclasses import dataclass, field

from intelligence.schemas import AssetType, DefectCategory  # noqa: TC001
from recommendation.config import (
    ASSET_TYPE_COST_MULTIPLIER,
    DEFAULT_COST_RATES,
    EMERGENCY_MOBILIZATION_COST,
    CostRate,
)
from recommendation.schemas import (
    CostEstimate,
    RecommendationDecision,
    RecommendationInput,
    RecommendedActionType,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CostEstimatorConfig:
    """
    Full configuration for a CostEstimator instance.

    Attributes:
        cost_rates: Per-DefectCategory cost rates.
        asset_multipliers: Per-AssetType scaling multipliers.
        emergency_cost: Flat cost range added for EMERGENCY_INTERVENTION.
        engine_version: Recorded in RecommendationReport metadata for
            traceability.
    """

    cost_rates: Mapping[DefectCategory, CostRate] = field(
        default_factory=lambda: DEFAULT_COST_RATES
    )
    asset_multipliers: Mapping[AssetType, float] = field(
        default_factory=lambda: ASSET_TYPE_COST_MULTIPLIER
    )
    emergency_cost: CostRate = field(
        default_factory=lambda: EMERGENCY_MOBILIZATION_COST
    )
    engine_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------


class CostEstimator:
    """
    Deterministic, configuration-driven cost estimator for Phase 5.

    Reads RecommendationInput (for defect breakdown and asset type) and
    RecommendationDecision (to check for emergency mobilization) to produce a
    CostEstimate range.  Never constructs or returns a RecommendationDecision.

    Scope boundary: this class produces ONLY CostEstimate — no decision
    logic, no forecasting, no PDF generation, no ORM access.
    It never imports engine.py.

    Usage — default configuration::

        estimator = CostEstimator()
        cost = estimator.estimate(recommendation_input, decision)

    Usage — custom configuration::

        config = CostEstimatorConfig(engine_version="2.0.0")
        estimator = CostEstimator(config=config)
        cost = estimator.estimate(recommendation_input, decision)
    """

    def __init__(self, config: CostEstimatorConfig | None = None) -> None:
        """
        Args:
            config: Estimator configuration. Defaults to CostEstimatorConfig().
        """
        self._config = config or CostEstimatorConfig()

    # ── Public API ───────────────────────────────────────────────────────────

    def estimate(
        self,
        input: RecommendationInput,
        decision: RecommendationDecision,
    ) -> CostEstimate:
        """
        Produce a CostEstimate for the recommended intervention.

        Reads decision.recommended_action to determine whether emergency
        mobilization cost applies.  Does not mutate or return decision.

        Args:
            input: RecommendationInput with defect breakdown and asset type.
            decision: Completed RecommendationDecision from RecommendationEngine.
                Read-only; this method does not mutate or return it.

        Returns:
            A CostEstimate with low/high range, currency, and human-readable
            basis string.
        """
        defect_low, defect_high, categories_used = self._sum_defect_costs(input)

        asset_multiplier = self._config.asset_multipliers.get(input.asset_type, 1.0)
        scaled_low = defect_low * asset_multiplier
        scaled_high = defect_high * asset_multiplier

        emergency_applied = (
            decision.recommended_action == RecommendedActionType.EMERGENCY_INTERVENTION
        )
        if emergency_applied:
            emg = self._config.emergency_cost
            scaled_low += emg.rate_per_unit * emg.low_multiplier
            scaled_high += emg.rate_per_unit * emg.high_multiplier

        basis = self._build_basis(
            categories_used=categories_used,
            asset_type=input.asset_type,
            asset_multiplier=asset_multiplier,
            emergency_applied=emergency_applied,
        )

        return CostEstimate(
            low=round(scaled_low, 2),
            high=round(scaled_high, 2),
            currency="USD",
            basis=basis,
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _sum_defect_costs(
        self, input: RecommendationInput
    ) -> tuple[float, float, list[str]]:
        """
        Compute the raw (pre-asset-multiplier) cost range from defect breakdown.

        Returns:
            Tuple of (total_low, total_high, list_of_category_names_used).
        """
        total_low = 0.0
        total_high = 0.0
        categories_used: list[str] = []

        for breakdown in input.health_report.severity_breakdown:
            category = breakdown.defect_category
            rate = self._config.cost_rates.get(category)
            if rate is None:
                # No rate configured for this category — skip silently.
                continue

            if breakdown.total_area_mm2 is not None and breakdown.total_area_mm2 > 0.0:
                base_cost = rate.rate_per_unit * breakdown.total_area_mm2
            else:
                # No area data: use the flat rate_per_unit directly.
                base_cost = rate.rate_per_unit

            total_low += base_cost * rate.low_multiplier
            total_high += base_cost * rate.high_multiplier
            categories_used.append(category.value)

        return total_low, total_high, categories_used

    @staticmethod
    def _build_basis(
        categories_used: list[str],
        asset_type: AssetType,
        asset_multiplier: float,
        emergency_applied: bool,
    ) -> str:
        """
        Build a human-readable one-line basis string.

        Summarises the defect categories included, asset-type multiplier,
        and whether emergency mobilization cost was added.
        """
        parts: list[str] = []

        if categories_used:
            cats = ", ".join(categories_used)
            parts.append(f"defect categories: [{cats}]")
        else:
            parts.append("no defect area data — zero base cost")

        parts.append(f"asset_type={asset_type.value} (×{asset_multiplier:.2f})")

        if emergency_applied:
            parts.append("+ emergency mobilization")

        return "; ".join(parts)
