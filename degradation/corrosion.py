"""
Corrosion Propagation Model — Phase 4 Material Degradation.

Deterministic, configuration-driven model that derives a corrosion state
from the output of CarbonationModel.  No machine learning, no probabilistic
inference.

Physics model
-------------
Initiation: corrosion is considered initiated when the carbonation front has
reached or passed the rebar (depassivation):

    initiated = carbonation.time_to_depassivation_years is None
                (i.e. depassivation has already occurred)

Secondary initiation signal (engineering conservatism): when carbonation
alone has NOT flagged initiation but the most recent inspection reports
SEVERE or CRITICAL corrosion severity, corrosion is also treated as
initiated.  This conservatism is deliberate — visible severe/critical
corrosion is strong empirical evidence of active corrosion regardless of
the modelled carbonation state.  This fallback is documented explicitly here
and in the predict() docstring so it is never an implicit or hidden default.

years_since_initiation is estimated as:
  • If initiated via carbonation:
        years_since_initiation = max(0, asset_age_years - t_depassivation)
    where t_depassivation = (cover / k_c)² is back-calculated from the
    carbonation projection.
  • If initiated only via the secondary severity signal (no carbonation
    initiation):
        years_since_initiation = 0.0
    (conservative: treats initiation as concurrent with inspection)

Corrosion index (deterministic saturating function):

    index(τ) = 1 - exp(-τ / τ_sat)

where τ = years_since_initiation, τ_sat = saturation_timescale_years from
config.  This is clipped to [0, 1].

IMPORTANT — terminology: the ``corrosion_probability_now`` output field is
this deterministic index, NOT a statistical probability.  The name mirrors
the ORM column DegradationRecord.corrosion_probability for adapter-layer
compatibility; the value is fully deterministic.

Scope boundary
--------------
This module answers "has corrosion initiated, and if so how advanced is it?"
for a single asset at a single point in time.  It deliberately does NOT:
  - Compute carbonation depth (CarbonationModel's responsibility).
  - Model chloride-induced corrosion (separate future module).
  - Produce multi-point forecast time-series (out of scope for Phase 4).
  - Classify risk or recommend maintenance (IRiskEngine / Phase 5).
  - Import from backend.app.models (ORM decoupling).

NOTE: default propagation rates and saturation timescales (in
degradation/config.py) are reasonable engineering starting points.
They are NOT derived from a specific code or standard and must be reviewed
by a domain expert before real structural decision-making.
"""
from __future__ import annotations

import math
from collections.abc import Mapping  # noqa: TC003
from dataclasses import dataclass, field

from degradation.config import (
    DEFAULT_CORROSION_RATES,
    CorrosionRateEntry,
)
from degradation.models import ExposureClass  # noqa: TC001
from degradation.schemas import (
    CarbonationProjection,
    CorrosionProjection,
    DegradationAssessmentInput,
    InitiationStatus,
)
from intelligence.schemas import SeverityLevel

