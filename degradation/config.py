"""
Phase 4 Material Degradation — Tunable Coefficient Tables.

All physics-model coefficients live here as frozen dataclasses, matching the
pattern established by DEFAULT_SCORING_RULES (health_scorer.py),
DEFAULT_SEVERITY_RULES (severity_classifier.py), and the escalation tables
in risk_engine.py.

NOTE: The default coefficient values in this module are reasonable
engineering starting points for a deterministic, explainable physics model.
They are NOT derived from a specific engineering code or standard (e.g.
EN 206, fib Model Code, or ACI 318), nor have they been calibrated against
real inspection data.  A domain expert (structural engineer or materials
scientist) must review and retune every coefficient before this model is
used for real structural decision-making.

Scope boundary
--------------
This module defines coefficient tables and maintenance thresholds only.
It does NOT:
  - Implement any physics formulas.
  - Import from backend.app.models (ORM decoupling).
  - Depend on degradation/schemas.py (no circular imports).
"""
from __future__ import annotations

from collections.abc import Mapping  # noqa: TC003
from dataclasses import dataclass

from degradation.models import ExposureClass

# ---------------------------------------------------------------------------
# Carbonation coefficient table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CarbonationCoefficient:
    """
    Configuration for the carbonation depth model for one ExposureClass.

    The depth model is:
        d_c(t) = k_c * sqrt(t)

    where t is asset age in years and k_c is derived from this dataclass.

    Attributes:
        k_c_base: Base carbonation coefficient in mm/sqrt(year).
            Represents the depth reached at t=1 year in a standard
            environment for this exposure class.
        wc_adjustment_slope: Multiplier applied to (w/c – wc_reference) when
            a water-cement ratio is provided.  A higher w/c means more
            permeable concrete and a larger k_c.  Set to 0.0 to disable
            the adjustment.
        wc_reference: The reference w/c ratio at which the adjustment is
            zero (i.e., k_c = k_c_base when w/c == wc_reference).
    """

    k_c_base: float  # mm / sqrt(year)
    wc_adjustment_slope: float = 0.0  # mm/sqrt(year) per unit w/c deviation
    wc_reference: float = 0.50  # reference w/c (no adjustment at this value)

    def effective_k_c(self, water_cement_ratio: float | None) -> float:
        """
        Return the effective carbonation coefficient, optionally adjusted
        for the concrete's water-cement ratio.

        If water_cement_ratio is None (uncalibrated), k_c_base is returned
        unchanged (conservative: uses the reference value for the class).
        """
        if water_cement_ratio is None or self.wc_adjustment_slope == 0.0:
            return self.k_c_base
        adjustment = self.wc_adjustment_slope * (water_cement_ratio - self.wc_reference)
        return max(0.0, self.k_c_base + adjustment)


# NOTE: k_c_base values are broad representative starting points for each
# EN 206 exposure class.  Literature values span roughly:
#   XC1: 1.5–3 mm/√yr  (dry, low CO₂ penetration)
#   XC2: 2–4 mm/√yr
#   XC3: 3–6 mm/√yr    (most common exterior sheltered condition)
#   XC4: 4–8 mm/√yr    (cyclic wet/dry accelerates penetration)
# The wc_adjustment_slope of 5.0 encodes the well-known empirical observation
# that each 0.10 increase in w/c roughly raises k_c by 0.5 mm/√yr.
DEFAULT_CARBONATION_COEFFICIENTS: Mapping[ExposureClass, CarbonationCoefficient] = {
    ExposureClass.XC1: CarbonationCoefficient(
        k_c_base=2.0,
        wc_adjustment_slope=4.0,
        wc_reference=0.50,
    ),
    ExposureClass.XC2: CarbonationCoefficient(
        k_c_base=3.0,
        wc_adjustment_slope=4.5,
        wc_reference=0.50,
    ),
    ExposureClass.XC3: CarbonationCoefficient(
        k_c_base=4.5,
        wc_adjustment_slope=5.0,
        wc_reference=0.50,
    ),
    ExposureClass.XC4: CarbonationCoefficient(
        k_c_base=6.0,
        wc_adjustment_slope=5.5,
        wc_reference=0.50,
    ),
}


# ---------------------------------------------------------------------------
# Corrosion rate table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorrosionRateEntry:
    """
    Configuration for the corrosion propagation model for one ExposureClass.

    IMPORTANT — terminology note: the field ``corrosion_probability_now``
    produced by CorrosionModel is a deterministic saturating index in [0, 1]
    derived from years-since-initiation and the saturation timescale below.
    It is NOT a statistical probability inferred from a probabilistic model.
    The name mirrors the ORM field (DegradationRecord.corrosion_probability)
    to simplify future adapter mapping, but its value is computed
    deterministically from the physics parameters here.

    Attributes:
        propagation_rate_mm_per_year: Rate at which active corrosion
            consumes rebar cross-section in mm/year once initiation has
            occurred.
        saturation_timescale_years: Characteristic time (years) for the
            deterministic corrosion index to reach ~63 % of its saturation
            value (1/e time constant of the exponential saturation function).
            Larger values represent slower-progressing exposure environments.
    """

    propagation_rate_mm_per_year: float
    saturation_timescale_years: float


# NOTE: propagation rates and saturation timescales below are representative
# starting points, not values calibrated to any specific field data set or
# code.  Literature suggests initiation-phase corrosion propagation rates
# broadly in the range 0.01–0.10 mm/year for carbonation-induced scenarios;
# saturation timescales of 15–40 years reflect the slow progression typical
# of sheltered concrete.  All values must be reviewed by a domain expert
# before use in real structural decisions.
DEFAULT_CORROSION_RATES: Mapping[ExposureClass, CorrosionRateEntry] = {
    ExposureClass.XC1: CorrosionRateEntry(
        propagation_rate_mm_per_year=0.010,
        saturation_timescale_years=40.0,
    ),
    ExposureClass.XC2: CorrosionRateEntry(
        propagation_rate_mm_per_year=0.025,
        saturation_timescale_years=30.0,
    ),
    ExposureClass.XC3: CorrosionRateEntry(
        propagation_rate_mm_per_year=0.050,
        saturation_timescale_years=20.0,
    ),
    ExposureClass.XC4: CorrosionRateEntry(
        propagation_rate_mm_per_year=0.080,
        saturation_timescale_years=15.0,
    ),
}


# ---------------------------------------------------------------------------
# Maintenance threshold
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaintenanceThreshold:
    """
    Configurable thresholds that define when maintenance intervention is
    triggered. Consumed by ServiceLifeEstimator to populate the typed
    MaintenanceDecision on DegradationAssessmentReport.

    Attributes:
        corrosion_probability_ceiling: Corrosion index value [0, 1] above
            which maintenance is considered necessary. Default 0.40 is a
            conservative starting point (40 % of saturation index).
        carbonation_cover_fraction: Fraction of concrete cover depth that,
            when exceeded by the carbonation front, flags heightened risk.
            Default 1.0 means the threshold is depassivation itself.
    """

    corrosion_probability_ceiling: float = 0.40
    carbonation_cover_fraction: float = 1.0


DEFAULT_MAINTENANCE_THRESHOLD = MaintenanceThreshold()
