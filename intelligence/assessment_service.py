"""
Assessment Service — Integration Layer.

Orchestrates the four Phase 3 intelligence engines to produce a complete
HealthAssessmentReport from a single HealthAssessmentInput.  This module
contains *no* business logic: every decision is delegated to the engine
responsible for it.

Scope boundary
--------------
AssessmentService deliberately does NOT:

  - Compute health scores (IHealthScorer's responsibility).
  - Classify defect severities (ISeverityClassifier's responsibility).
  - Identify structural failure modes (IEngineeringRulesEngine's).
  - Determine overall risk (IRiskEngine's).
  - Generate maintenance recommendations (Phase 5).
  - Persist results or expose HTTP endpoints (backend layer).

It ONLY:

  - Accepts a HealthAssessmentInput.
  - Calls each engine exactly once in the defined order.
  - Passes outputs between engines where appropriate.
  - Assembles and returns a schema-valid HealthAssessmentReport.

Execution order
---------------
HealthAssessmentInput
    │
    ├─► IHealthScorer.calculate_score()         → health_score: float
    │
    ├─► ISeverityClassifier.classify()          → severity_breakdown
    │
    ├─► IEngineeringRulesEngine.identify_failure_modes()  → failure_modes
    │
    └─► IRiskEngine  ──────────────────────────────────────────────────►
            • RiskEngine.assess() if the concrete engine supports it
              (passes all three outputs for richer four-stage synthesis)
            • IRiskEngine.determine_risk_level() otherwise
                                                → risk_level: RiskLevel
    │
    ▼
HealthAssessmentReport

Dependency injection
--------------------
All four engines are injected via the constructor, defaulting to the
concrete implementations shipped in Phase 3.  Swap any engine by passing
an alternative implementation — including test doubles.

    service = AssessmentService()                          # defaults
    service = AssessmentService(scorer=MyCustomScorer())   # partial override
    service = AssessmentService(
        scorer=MockScorer(),
        classifier=MockClassifier(),
        rules_engine=MockRulesEngine(),
        risk_engine=MockRiskEngine(),
    )

RiskEngine.assess() integration
--------------------------------
The concrete RiskEngine exposes an ``assess()`` method that synthesises all
three intelligence outputs for a richer four-stage risk assessment.  This
method is NOT on the IRiskEngine interface (which only guarantees
``determine_risk_level()``).  AssessmentService uses it when the injected
engine is a RiskEngine instance; otherwise it falls back gracefully to the
interface contract.  Injecting a custom IRiskEngine that does not implement
``assess()`` is fully supported and produces a valid (score-only) report.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from intelligence.engineering_rules import EngineeringRulesEngine
from intelligence.risk_engine import RiskEngine
from intelligence.schemas import (
    DefectSeverityBreakdown,
    HealthAssessmentInput,
    HealthAssessmentReport,
    RiskLevel,
    StructuralFailureMode,
)
from intelligence.scoring.health_scorer import HealthScorer
from intelligence.severity_classifier import SeverityClassifier

if TYPE_CHECKING:
    from intelligence.interfaces import (
        IEngineeringRulesEngine,
        IHealthScorer,
        IRiskEngine,
        ISeverityClassifier,
    )


# ---------------------------------------------------------------------------
# Service configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssessmentServiceConfig:
    """
    Configuration for an AssessmentService instance.

    Attributes:
        service_version: Recorded in every report's metadata for traceability.
        include_engine_versions: When True, the version string of each
            concrete engine is captured in report metadata (best-effort —
            engines without a ``_config.engine_version`` attribute are
            skipped gracefully).
    """

    service_version: str = "1.0.0"
    include_engine_versions: bool = True


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AssessmentService:
    """
    Lightweight orchestrator for the Phase 3 Structural Health Intelligence
    layer.

    Coordinates the four intelligence engines in the correct sequence and
    assembles their outputs into a complete, schema-valid
    HealthAssessmentReport.  Contains no scoring, classification, rule, or
    risk logic of its own.

    Usage — default engines::

        service = AssessmentService()
        report  = service.assess(assessment_input)

    Usage — injected engines (e.g. for testing)::

        service = AssessmentService(
            scorer=MockScorer(),
            classifier=MockClassifier(),
            rules_engine=MockRulesEngine(),
            risk_engine=MockRiskEngine(),
        )
        report = service.assess(assessment_input)
    """

    def __init__(
        self,
        scorer: IHealthScorer | None = None,
        classifier: ISeverityClassifier | None = None,
        rules_engine: IEngineeringRulesEngine | None = None,
        risk_engine: IRiskEngine | None = None,
        config: AssessmentServiceConfig | None = None,
    ) -> None:
        """
        Args:
            scorer: Health scoring engine.  Defaults to HealthScorer().
            classifier: Severity classification engine.  Defaults to
                SeverityClassifier().
            rules_engine: Engineering rules engine.  Defaults to
                EngineeringRulesEngine().
            risk_engine: Risk assessment engine.  Defaults to RiskEngine().
                If the injected engine is a concrete RiskEngine, its
                ``assess()`` method is used for richer synthesis; otherwise
                ``determine_risk_level()`` is used.
            config: Service-level configuration.  Defaults to
                AssessmentServiceConfig().
        """
        self._scorer: IHealthScorer = scorer or HealthScorer()
        self._classifier: ISeverityClassifier = classifier or SeverityClassifier()
        self._rules_engine: IEngineeringRulesEngine = rules_engine or EngineeringRulesEngine()
        self._risk_engine: IRiskEngine = risk_engine or RiskEngine()
        self._config = config or AssessmentServiceConfig()

    # ── Public API ──────────────────────────────────────────────────────────

    def assess(self, assessment_input: HealthAssessmentInput) -> HealthAssessmentReport:
        """
        Produce a complete HealthAssessmentReport for one inspection.

        Engines are called exactly once each, in the defined execution order.
        No engine output is discarded; all are forwarded to the report.

        Args:
            assessment_input: Aggregated defect observations and asset context
                for a single inspection of a single asset.

        Returns:
            A schema-valid HealthAssessmentReport containing the health score,
            risk level, per-category severity breakdown, identified structural
            failure modes, and execution metadata.
        """
        # Stage 1 — health score
        health_score: float = self._scorer.calculate_score(assessment_input)

        # Stage 2 — per-category severity breakdown
        severity_breakdown: list[DefectSeverityBreakdown] = self._classifier.classify(
            assessment_input
        )

        # Stage 3 — structural failure modes
        failure_modes: list[StructuralFailureMode] = self._rules_engine.identify_failure_modes(
            assessment_input
        )

        # Stage 4 — overall risk level
        risk_level: RiskLevel = self._determine_risk(
            health_score, severity_breakdown, failure_modes
        )

        # Assemble report
        metadata = self._build_metadata(assessment_input)

        return HealthAssessmentReport(
            asset_id=assessment_input.asset_id,
            inspection_id=assessment_input.inspection_id,
            health_score=health_score,
            risk_level=risk_level,
            severity_breakdown=severity_breakdown,
            failure_modes=failure_modes,
            metadata=metadata,
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _determine_risk(
        self,
        health_score: float,
        severity_breakdown: list[DefectSeverityBreakdown],
        failure_modes: list[StructuralFailureMode],
    ) -> RiskLevel:
        """
        Delegate risk determination to the injected IRiskEngine.

        Uses RiskEngine.assess() when the injected engine is a concrete
        RiskEngine instance (richer four-stage synthesis using all three
        intelligence outputs).  Falls back to the interface-mandated
        determine_risk_level() for any other IRiskEngine implementation.

        This keeps the orchestration decoupled from the risk engine's
        internal API: custom IRiskEngine implementations injected in tests
        or future milestones are always supported.
        """
        if isinstance(self._risk_engine, RiskEngine):
            return self._risk_engine.assess(
                health_score=health_score,
                severity_breakdown=severity_breakdown,
                failure_modes=failure_modes,
            )
        return self._risk_engine.determine_risk_level(health_score)

    def _build_metadata(
        self, assessment_input: HealthAssessmentInput
    ) -> dict[str, Any]:
        """
        Assemble minimal, deterministic report metadata.

        Metadata is informational only and is NOT used for any structural
        decision-making.  It records which engine versions produced the
        report, the UTC timestamp at assessment time, and summary counts
        that may be useful for diagnostics.
        """
        meta: dict[str, Any] = {
            "service": "AssessmentService",
            "service_version": self._config.service_version,
            "assessed_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "observation_count": len(assessment_input.observations),
            "asset_type": assessment_input.asset_type,
        }

        if assessment_input.asset_age_years is not None:
            meta["asset_age_years"] = assessment_input.asset_age_years

        if self._config.include_engine_versions:
            meta["engine_versions"] = self._collect_engine_versions()

        return meta

    def _collect_engine_versions(self) -> dict[str, str]:
        """
        Best-effort collection of engine version strings from each component.

        Reads the ``_config.engine_version`` attribute where present.
        Engines without this attribute (e.g. test doubles) are silently
        omitted — this is metadata only and must not affect the report's
        structural outputs.
        """
        versions: dict[str, str] = {}
        engines: dict[str, object] = {
            "scorer": self._scorer,
            "classifier": self._classifier,
            "rules_engine": self._rules_engine,
            "risk_engine": self._risk_engine,
        }
        for name, engine in engines.items():
            cfg = getattr(engine, "_config", None)
            if cfg is not None:
                version = getattr(cfg, "engine_version", None)
                if isinstance(version, str):
                    versions[name] = version
        return versions
