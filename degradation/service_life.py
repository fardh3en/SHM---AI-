"""
Service Life Estimator — Phase 4 Material Degradation Integration Layer.

Orchestrates CarbonationModel and CorrosionModel to produce a complete
DegradationAssessmentReport.  Contains no physics formulas — every
calculation is delegated to the responsible engine.

Mirrors the pattern of intelligence/assessment_service.py:
  - Constructor-injected engines with concrete-class defaults (no ABCs yet —
    abstraction will be revisited when a third mechanism, e.g. chloride,
    is added).
  - Type hints reference concrete classes directly (not interface types)
    because no IXxx ABC exists for Phase 4 engines.
  - No business logic; no scoring, classification, or rule logic.

Scope boundary
--------------
This module is an orchestrator only.  It deliberately does NOT:
  - Implement any physics formulas (CarbonationModel / CorrosionModel do
    that).
  - Classify risk or recommend maintenance (IRiskEngine / Phase 5).
  - Produce multi-point forecast time-series (out of scope for Phase 4).
  - Import from backend.app.models (ORM decoupling).
  - Persist results (backend layer).

NOTE: all thresholds used in maintenance flag metadata come from
MaintenanceThreshold in degradation/config.py and are configurable.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

from degradation.carbonation import CarbonationModel
from degradation.config import DEFAULT_MAINTENANCE_THRESHOLD, MaintenanceThreshold
from degradation.corrosion import CorrosionModel
from degradation.schemas import (
    CarbonationProjection,
    CorrosionProjection,
    DegradationAssessmentInput,
    DegradationAssessmentReport,
    InitiationStatus,
    MaintenanceDecision,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceLifeEstimatorConfig:
    """
    Configuration for a ServiceLifeEstimator instance.

    Attributes:
        maintenance_threshold: Thresholds used to evaluate maintenance intervention.
        service_version: Recorded in every report's metadata for traceability.
        include_engine_versions: When True, each injected engine's
            _config.engine_version (if present) is captured in metadata.
    """

    maintenance_threshold: MaintenanceThreshold = field(
        default_factory=lambda: DEFAULT_MAINTENANCE_THRESHOLD
    )
    service_version: str = "1.0.0"
    include_engine_versions: bool = True


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------


class ServiceLifeEstimator:
    """
    Lightweight orchestrator for the Phase 4 Material Degradation layer.

    Calls CarbonationModel then CorrosionModel exactly once each, in the
    defined order, evaluates maintenance thresholds into a typed
    MaintenanceDecision, and assembles their outputs into a complete
    DegradationAssessmentReport.

    Usage — default engines::

        estimator = ServiceLifeEstimator()
        report = estimator.assess(degradation_input)

    Usage — injected engines (e.g. for testing)::

        estimator = ServiceLifeEstimator(
            carbonation_model=MyCarbonationModel(),
            corrosion_model=MyCorrosionModel(),
        )
        report = estimator.assess(degradation_input)
    """

    def __init__(
        self,
        carbonation_model: CarbonationModel | None = None,
        corrosion_model: CorrosionModel | None = None,
        config: ServiceLifeEstimatorConfig | None = None,
    ) -> None:
        """
        Args:
            carbonation_model: Carbonation depth engine. Defaults to
                CarbonationModel().
            corrosion_model: Corrosion propagation engine. Defaults to
                CorrosionModel().
            config: Estimator-level configuration. Defaults to
                ServiceLifeEstimatorConfig().
        """
        self._carbonation_model = carbonation_model or CarbonationModel()
        self._corrosion_model = corrosion_model or CorrosionModel()
        self._config = config or ServiceLifeEstimatorConfig()

    # ── Public API ──────────────────────────────────────────────────────────

    def assess(
        self, assessment_input: DegradationAssessmentInput
    ) -> DegradationAssessmentReport:
        """
        Produce a complete DegradationAssessmentReport.

        Execution order:
          1. CarbonationModel.predict() → CarbonationProjection
          2. CorrosionModel.predict(carbonation) → CorrosionProjection
          3. Evaluate MaintenanceDecision
          4. Assemble DegradationAssessmentReport

        Each engine is called exactly once.

        Args:
            assessment_input: Aggregated asset and material data.

        Returns:
            A schema-valid DegradationAssessmentReport.
        """
        carbonation = self._carbonation_model.predict(assessment_input)
        corrosion = self._corrosion_model.predict(assessment_input, carbonation)
        maintenance_decision = self._evaluate_maintenance(
            assessment_input, carbonation, corrosion
        )
        metadata = self._build_metadata(assessment_input)

        return DegradationAssessmentReport(
            asset_id=assessment_input.asset_id,
            inspection_id=assessment_input.inspection_id,
            carbonation=carbonation,
            corrosion=corrosion,
            maintenance_decision=maintenance_decision,
            metadata=metadata,
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _evaluate_maintenance(
        self,
        assessment_input: DegradationAssessmentInput,
        carbonation: CarbonationProjection,
        corrosion: CorrosionProjection,
    ) -> MaintenanceDecision:
        """
        Evaluate degradation projections and observed signals against
        maintenance thresholds to produce a typed MaintenanceDecision.

        Resolves the secondary initiation contradiction by explicitly checking
        if initiation was triggered via observed severe/critical defects
        even when carbonation front has not yet reached cover depth.
        """
        threshold = self._config.maintenance_threshold

        corrosion_exceeds = (
            corrosion.corrosion_probability_now
            >= threshold.corrosion_probability_ceiling
        )
        carbonation_exceeds = (
            carbonation.depth_mm_now
            >= threshold.carbonation_cover_fraction
            * assessment_input.material_properties.concrete_cover_mm
        )
        secondary_triggered = (
            corrosion.initiation_status == InitiationStatus.INITIATED
            and carbonation.time_to_depassivation_years is not None
        )

        maintenance_required = (
            corrosion_exceeds or carbonation_exceeds or secondary_triggered
        )

        return MaintenanceDecision(
            maintenance_required=maintenance_required,
            corrosion_index_exceeds_ceiling=corrosion_exceeds,
            carbonation_exceeds_cover_fraction=carbonation_exceeds,
            secondary_initiation_triggered=secondary_triggered,
        )

    def _build_metadata(
        self,
        assessment_input: DegradationAssessmentInput,
    ) -> dict[str, Any]:
        """
        Assemble minimal, deterministic report metadata.

        Includes engine versions (best-effort) and assessment timestamp.
        Structured decision data lives in report.maintenance_decision.
        """
        meta: dict[str, Any] = {
            "service": "ServiceLifeEstimator",
            "service_version": self._config.service_version,
            "assessed_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "asset_age_years": assessment_input.asset_age_years,
            "exposure_class": assessment_input.exposure_class,
        }

        if self._config.include_engine_versions:
            meta["engine_versions"] = self._collect_engine_versions()

        return meta

    def _collect_engine_versions(self) -> dict[str, str]:
        """
        Best-effort collection of engine version strings.

        Reads _config.engine_version where present; silently omits engines
        without this attribute (e.g. test doubles).
        """
        versions: dict[str, str] = {}
        engines: dict[str, object] = {
            "carbonation_model": self._carbonation_model,
            "corrosion_model": self._corrosion_model,
        }
        for name, engine in engines.items():
            cfg = getattr(engine, "_config", None)
            if cfg is not None:
                version = getattr(cfg, "engine_version", None)
                if isinstance(version, str):
                    versions[name] = version
        return versions
