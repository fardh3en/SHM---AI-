"""
Recommendation Engine — Phase 5 Decision Logic.

Deterministic, configuration-driven engine that maps health and degradation
intelligence to a recommended maintenance action.  Produces a
RecommendationDecision with a full escalation audit trace.

Scope boundary
--------------
This module is responsible ONLY for deciding WHAT action to recommend and
WHEN the next inspection should occur.  It deliberately does NOT:
  - Estimate costs — that is CostEstimator's sole responsibility.
  - Import cost_estimator.py — the import-level decoupling is enforced
    architecturally (only RecommendationService imports both).
  - Produce multi-point forecasts, portfolio prioritizations, or PDF reports.
  - Import from backend.app.models (ORM decoupling).

Assessment strategy
-------------------
The decision is computed in three ordered stages, each of which can ONLY
raise (never lower) the recommended action:

  Stage 1 – Risk-level baseline
    Look up health_report.risk_level in DEFAULT_RECOMMENDATION_RULES to
    obtain the baseline RecommendedActionType.

  Stage 2 – Degradation escalation
    If a DegradationAssessmentReport is available and its
    ``requires_maintenance`` flag is True, and the current action is below
    REPAIR in ordinal rank, escalate to REPAIR.  When degradation_report is
    None this stage is skipped entirely with no error.

  Stage 3 – Failure-mode escalation
    Scan health_report.failure_modes for modes whose category is in the
    configured ``escalation_trigger_modes`` set AND whose confidence meets or
    exceeds ``confidence_threshold``.  If any such mode is found and the
    current action is below EMERGENCY_INTERVENTION, escalate to
    EMERGENCY_INTERVENTION and populate triggering_failure_modes.

The next_inspection_interval_years in the output is looked up from the
FINAL (post-escalation) action tier — not from the baseline action.
"""
from __future__ import annotations

from collections.abc import Mapping  # noqa: TC003
from dataclasses import dataclass, field

from intelligence.schemas import FailureModeCategory, RiskLevel  # noqa: TC001
from recommendation.config import (
    ACTION_TO_INTERVAL,
    DEFAULT_FAILURE_MODE_ESCALATION,
    DEFAULT_RECOMMENDATION_RULES,
    FailureModeEscalationConfig,
    RecommendationRule,
)
from recommendation.schemas import (
    EscalationTrace,
    RecommendationDecision,
    RecommendationInput,
    RecommendedActionType,
)

# ---------------------------------------------------------------------------
# Action-level ordering helpers (mirrors _RISK_RANK in risk_engine.py)
# ---------------------------------------------------------------------------

_ACTION_RANK: dict[RecommendedActionType, int] = {
    RecommendedActionType.MONITOR: 0,
    RecommendedActionType.INSPECT: 1,
    RecommendedActionType.REPAIR: 2,
    RecommendedActionType.EMERGENCY_INTERVENTION: 3,
}

_RANK_TO_ACTION: dict[int, RecommendedActionType] = {
    v: k for k, v in _ACTION_RANK.items()
}


def _max_action(
    a: RecommendedActionType, b: RecommendedActionType
) -> RecommendedActionType:
    """Return whichever action is of higher or equal urgency."""
    return _RANK_TO_ACTION[max(_ACTION_RANK[a], _ACTION_RANK[b])]


