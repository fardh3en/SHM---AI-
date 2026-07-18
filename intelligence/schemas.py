"""
Domain schemas for the Structural Health Intelligence engine.

These are pure Pydantic v2 domain models. They intentionally do NOT import
from backend.app.models (the persistence/ORM layer) — this package is a
separate bounded context. Where a concept overlaps with an existing
persistence-layer enum (e.g. AssetType, DefectType/DefectCategory), the
enum is redefined here at the domain level. A mapping/adapter layer between
this domain model and the ORM layer is a later Phase 3 milestone, not part
of this foundation.

No business logic, scoring algorithms, or default classification values live
in this module — schemas only.
"""
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# ── Domain Enums ─────────────────────────────────────────────────────────────
class AssetType(StrEnum):
    """Physical category of the monitored structure."""

    BRIDGE = "bridge"
    BUILDING = "building"
    TUNNEL = "tunnel"
    ROAD = "road"
    DAM = "dam"
    PIPELINE = "pipeline"
    OTHER = "other"


class DefectCategory(StrEnum):
    """Structural defect categories, as produced by the vision engine."""

    CRACK = "crack"
    SPALLING = "spalling"
    CORROSION = "corrosion"
    EXPOSED_REINFORCEMENT = "exposed_reinforcement"
    DELAMINATION = "delamination"
    POTHOLE = "pothole"
    SURFACE_DAMAGE = "surface_damage"
    UNKNOWN = "unknown"


class SeverityLevel(StrEnum):
    """Discrete severity classification for a defect category grouping."""

    NEGLIGIBLE = "negligible"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class RiskLevel(StrEnum):
    """Overall asset risk classification derived from the health score."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FailureModeCategory(StrEnum):
    """Structural failure mechanisms identifiable from defect patterns."""

    FLEXURAL = "flexural"
    SHEAR = "shear"
    COMPRESSION_BUCKLING = "compression_buckling"
    PUNCHING_SHEAR = "punching_shear"
    CORROSION_INDUCED_SECTION_LOSS = "corrosion_induced_section_loss"
    DELAMINATION_INDUCED = "delamination_induced"
    UNKNOWN = "unknown"


# ── Input Schemas ─────────────────────────────────────────────────────────────
class DefectObservation(BaseModel):
    """
    A single defect observation feeding into a health assessment.

    Intentionally decoupled from the persistence-layer Detection model —
    this is the domain-level view of what the intelligence engine needs to
    reason about a defect, expressed in calibrated real-world units where
    available.
    """

    defect_category: DefectCategory
    confidence: float = Field(
        ge=0.0, le=1.0, description="Vision engine detection confidence."
    )
    area_mm2: float | None = Field(
        default=None, description="Physical defect area in mm², if calibrated."
    )
    length_mm: float | None = Field(
        default=None, description="Physical centerline length in mm, if calibrated."
    )
    width_mm: float | None = Field(
        default=None, description="Average physical width in mm, if calibrated."
    )
    max_width_mm: float | None = Field(
        default=None, description="Maximum physical width in mm, if calibrated."
    )
    orientation_deg: float | None = Field(
        default=None, description="Dominant orientation angle (-90 to 90, 0 = horizontal)."
    )
    location_label: str | None = Field(
        default=None,
        description=(
            "Optional structural location descriptor supplied by the "
            "inspector or a future localisation model, e.g. "
            "'beam-bottom', 'column-face-A', 'slab-midspan'."
        ),
    )


class HealthAssessmentInput(BaseModel):
    """
    Aggregated input required to produce a HealthAssessmentReport for a
    single inspection of a single asset.
    """

    asset_id: str
    asset_type: AssetType
    inspection_id: str
    observations: list[DefectObservation] = Field(default_factory=list)
    asset_age_years: float | None = Field(
        default=None, description="Age of the asset at time of inspection, if known."
    )
    design_life_years: float | None = Field(
        default=None, description="Original design service life of the asset, if known."
    )


# ── Output Schemas ────────────────────────────────────────────────────────────
class DefectSeverityBreakdown(BaseModel):
    """
    Severity classification for one defect category observed in an
    inspection, aggregated across all matching observations.
    """

    defect_category: DefectCategory
    severity: SeverityLevel
    observation_count: int = Field(ge=0)
    total_area_mm2: float | None = Field(
        default=None, description="Sum of area_mm2 across observations in this category."
    )
    max_width_mm: float | None = Field(
        default=None, description="Largest max_width_mm observed in this category."
    )
    contribution_score: float | None = Field(
        default=None,
        description=(
            "This category's contribution to the overall health score "
            "deduction. Sign and scale defined by the scoring engine "
            "implementation, not by this schema."
        ),
    )


class StructuralFailureMode(BaseModel):
    """
    An identified structural failure mechanism, derived from engineering
    rules applied to the observed defect pattern.
    """

    category: FailureModeCategory
    description: str = Field(
        description="Human-readable explanation of the identified failure mode."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Engine confidence in this failure mode identification."
    )
    related_defect_categories: list[DefectCategory] = Field(
        default_factory=list,
        description="Defect categories that contributed to identifying this failure mode.",
    )


class HealthAssessmentReport(BaseModel):
    """
    Complete output of the Structural Health Intelligence engine for a
    single inspection.

    Contains only outputs available from the scoring and classification
    stages. Maintenance recommendations are explicitly out of scope for
    this report — that is the responsibility of a separate Recommendation
    Engine (Phase 5).
    """

    asset_id: str
    inspection_id: str
    health_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Composite structural health score, 0 (critical) - 100 (pristine).",
    )
    risk_level: RiskLevel
    severity_breakdown: list[DefectSeverityBreakdown] = Field(default_factory=list)
    failure_modes: list[StructuralFailureMode] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Free-form supplementary data about the assessment run "
            "(e.g. engine version, rule set version, timing). Not intended "
            "for structural decision-making itself."
        ),
    )