# Severity levels that act as a secondary initiation signal.
# Only SEVERE and CRITICAL observed corrosion are treated conservatively as
# evidence of active initiation when carbonation depth alone has not yet
# flagged depassivation.
_SECONDARY_INITIATION_SEVERITIES: frozenset[SeverityLevel] = frozenset(
    {SeverityLevel.SEVERE, SeverityLevel.CRITICAL}
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorrosionModelConfig:
    """
    Full configuration for a CorrosionModel instance.

    Attributes:
        rates: Per-exposure-class corrosion rate entries.  The mapping must
            contain an entry for every ExposureClass encountered; missing
            keys raise KeyError at predict() time.
        engine_version: Recorded in ServiceLifeEstimator metadata.
    """

    rates: Mapping[ExposureClass, CorrosionRateEntry] = field(
        default_factory=lambda: DEFAULT_CORROSION_RATES
    )
    engine_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class CorrosionModel:
    """
    Deterministic, configurable corrosion propagation model.

    See module docstring for the physics model, initiation logic (including
    the secondary severity-based signal), scope boundary, and terminology
    note on corrosion_probability_now.

    Usage::

        model = CorrosionModel()
        projection = model.predict(assessment_input, carbonation_projection)
    """

    def __init__(self, config: CorrosionModelConfig | None = None) -> None:
        self._config = config or CorrosionModelConfig()

    def predict(
        self,
        input: DegradationAssessmentInput,  # noqa: A002
        carbonation: CarbonationProjection,
    ) -> CorrosionProjection:
        """
        Compute a single-point corrosion state projection.

        Initiation is determined first from the carbonation projection
        (primary signal), then from observed_corrosion_severity as a
        secondary conservative fallback (see module docstring for rationale).

        Args:
            input: Aggregated asset and material data for this assessment.
            carbonation: Output of CarbonationModel.predict() for the same
                input.  Provides the depassivation signal.

        Returns:
            CorrosionProjection with initiation status, years since
            initiation, deterministic corrosion index, and propagation rate.
        """
        rate_entry = self._config.rates[input.exposure_class]

        initiated, years_since = self._determine_initiation(
            input, carbonation, rate_entry
        )

        if not initiated:
            return CorrosionProjection(
                initiation_status=InitiationStatus.NOT_INITIATED,
                years_since_initiation=None,
                corrosion_probability_now=0.0,
                propagation_rate_mm_per_year=None,
            )

        index = self._corrosion_index(years_since, rate_entry.saturation_timescale_years)

        return CorrosionProjection(
            initiation_status=InitiationStatus.INITIATED,
            years_since_initiation=round(years_since, 4),
            corrosion_probability_now=round(index, 6),
            propagation_rate_mm_per_year=rate_entry.propagation_rate_mm_per_year,
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _determine_initiation(
        self,
        input: DegradationAssessmentInput,  # noqa: A002
        carbonation: CarbonationProjection,
        rate_entry: CorrosionRateEntry,
    ) -> tuple[bool, float]:
        """
        Determine whether corrosion has initiated and, if so, how many years
        ago.

        Returns:
            (initiated: bool, years_since_initiation: float)
            years_since_initiation is 0.0 when initiated is False.
        """
        # ── Primary signal: carbonation depassivation ────────────────────────
        # time_to_depassivation_years is None iff the cover has already been
        # reached (depassivation is present or past).
        if carbonation.time_to_depassivation_years is None:
            years_since = self._years_since_from_carbonation(
                input.asset_age_years,
                input.material_properties.concrete_cover_mm,
                carbonation.carbonation_rate_mm_per_sqrt_year,
            )
            return True, years_since

        # ── Secondary signal: observed severe/critical corrosion ─────────────
        # This is a deliberate engineering conservatism: when inspection data
        # reports SEVERE or CRITICAL corrosion and the carbonation model has
        # not yet flagged depassivation, we conservatively treat corrosion as
        # initiated.  years_since_initiation is set to 0.0 (concurrent with
        # inspection — the most conservative estimate available without
        # additional timing data).
        if (
            input.observed_corrosion_severity is not None
            and input.observed_corrosion_severity in _SECONDARY_INITIATION_SEVERITIES
        ):
            return True, 0.0

        return False, 0.0

    @staticmethod
    def _years_since_from_carbonation(
        asset_age_years: float,
        cover_mm: float,
        k_c: float,
    ) -> float:
        """
        Back-calculate years since depassivation from the carbonation model.

        t_dep = (cover / k_c)²  (closed-form inverse of d_c = k_c * sqrt(t))
        years_since = max(0, asset_age_years - t_dep)
        """
        if k_c <= 0.0:
            return 0.0
        t_dep = (cover_mm / k_c) ** 2
        return max(0.0, asset_age_years - t_dep)

    @staticmethod
    def _corrosion_index(years_since: float, saturation_timescale: float) -> float:
        """
        Deterministic saturating corrosion index in [0, 1].

            index = 1 - exp(-years_since / saturation_timescale)

        Clipped to [0, 1] to guard against floating-point edge cases.
        """
        if saturation_timescale <= 0.0 or years_since <= 0.0:
            return 0.0
        raw = 1.0 - math.exp(-years_since / saturation_timescale)
        return max(0.0, min(1.0, raw))
