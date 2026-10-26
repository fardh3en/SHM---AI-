"""
Structural Health Assessment schemas.

Defines client contracts for explainable structural assessment results,
failure mode inference, severity breakdowns, and provenance metadata.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SeverityBreakdownItem(BaseModel):
    """Per-defect-category severity classification."""
    defect_category: str
    severity: str
    observation_count: int
    max_width_mm: float | None = None
    total_area_mm2: float | None = None


class FailureModeItem(BaseModel):
    """Inferred structural failure mode with engineering confidence."""
    category: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    related_defects: list[str] = Field(default_factory=list)


class StructuralAssessmentResponse(BaseModel):
    """
    Authoritative, explainable structural health assessment output.

    Preserves provenance, method versions, assumptions, limitations,
    and missing input disclosures.
    """
    status: str = Field(
        description="Assessment status: 'completed', 'unavailable', 'insufficient_data', or 'unverified'."
    )
    asset_id: str
    asset_name: str
    inspection_id: str
    assessment_date_utc: str | None = None
    health_score: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Deterministic composite score (0-100). None if assessment cannot be computed.",
    )
    risk_level: str | None = Field(
        default=None,
        description="Discrete risk level ('low', 'medium', 'high', 'critical').",
    )
    assessment_method: str = Field(
        default="SHM-AI Deterministic Rules Engine v1.0",
        description="Documented methodology identifier.",
    )
    service_version: str = Field(
        default="1.0.0",
        description="Version of the intelligence assessment service.",
    )
    calibration_status: str = Field(
        default="uncalibrated_pixel_space",
        description="Metric calibration state ('uncalibrated_pixel_space' or 'calibrated_gsd').",
    )
    data_sources: list[str] = Field(
        default_factory=list,
        description="Specific models, rule sets, and sensor/media sources that contributed.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Engineering assumptions underlying this assessment.",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Known structural monitoring and visual inspection limitations.",
    )
    missing_inputs: list[str] = Field(
        default_factory=list,
        description="Disclosures of missing or uncalibrated parameters.",
    )
    severity_breakdown: list[SeverityBreakdownItem] = Field(default_factory=list)
    failure_modes: list[FailureModeItem] = Field(default_factory=list)
    notes: str | None = None
    model_name: str | None = Field(
        default=None,
        description="Active computer vision model identifier.",
    )
    model_validated: bool | None = Field(
        default=None,
        description="Whether the active computer vision model has been validated for target structural defect classes.",
    )
    detected_defect_count: int = Field(
        default=0,
        description="Number of defect instances detected in the photographic evidence.",
    )

    model_config = {
        "protected_namespaces": (),
    }
