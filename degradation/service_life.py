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

NOTE: maintenance thresholds come from MaintenanceThreshold in
degradation/config.py and are configurable. The authoritative maintenance
decision is exposed as DegradationAssessmentReport.requires_maintenance;
metadata["maintenance_flags"] is kept for backward compatibility only.
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
)  # noqa: TCH001

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
        metadata = self._build_metadata(
            assessment_input, carbonation, corrosion, maintenance_decision
        )

        return DegradationAssessmentReport(
            asset_id=assessment_input.asset_id,
            inspection_id=assessment_input.inspection_id,
            carbonation=carbonation,
            corrosion=corrosion,
            maintenance_decision=maintenance_decision,
            requires_maintenance=maintenance_decision.maintenance_required,
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

        Root-cause fix for silent-suppression bug
        ------------------------------------------
        The secondary initiation path (observed SEVERE/CRITICAL severity)
        always sets years_since_initiation = 0.0, which makes
        corrosion_probability_now = 0.0 (1 - exp(0) = 0). Reading only the
        numeric index against a ceiling would therefore silently suppress the
        maintenance flag for exactly the scenario the secondary signal exists
        to catch.

        Fix: maintenance is required when corrosion is INITIATED and EITHER
          (a) the numeric index meets the ceiling, OR
          (b) years_since_initiation == 0.0 — the categorical confirmation
              of active corrosion from field observation must override the
              formula, not be erased by it.
        """
        threshold = self._config.maintenance_threshold

        corrosion_exceeds = (
            corrosion.corrosion_probability_now
            >= threshold.corrosion_probability_ceiling
        )
        # Secondary-signal case: initiation confirmed by observed field severity
        # but carbonation hasn't reached cover yet, so the propagation formula
        # hasn't had any elapsed time to work with (years_since = 0.0).
        corrosion_secondary_signal = (
            corrosion.initiation_status == InitiationStatus.INITIATED
            and corrosion.years_since_initiation == 0.0
        )
        carbonation_exceeds = (
            carbonation.depth_mm_now
            >= threshold.carbonation_cover_fraction
            * assessment_input.material_properties.concrete_cover_mm
        )
        # secondary_triggered: INITIATED but carbonation hasn't reached cover
        # (time_to_depassivation_years is not None means cover is still intact)
        secondary_triggered = (
            corrosion.initiation_status == InitiationStatus.INITIATED
            and carbonation.time_to_depassivation_years is not None
        )

        maintenance_required = (
            (
                corrosion.initiation_status == InitiationStatus.INITIATED
                and (corrosion_exceeds or corrosion_secondary_signal)
            )
            or carbonation_exceeds
            or secondary_triggered
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
        carbonation: CarbonationProjection,
        corrosion: CorrosionProjection,
        maintenance_decision: MaintenanceDecision,
    ) -> dict[str, Any]:
        """
        Assemble report metadata for traceability and backward compatibility.

        IMPORTANT: metadata["maintenance_flags"] is retained for backward
        compatibility with callers that read it, but it is NOT authoritative.
        Use report.requires_maintenance for the actual maintenance decision.
        The structured breakdown is at report.maintenance_decision.
        """
        meta: dict[str, Any] = {
            "service": "ServiceLifeEstimator",
            "service_version": self._config.service_version,
            "assessed_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "asset_age_years": assessment_input.asset_age_years,
            "exposure_class": assessment_input.exposure_class,
            # Non-authoritative backward-compat snapshot of the maintenance
            # flags. Mirrors maintenance_decision fields; not the source of
            # truth — use report.requires_maintenance instead.
            "maintenance_flags": {
                "corrosion_index_exceeds_ceiling": (
                    maintenance_decision.corrosion_index_exceeds_ceiling
                ),
                "carbonation_exceeds_cover_fraction": (
                    maintenance_decision.carbonation_exceeds_cover_fraction
                ),
                "secondary_initiation_triggered": (
                    maintenance_decision.secondary_initiation_triggered
                ),
                "requires_maintenance": maintenance_decision.maintenance_required,
            },
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
