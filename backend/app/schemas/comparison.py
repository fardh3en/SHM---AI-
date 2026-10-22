"""
Inspection Comparison & Change Tracking schemas.

Provides typed contracts for comparing two inspections of the same asset,
evaluating defect persistence vs newly detected defects, score deltas,
and engineering comparability disclosures.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class InspectionComparisonSummary(BaseModel):
    """Summary of an individual inspection within a comparison."""
    id: str
    created_at: str
    source: str
    status: str
    defect_count: int
    health_score: float | None = None
    assessment_method: str | None = None
    input_path: str | None = None
    defect_types: list[str] = Field(default_factory=list)
    total_area_px: float | None = None


class InspectionComparisonResponse(BaseModel):
    """
    Comparison output between two inspections of the same asset.

    Discloses limitations regarding viewing angles, missed detections vs repairs,
    and measurement comparability.
    """
    asset_id: str
    asset_name: str
    base_inspection: InspectionComparisonSummary
    target_inspection: InspectionComparisonSummary
    comparability_status: str = Field(
        description="'comparable', 'partially_comparable', or 'incomparable'."
    )
    common_defect_types: list[str] = Field(
        default_factory=list,
        description="Defect categories identified in both inspections.",
    )
    newly_observed_defect_types: list[str] = Field(
        default_factory=list,
        description="Defect categories observed in the target inspection but not the base.",
    )
    previously_observed_defect_types_absent: list[str] = Field(
        default_factory=list,
        description="Defect categories observed in the base inspection but absent in the target.",
    )
    health_score_delta: float | None = Field(
        default=None,
        description="Target health score minus base health score (positive indicates improvement).",
    )
    defect_count_delta: int = Field(
        description="Target defect count minus base defect count.",
    )
    measurement_comparison: dict[str, Any] = Field(
        default_factory=dict,
        description="Pixel measurement comparisons (total area, max dimensions) with caveats.",
    )
    disclosures_and_limitations: list[str] = Field(
        default_factory=list,
        description="Explicit engineering disclosures regarding measurement comparability.",
    )
