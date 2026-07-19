"""
Phase 4 Material Degradation — I/O Schemas.

Pydantic v2 domain models for the degradation assessment pipeline.
Mirrors the style and constraints of intelligence/schemas.py:
  - No ORM imports.
  - No business logic or formulas.
  - Pure data containers with field-level documentation.

Cross-package reference: SeverityLevel is imported from intelligence.schemas
because intelligence/ is the upstream domain layer and SeverityLevel is the
canonical defect-severity vocabulary for the whole platform.  This is the
only intentional cross-package import; all other types are local.

Scope boundary
--------------
This module defines I/O contracts only.  It does NOT:
  - Import from backend.app.models (ORM decoupling).
  - Contain any physics formulas or scoring logic.
  - Define domain vocabulary enumerations (those live in degradation/models.py).
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from degradation.models import ExposureClass, MaterialProperties  # noqa: TC001
from intelligence.schemas import SeverityLevel  # noqa: TC001

# ── Corrosion initiation state ────────────────────────────────────────────────


class InitiationStatus(StrEnum):
    """
    Whether corrosion has been initiated (i.e. carbonation front has
    reached or passed the rebar depth).
    """

    NOT_INITIATED = "not_initiated"
    INITIATED = "initiated"


# ── Input schema ──────────────────────────────────────────────────────────────


class DegradationAssessmentInput(BaseModel):
    """
    Aggregated input required to run a degradation assessment for a single
    asset at a single point in time.

    Fields intentionally decouple from the ORM layer — this is the domain-
    level view of what the physics models need.  An adapter layer mapping
    Asset / Inspection ORM records to this schema is a later, separate task.
    """

    asset_id: str
    inspection_id: str | None = Field(
        default=None,
        description=(
            "Optional reference to the inspection that triggered this assessment. "
            "May be None when the assessment is run independently of an inspection."
        ),
    )
    asset_age_years: float = Field(
        ge=0.0,
        description="Age of the asset in years at the time of assessment.",
    )
    material_properties: MaterialProperties
    exposure_class: ExposureClass
    observed_corrosion_severity: SeverityLevel | None = Field(
        default=None,
        description=(
            "Severity of observed corrosion defects from the most recent inspection, "
            "as classified by ISeverityClassifier.  Used as a secondary initiation "
            "signal when carbonation depth alone has not yet flagged depassivation."
        ),
    )


# ── Output schemas ────────────────────────────────────────────────────────────


class CarbonationProjection(BaseModel):
    """
    Single-point carbonation depth projection at the current asset age.

    Produced by CarbonationModel.predict().
    """

    depth_mm_now: float = Field(
        ge=0.0,
        description="Carbonation front depth in mm at the current asset age.",
    )
    time_to_depassivation_years: float | None = Field(
        description=(
            "Remaining years until the carbonation front is projected to reach "
            "the concrete cover depth (depassivation).  "
            "None if the cover has already been reached under current coefficients "
            "(depassivation is already past or present)."
        ),
    )
    carbonation_rate_mm_per_sqrt_year: float = Field(
        ge=0.0,
        description=(
            "Effective k_c coefficient used in this projection, in mm/√year. "
            "Incorporates any w/c-ratio adjustment applied by the model."
        ),
    )


class CorrosionProjection(BaseModel):
    """
    Deterministic corrosion state projection at the current asset age.

    Produced by CorrosionModel.predict().

    IMPORTANT — terminology: corrosion_probability_now is a deterministic
    saturating index in [0, 1] derived from years-since-initiation and the
    configured saturation timescale.  It is NOT a statistical probability
    from a probabilistic model.  The field name mirrors the ORM column
    (DegradationRecord.corrosion_probability) to simplify future adapter
    mapping.
    """

    initiation_status: InitiationStatus
    years_since_initiation: float | None = Field(
        default=None,
        description=(
            "Years elapsed since corrosion initiation.  None if corrosion "
            "has not yet been initiated."
        ),
    )
    corrosion_probability_now: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Deterministic corrosion index in [0, 1].  0.0 if not initiated. "
            "Computed as 1 - exp(-years_since_initiation / saturation_timescale) "
            "once initiated, saturating towards 1.0 over time."
        ),
    )
    propagation_rate_mm_per_year: float | None = Field(
        default=None,
        description=(
            "Active corrosion propagation rate in mm/year from the config table. "
            "None if corrosion has not yet been initiated."
        ),
    )


class MaintenanceDecision(BaseModel):
    """
    Typed evaluation indicating whether maintenance intervention is recommended
    based on physics projections and observed degradation signals.

    Produced by ServiceLifeEstimator evaluating CarbonationProjection and
    CorrosionProjection against MaintenanceThreshold configuration.
    """

    maintenance_required: bool = Field(
        description=(
            "True if any maintenance threshold is exceeded or if active secondary "
            "corrosion initiation was triggered by observed severe/critical defects."
        ),
    )
    corrosion_index_exceeds_ceiling: bool = Field(
        description=(
            "True if the corrosion probability index meets or exceeds the "
            "configured maintenance ceiling."
        ),
    )
    carbonation_exceeds_cover_fraction: bool = Field(
        description=(
            "True if carbonation depth meets or exceeds the concrete cover "
            "fraction threshold."
        ),
    )
    secondary_initiation_triggered: bool = Field(
        description=(
            "True if corrosion initiation was triggered by observed severe or critical "
            "corrosion defects despite carbonation depth not yet reaching cover."
        ),
    )


class DegradationAssessmentReport(BaseModel):
    """
    Complete output of the Phase 4 Material Degradation Engine for a single
    asset assessment.

    Assembled by ServiceLifeEstimator from the outputs of CarbonationModel
    and CorrosionModel. Contains deterministic physics-model projections,
    a typed maintenance decision, and a top-level requires_maintenance flag.
    Maintenance recommendation orchestration (e.g., intervention actions and
    scheduling) remains the responsibility of Phase 5.

    Key fields
    ----------
    requires_maintenance : bool
        Authoritative single-boolean maintenance flag. True if any threshold
        is exceeded OR if corrosion initiation was confirmed by observed
        severe/critical field severity (secondary initiation signal), even
        when the numeric corrosion index is still 0.0.  Use this field —
        not metadata["maintenance_flags"] — for decision-making.
    maintenance_decision : MaintenanceDecision
        Typed breakdown of which specific condition triggered maintenance.
    metadata : dict
        Non-authoritative supplementary context (engine versions, timestamps,
        raw threshold values). Kept for backward compatibility; NOT the source
        of truth for the maintenance decision.
    """

    asset_id: str
    inspection_id: str | None
    carbonation: CarbonationProjection
    corrosion: CorrosionProjection
    maintenance_decision: MaintenanceDecision
    requires_maintenance: bool = Field(
        description=(
            "Authoritative maintenance flag. True if any threshold is exceeded "
            "or if corrosion initiation was confirmed by observed severe/critical "
            "field severity (secondary signal), even when the numeric corrosion "
            "index is still 0.0. Prefer this field over metadata['maintenance_flags'] "
            "for structural decision-making."
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Non-authoritative supplementary context for the assessment run "
            "(e.g. engine versions, assessment timestamp, raw threshold values). "
            "Kept for backward compatibility. NOT the source of truth for the "
            "maintenance decision — use requires_maintenance for that."
        ),
    )
