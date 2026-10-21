"""
Phase 5 Recommendation Decision Engine — I/O Schemas.

Pydantic v2 domain models for the recommendation pipeline.
Mirrors the style and constraints of intelligence/schemas.py and
degradation/schemas.py:
  - No ORM imports.
  - No business logic, scoring algorithms, or rule logic.
  - Pure data containers with field-level documentation.

Cross-package references
------------------------
AssetType, HealthAssessmentReport, FailureModeCategory are imported from
intelligence.schemas because intelligence/ is the canonical upstream domain
layer for those concepts.
DegradationAssessmentReport is imported from degradation.schemas as the
Phase 4 output that feeds optionally into this phase.

Scope boundary
--------------
This module defines I/O contracts only.  It does NOT:
  - Import from backend.app.models (ORM decoupling).
  - Contain any decision logic, scoring, or cost formulas.
  - Define cost fields on RecommendationDecision — cost data belongs
    exclusively on CostEstimate and RecommendationReport (engine/cost
    separation is a hard architectural constraint of Phase 5).
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from degradation.schemas import DegradationAssessmentReport  # noqa: TC001
from intelligence.schemas import (  # noqa: TC001
    AssetType,
    FailureModeCategory,
    HealthAssessmentReport,
)

# ── Action enum ───────────────────────────────────────────────────────────────


class RecommendedActionType(StrEnum):
    """
    Ordered set of recommended maintenance actions.

    Ordinal rank increases with urgency:
      MONITOR < INSPECT < REPAIR < EMERGENCY_INTERVENTION

    Escalation within the recommendation engine is strictly monotonic —
    an action tier may be raised (never lowered) by each decision stage.
    """

    MONITOR = "monitor"
    INSPECT = "inspect"
    REPAIR = "repair"
    EMERGENCY_INTERVENTION = "emergency_intervention"


# ── Input schema ──────────────────────────────────────────────────────────────


class RecommendationInput(BaseModel):
    """
    Aggregated input required to produce a RecommendationReport for a single
    inspection of a single asset.

    The degradation_report field is explicitly Optional because not every
    asset will have completed a Phase 4 degradation assessment.  When absent,
    the engine falls back to a risk-level-baseline-only decision with no error.
    """

    asset_id: str
    inspection_id: str
    asset_type: AssetType
    health_report: HealthAssessmentReport
    degradation_report: DegradationAssessmentReport | None = Field(
        default=None,
        description=(
            "Phase 4 degradation assessment result. When None the recommendation engine "
            "produces a risk-level-baseline-only decision without error."
        ),
    )


# ── Escalation trace ──────────────────────────────────────────────────────────


class EscalationTrace(BaseModel):
    """
    Audit record documenting which escalation stages fired during a
    RecommendationEngine.decide() call.

    Useful for explainability and debugging — records exactly which signals
    pushed the final action above the baseline.
    """

    baseline_action: RecommendedActionType = Field(
        description="Action derived from the health_report.risk_level before any escalation."
    )
    degradation_escalation_applied: bool = Field(
        description=(
            "True if Stage 2 (degradation report requires_maintenance) raised the action "
            "above the baseline."
        )
    )
    failure_mode_escalation_applied: bool = Field(
        description=(
            "True if Stage 3 (critical failure mode detection) raised the action to "
            "EMERGENCY_INTERVENTION."
        )
    )
    triggering_failure_modes: list[FailureModeCategory] = Field(
        default_factory=list,
        description=(
            "FailureModeCategories that triggered Stage 3 escalation. Empty unless "
            "failure_mode_escalation_applied is True."
        ),
    )


# ── Decision (NO cost field — this is deliberate and must not be added) ───────


class RecommendationDecision(BaseModel):
    """
    Output of RecommendationEngine.decide().

    IMPORTANT — cost separation constraint
    ---------------------------------------
    This class intentionally contains NO cost-related fields.  Cost data
    belongs exclusively on CostEstimate, assembled downstream by CostEstimator.
    This separation is a hard architectural constraint: the decision engine
    must not know about or depend on cost logic, and CostEstimator must not
    be able to influence or mutate the decision.

    Any future addition of a cost field to this class is a design violation
    and will be caught by the structural-decoupling test in
    tests/unit/test_recommendation_engine.py.
    """

    recommended_action: RecommendedActionType = Field(
        description="Final recommended maintenance action after all escalation stages."
    )
    escalation: EscalationTrace = Field(
        description="Audit trace documenting which escalation stages fired."
    )
    next_inspection_interval_years: float = Field(
        gt=0.0,
        description=(
            "Recommended interval in years before the next inspection, "
            "looked up from the final (post-escalation) action tier's rule entry."
        ),
    )


# ── Cost estimate (populated separately by CostEstimator) ────────────────────


class CostEstimate(BaseModel):
    """
    Cost range estimate produced by CostEstimator.estimate().

    Intentionally separate from RecommendationDecision to enforce the
    architectural constraint that the decision engine has no knowledge of
    cost logic and CostEstimator cannot influence the decision.
    """

    low: float = Field(
        ge=0.0,
        description="Lower bound of the estimated intervention cost in ``currency``.",
    )
    high: float = Field(
        ge=0.0,
        description="Upper bound of the estimated intervention cost in ``currency``.",
    )
    currency: str = Field(
        default="USD",
        description="ISO 4217 currency code for low/high values.",
    )
    basis: str = Field(
        description=(
            "Human-readable one-line summary of what drove the cost range "
            "(e.g. which defect categories contributed, whether emergency "
            "mobilization was added, asset-type multiplier applied)."
        )
    )


# ── Top-level report (assembled by RecommendationService) ─────────────────────


class RecommendationReport(BaseModel):
    """
    Complete output of the Phase 5 Recommendation layer for a single
    inspection of a single asset.

    Assembled by RecommendationService from the outputs of
    RecommendationEngine (decision) and CostEstimator (cost_estimate).
    Contains no business logic — pure data container.
    """

    asset_id: str
    inspection_id: str
    decision: RecommendationDecision = Field(
        description="Recommended action and escalation audit trace from RecommendationEngine."
    )
    cost_estimate: CostEstimate = Field(
        description="Cost range estimate from CostEstimator."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Free-form supplementary data about the assessment run "
            "(e.g. service name/version, timestamp, engine_versions). "
            "Not intended for structural decision-making."
        ),
    )