def _action_below(
    a: RecommendedActionType, b: RecommendedActionType
) -> bool:
    """True if action ``a`` is strictly less urgent than action ``b``."""
    return _ACTION_RANK[a] < _ACTION_RANK[b]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecommendationEngineConfig:
    """
    Full configuration for a RecommendationEngine instance.

    Every threshold and rule set is exposed here so the engine can be retuned
    without code changes — supply a custom config on construction.

    Attributes:
        rules: Mapping from RiskLevel to RecommendationRule (action + interval).
            Defaults to DEFAULT_RECOMMENDATION_RULES.
        failure_mode_escalation: Stage 3 failure-mode escalation config.
            Defaults to DEFAULT_FAILURE_MODE_ESCALATION.
        engine_version: Recorded in RecommendationReport metadata for
            traceability.
    """

    rules: Mapping[RiskLevel, RecommendationRule] = field(
        default_factory=lambda: DEFAULT_RECOMMENDATION_RULES
    )
    failure_mode_escalation: FailureModeEscalationConfig = field(
        default_factory=lambda: DEFAULT_FAILURE_MODE_ESCALATION
    )
    engine_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RecommendationEngine:
    """
    Deterministic, configurable recommendation decision engine.

    Produces a RecommendationDecision from a RecommendationInput using a
    three-stage monotonic escalation strategy.  See module docstring for
    the full strategy description.

    Scope boundary: this class produces ONLY RecommendationDecision — no
    cost estimation, no forecasting, no PDF generation, no ORM access.
    It never imports cost_estimator.py.

    Usage — default configuration::

        engine = RecommendationEngine()
        decision = engine.decide(recommendation_input)

    Usage — custom configuration::

        config = RecommendationEngineConfig(engine_version="2.0.0")
        engine = RecommendationEngine(config=config)
        decision = engine.decide(recommendation_input)
    """

    def __init__(self, config: RecommendationEngineConfig | None = None) -> None:
        """
        Args:
            config: Engine configuration. Defaults to RecommendationEngineConfig().
        """
        self._config = config or RecommendationEngineConfig()

    # ── Public API ───────────────────────────────────────────────────────────

    def decide(self, input: RecommendationInput) -> RecommendationDecision:
        """
        Produce a RecommendationDecision for a single inspection.

        Applies three strictly-monotonic escalation stages.  Each stage can
        only raise (never lower) the recommended action.

        Args:
            input: Aggregated intelligence from Phase 3 and optionally Phase 4.

        Returns:
            A schema-valid RecommendationDecision with full escalation trace.
        """
        # Stage 1: risk-level baseline
        baseline_action = self._stage1_baseline(input)
        current_action = baseline_action

        # Stage 2: degradation escalation
        current_action, degradation_escalated = self._stage2_degradation(
            current_action, input
        )

        # Stage 3: failure-mode escalation
        current_action, fm_escalated, triggering_modes = self._stage3_failure_mode(
            current_action, input
        )

        # Look up the next inspection interval from the FINAL action tier.
        interval = self._interval_for_action(current_action)

        return RecommendationDecision(
            recommended_action=current_action,
            escalation=EscalationTrace(
                baseline_action=baseline_action,
                degradation_escalation_applied=degradation_escalated,
                failure_mode_escalation_applied=fm_escalated,
                triggering_failure_modes=triggering_modes,
            ),
            next_inspection_interval_years=interval,
        )

    # ── Stage implementations ────────────────────────────────────────────────

    def _stage1_baseline(self, input: RecommendationInput) -> RecommendedActionType:
        """
        Stage 1: look up the baseline action from risk_level.

        Raises KeyError if the RiskLevel is not in the configured rules table —
        this is a configuration error and should propagate loudly.
        """
        return self._config.rules[input.health_report.risk_level].action

    def _stage2_degradation(
        self,
        current: RecommendedActionType,
        input: RecommendationInput,
    ) -> tuple[RecommendedActionType, bool]:
        """
        Stage 2: escalate to REPAIR when degradation report flags maintenance.

        Gracefully skips (no error) when degradation_report is None — not
        every asset will have a Phase 4 result at the time of recommendation.

        Returns:
            Tuple of (updated_action, escalation_applied_flag).
        """
        if input.degradation_report is None:
            return current, False

        if not input.degradation_report.requires_maintenance:
            return current, False

        if not _action_below(current, RecommendedActionType.REPAIR):
            # Already at REPAIR or above — no change needed, but we still note
            # that the degradation signal was present (flag stays False because
            # no actual escalation was applied — the action was already sufficient).
            return current, False

        return RecommendedActionType.REPAIR, True

    def _stage3_failure_mode(
        self,
        current: RecommendedActionType,
        input: RecommendationInput,
    ) -> tuple[RecommendedActionType, bool, list[FailureModeCategory]]:
        """
        Stage 3: escalate to EMERGENCY_INTERVENTION on critical failure modes.

        Scans health_report.failure_modes for entries whose category is in the
        escalation_trigger_modes set AND whose confidence meets or exceeds
        confidence_threshold.  If any are found and current action is below
        EMERGENCY_INTERVENTION, escalates.

        Returns:
            Tuple of (updated_action, escalation_applied_flag, triggering_modes).
        """
        escalation_cfg = self._config.failure_mode_escalation
        triggering: list[FailureModeCategory] = []

        for mode in input.health_report.failure_modes:
            if (
                mode.category in escalation_cfg.escalation_trigger_modes
                and mode.confidence >= escalation_cfg.confidence_threshold
            ):
                triggering.append(mode.category)

        if not triggering:
            return current, False, []

        if not _action_below(current, RecommendedActionType.EMERGENCY_INTERVENTION):
            # Already at EMERGENCY_INTERVENTION — collect triggering modes for
            # the audit trace but don't flag escalation_applied since the action
            # didn't change.
            return current, False, triggering

        return RecommendedActionType.EMERGENCY_INTERVENTION, True, triggering

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _interval_for_action(self, action: RecommendedActionType) -> float:
        """
        Look up next_inspection_interval_years for the given action tier.

        Uses ACTION_TO_INTERVAL from config (derived from DEFAULT_RECOMMENDATION_RULES)
        as the canonical mapping.  For custom-config engines that override ``rules``,
        we fall back to re-deriving the interval from ``self._config.rules`` if the
        action is found there, otherwise use ACTION_TO_INTERVAL.
        """
        # Prefer the configured rules' action-to-interval mapping for this instance.
        for risk_level, rule in self._config.rules.items():  # noqa: B007
            if rule.action == action:
                return rule.next_inspection_interval_years
        # Fallback to the module-level constant (handles edge cases with custom configs).
        return ACTION_TO_INTERVAL[action]
