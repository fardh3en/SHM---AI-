"""
Carbonation Depth Model — Phase 4 Material Degradation.

Deterministic, configuration-driven implementation of the square-root-of-time
carbonation depth model.  No machine learning, no LLMs, no probabilistic
inference.  Every coefficient is config-driven and overridable.

Physics model
-------------
The standard carbonation depth formula (Papadakis / fib Model Code):

    d_c(t) = k_c * sqrt(t)

where:
  - d_c  : carbonation front depth in mm at age t
  - t    : asset age in years
  - k_c  : effective carbonation coefficient in mm/√year, derived from the
            exposure class and optionally adjusted for the water-cement ratio

Depassivation occurs when d_c(t) ≥ concrete_cover_mm.

Time to depassivation (closed-form, not sampled):
    Solve k_c * sqrt(t_dep) = cover  →  t_dep = (cover / k_c)²
    remaining = t_dep - asset_age_years

If asset_age_years ≥ t_dep (cover already reached), time_to_depassivation_years
is returned as None to indicate the cover has already been exceeded.

Scope boundary
--------------
This module answers "how deep is the carbonation front, and when will it
reach the rebar?" for a single asset at a single point in time.
It deliberately does NOT:
  - Model chloride diffusion (separate future module).
  - Model freeze-thaw or other degradation mechanisms.
  - Produce multi-point forecast time-series (out of scope for Phase 4).
  - Classify risk or recommend maintenance (IRiskEngine / Phase 5).
  - Import from backend.app.models (ORM decoupling).

NOTE: default coefficient values (in degradation/config.py) are reasonable
engineering starting points for a deterministic, explainable model.  They
are NOT derived from a specific engineering code or standard and must be
reviewed by a domain expert before real structural decision-making.
"""
from __future__ import annotations

import math
from collections.abc import Mapping  # noqa: TC003
from dataclasses import dataclass, field

from degradation.config import (
    DEFAULT_CARBONATION_COEFFICIENTS,
    CarbonationCoefficient,
)
from degradation.models import ExposureClass  # noqa: TC001
from degradation.schemas import CarbonationProjection, DegradationAssessmentInput

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CarbonationModelConfig:
    """
    Full configuration for a CarbonationModel instance.

    Attributes:
        coefficients: Per-exposure-class carbonation coefficients.  The
            mapping must contain an entry for every ExposureClass that will
            be encountered; missing keys raise KeyError at predict() time.
        engine_version: Recorded in ServiceLifeEstimator metadata for
            traceability and audit.
    """

    coefficients: Mapping[ExposureClass, CarbonationCoefficient] = field(
        default_factory=lambda: DEFAULT_CARBONATION_COEFFICIENTS
    )
    engine_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class CarbonationModel:
    """
    Deterministic, configurable carbonation depth model.

    See module docstring for the physics formula, scope boundary, and
    explicit list of what this engine does NOT do.

    Usage::

        model = CarbonationModel()
        projection = model.predict(assessment_input)

    To customise coefficients::

        config = CarbonationModelConfig(
            coefficients={ExposureClass.XC4: CarbonationCoefficient(k_c_base=7.5)},
            engine_version="2.0.0",
        )
        model = CarbonationModel(config=config)
    """

    def __init__(self, config: CarbonationModelConfig | None = None) -> None:
        self._config = config or CarbonationModelConfig()

    def predict(self, input: DegradationAssessmentInput) -> CarbonationProjection:  # noqa: A002
        """
        Compute a single-point carbonation depth projection.

        Args:
            input: Aggregated asset and material data for this assessment.

        Returns:
            CarbonationProjection containing:
              - depth_mm_now: carbonation front depth at asset_age_years.
              - time_to_depassivation_years: remaining years to cover
                depassivation, or None if already exceeded.
              - carbonation_rate_mm_per_sqrt_year: effective k_c used.
        """
        coeff = self._config.coefficients[input.exposure_class]
        k_c = coeff.effective_k_c(input.material_properties.water_cement_ratio)

        depth_now = self._depth_at(k_c, input.asset_age_years)
        cover = input.material_properties.concrete_cover_mm
        remaining = self._remaining_years(k_c, cover, input.asset_age_years)

        return CarbonationProjection(
            depth_mm_now=round(depth_now, 4),
            time_to_depassivation_years=round(remaining, 4) if remaining is not None else None,
            carbonation_rate_mm_per_sqrt_year=round(k_c, 6),
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _depth_at(k_c: float, age_years: float) -> float:
        """Compute d_c = k_c * sqrt(t).  Returns 0 for age 0."""
        if age_years <= 0.0:
            return 0.0
        return k_c * math.sqrt(age_years)

    @staticmethod
    def _remaining_years(
        k_c: float, cover_mm: float, age_years: float
    ) -> float | None:
        """
        Compute remaining years until depassivation (closed-form).

        Solves k_c * sqrt(t_dep) = cover for t_dep, then subtracts the
        already-elapsed age.  Returns None if the cover has already been
        reached (depassivation is current or past).
        """
        if k_c <= 0.0:
            # Zero or negative k_c: carbonation never progresses.
            return None
        t_depassivation = (cover_mm / k_c) ** 2
        remaining = t_depassivation - age_years
        if remaining <= 0.0:
            return None
        return remaining
