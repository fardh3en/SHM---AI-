"""
Recommendation Service — Phase 5 Orchestration Layer.

Orchestrates RecommendationEngine and CostEstimator to produce a complete
RecommendationReport.  Contains no rule logic or cost formulas — every
calculation is delegated to the responsible engine.

Mirrors the pattern of degradation/service_life.py:
  - Constructor-injected engines with concrete-class defaults (no ABCs yet —
    abstraction will be revisited if a second engine variant, e.g. a
    probabilistic recommender, is ever added).
  - Type hints reference concrete classes directly (not interface types).
  - No business logic; no decision, scoring, classification, or cost logic.

Scope boundary
--------------
This module is an orchestrator only.  It deliberately does NOT:
  - Implement any decision rules or cost formulas.
  - Classify risk or produce maintenance thresholds (upstream layers).
  - Produce multi-point forecasts, portfolio prioritizations, or PDF reports.
  - Import from backend.app.models (ORM decoupling).
  - Persist results (backend layer).

This is the ONLY module in the recommendation/ package that imports both
engine.py and cost_estimator.py — the import-level decoupling constraint
is enforced here by design.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

from recommendation.cost_estimator import CostEstimator
from recommendation.engine import RecommendationEngine
from recommendation.schemas import (
    RecommendationInput,
    RecommendationReport,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecommendationServiceConfig:
    """
    Configuration for a RecommendationService instance.

    Attributes:
        service_version: Recorded in every report's metadata for traceability.
        include_engine_versions: When True, each injected engine's
            _config.engine_version (if present) is captured in metadata.
    """

    service_version: str = "1.0.0"
    include_engine_versions: bool = True


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RecommendationService:
    """
    Lightweight orchestrator for the Phase 5 Recommendation layer.

    Calls RecommendationEngine.decide() then CostEstimator.estimate() exactly
    once each, in that order, and assembles their outputs into a complete
    RecommendationReport.

    Usage — default engines::

        service = RecommendationService()
        report = service.assess(recommendation_input)

    Usage — injected engines (e.g. for testing)::

        service = RecommendationService(
            engine=MyRecommendationEngine(),
            cost_estimator=MyCostEstimator(),
        )
        report = service.assess(recommendation_input)
    """

    def __init__(
        self,
        engine: RecommendationEngine | None = None,
        cost_estimator: CostEstimator | None = None,
        config: RecommendationServiceConfig | None = None,
    ) -> None:
        """
        Args:
            engine: Decision engine. Defaults to RecommendationEngine().
            cost_estimator: Cost estimation engine. Defaults to CostEstimator().
            config: Service-level configuration. Defaults to
                RecommendationServiceConfig().
        """
        self._engine = engine or RecommendationEngine()
        self._cost_estimator = cost_estimator or CostEstimator()
        self._config = config or RecommendationServiceConfig()

    # ── Public API ───────────────────────────────────────────────────────────

    def assess(self, input: RecommendationInput) -> RecommendationReport:
        """
        Produce a complete RecommendationReport.

        Execution order:
          1. RecommendationEngine.decide(input) → RecommendationDecision
          2. CostEstimator.estimate(input, decision) → CostEstimate
          3. Assemble RecommendationReport

        Each engine is called exactly once.

        Args:
            input: Aggregated intelligence from Phase 3 and optionally Phase 4.

        Returns:
            A schema-valid RecommendationReport.
        """
        decision = self._engine.decide(input)
        cost_estimate = self._cost_estimator.estimate(input, decision)
        metadata = self._build_metadata()

        return RecommendationReport(
            asset_id=input.asset_id,
            inspection_id=input.inspection_id,
            decision=decision,
            cost_estimate=cost_estimate,
            metadata=metadata,
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _build_metadata(self) -> dict[str, Any]:
        """
        Assemble report metadata for traceability.

        Mirrors ServiceLifeEstimator._build_metadata() in style.
        """
        meta: dict[str, Any] = {
            "service": "RecommendationService",
            "service_version": self._config.service_version,
            "assessed_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        }

        if self._config.include_engine_versions:
            meta["engine_versions"] = self._collect_engine_versions()

        return meta

    def _collect_engine_versions(self) -> dict[str, str]:
        """
        Best-effort collection of engine version strings.

        Reads _config.engine_version where present; silently omits engines
        without this attribute (e.g. test doubles).

        Mirrors ServiceLifeEstimator._collect_engine_versions() exactly.
        """
        versions: dict[str, str] = {}
        engines: dict[str, object] = {
            "recommendation_engine": self._engine,
            "cost_estimator": self._cost_estimator,
        }
        for name, engine in engines.items():
            cfg = getattr(engine, "_config", None)
            if cfg is not None:
                version = getattr(cfg, "engine_version", None)
                if isinstance(version, str):
                    versions[name] = version
        return versions
