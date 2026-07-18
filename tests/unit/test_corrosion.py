"""
Unit tests for degradation.corrosion.CorrosionModel.

Test strategy
-------------
Tests are organized by scenario type:
  - Not-yet-initiated: carbonation has not reached cover
  - Initiated via carbonation (primary signal)
  - Initiated via severity fallback (secondary signal)
  - Already-past-depassivation with years-since back-calculation
  - Physics formula verification (1 - exp(-τ/τ_sat))
  - Config override
  - Determinism

All tests are synchronous and self-contained.  CarbonationProjection
instances are built directly as fixtures to isolate CorrosionModel from
CarbonationModel.
"""
from __future__ import annotations

import math

import pytest

from degradation.config import CorrosionRateEntry
from degradation.corrosion import CorrosionModel, CorrosionModelConfig
from degradation.models import ExposureClass, MaterialProperties
from degradation.schemas import (
    CarbonationProjection,
    CorrosionProjection,
    DegradationAssessmentInput,
    InitiationStatus,
)
from intelligence.schemas import SeverityLevel

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _input(
    age_years: float = 20.0,
    cover_mm: float = 40.0,
    exposure_class: ExposureClass = ExposureClass.XC3,
    observed_severity: SeverityLevel | None = None,
) -> DegradationAssessmentInput:
    return DegradationAssessmentInput(
        asset_id="asset-001",
        inspection_id="insp-001",
        asset_age_years=age_years,
        material_properties=MaterialProperties(concrete_cover_mm=cover_mm),
        exposure_class=exposure_class,
        observed_corrosion_severity=observed_severity,
    )


def _carbonation_not_initiated(
    depth_mm: float = 20.0,
    remaining: float = 80.0,
    k_c: float = 4.5,
) -> CarbonationProjection:
    """Projection where depassivation has NOT yet occurred."""
    return CarbonationProjection(
        depth_mm_now=depth_mm,
        time_to_depassivation_years=remaining,
        carbonation_rate_mm_per_sqrt_year=k_c,
    )


def _carbonation_initiated(
    depth_mm: float = 60.0,
    k_c: float = 4.5,
) -> CarbonationProjection:
    """Projection where depassivation HAS occurred (time_to_dep is None)."""
    return CarbonationProjection(
        depth_mm_now=depth_mm,
        time_to_depassivation_years=None,  # cover already exceeded
        carbonation_rate_mm_per_sqrt_year=k_c,
    )


@pytest.fixture
def model() -> CorrosionModel:
    return CorrosionModel()


# ---------------------------------------------------------------------------
# Not-yet-initiated state
# ---------------------------------------------------------------------------


class TestNotInitiated:
    def test_returns_corrosion_projection(self, model: CorrosionModel) -> None:
        result = model.predict(_input(), _carbonation_not_initiated())
        assert isinstance(result, CorrosionProjection)

    def test_status_not_initiated(self, model: CorrosionModel) -> None:
        result = model.predict(_input(), _carbonation_not_initiated())
        assert result.initiation_status == InitiationStatus.NOT_INITIATED

    def test_probability_zero(self, model: CorrosionModel) -> None:
        result = model.predict(_input(), _carbonation_not_initiated())
        assert result.corrosion_probability_now == 0.0

    def test_years_since_none(self, model: CorrosionModel) -> None:
        result = model.predict(_input(), _carbonation_not_initiated())
        assert result.years_since_initiation is None

    def test_propagation_rate_none(self, model: CorrosionModel) -> None:
        result = model.predict(_input(), _carbonation_not_initiated())
        assert result.propagation_rate_mm_per_year is None

    def test_no_initiation_with_minor_severity(self, model: CorrosionModel) -> None:
        """MINOR and MODERATE severity do NOT trigger the secondary signal."""
        for sev in (SeverityLevel.MINOR, SeverityLevel.MODERATE):
            result = model.predict(
                _input(observed_severity=sev), _carbonation_not_initiated()
            )
            assert result.initiation_status == InitiationStatus.NOT_INITIATED

    def test_no_initiation_with_no_severity(self, model: CorrosionModel) -> None:
        result = model.predict(_input(observed_severity=None), _carbonation_not_initiated())
        assert result.initiation_status == InitiationStatus.NOT_INITIATED


# ---------------------------------------------------------------------------
# Initiated via carbonation (primary signal)
# ---------------------------------------------------------------------------


class TestInitiatedViaCarbonation:
    def test_status_initiated_when_depassivation_past(
        self, model: CorrosionModel
    ) -> None:
        result = model.predict(_input(), _carbonation_initiated())
        assert result.initiation_status == InitiationStatus.INITIATED

    def test_probability_positive(self, model: CorrosionModel) -> None:
        result = model.predict(_input(age_years=100.0), _carbonation_initiated())
        assert result.corrosion_probability_now > 0.0

    def test_probability_bounded_zero_to_one(self, model: CorrosionModel) -> None:
        for age in (10.0, 30.0, 100.0, 500.0):
            result = model.predict(_input(age_years=age), _carbonation_initiated())
            assert 0.0 <= result.corrosion_probability_now <= 1.0

    def test_propagation_rate_present(self, model: CorrosionModel) -> None:
        result = model.predict(_input(), _carbonation_initiated())
        assert result.propagation_rate_mm_per_year is not None
        assert result.propagation_rate_mm_per_year > 0.0

    def test_years_since_positive(self, model: CorrosionModel) -> None:
        """
        For an asset well past depassivation, years_since should be > 0.
        """
        # k_c=4.5, cover=40mm → t_dep = (40/4.5)^2 ≈ 79 years
        # asset_age=100 → years_since ≈ 21
        result = model.predict(
            _input(age_years=100.0, cover_mm=40.0),
            CarbonationProjection(
                depth_mm_now=45.0,
                time_to_depassivation_years=None,
                carbonation_rate_mm_per_sqrt_year=4.5,
            ),
        )
        assert result.years_since_initiation is not None
        assert result.years_since_initiation > 0.0

    def test_years_since_back_calculation(self) -> None:
        """
        years_since = max(0, age - t_dep) where t_dep = (cover / k_c)^2.
        """
        k_c = 5.0
        cover = 40.0
        age = 80.0
        t_dep = (cover / k_c) ** 2  # = 64
        expected_years_since = age - t_dep  # = 16

        carbonation = CarbonationProjection(
            depth_mm_now=50.0,
            time_to_depassivation_years=None,
            carbonation_rate_mm_per_sqrt_year=k_c,
        )
        model = CorrosionModel()
        result = model.predict(_input(age_years=age, cover_mm=cover), carbonation)
        assert result.years_since_initiation is not None
        assert abs(result.years_since_initiation - expected_years_since) < 1e-4

    def test_probability_increases_with_age(self, model: CorrosionModel) -> None:
        """More years since initiation → higher corrosion index."""
        r_early = model.predict(
            _input(age_years=30.0), _carbonation_initiated()
        )
        r_late = model.predict(
            _input(age_years=80.0), _carbonation_initiated()
        )
        assert r_late.corrosion_probability_now > r_early.corrosion_probability_now


# ---------------------------------------------------------------------------
# Physics formula verification: 1 - exp(-τ / τ_sat)
# ---------------------------------------------------------------------------


class TestPhysicsFormula:
    def test_corrosion_index_formula(self) -> None:
        """
        For known years_since and saturation_timescale, index must match formula.
        """
        sat = 20.0  # saturation timescale
        years_since = 10.0
        expected_index = 1.0 - math.exp(-years_since / sat)

        config = CorrosionModelConfig(
            rates={
                ExposureClass.XC3: CorrosionRateEntry(
                    propagation_rate_mm_per_year=0.05,
                    saturation_timescale_years=sat,
                )
            }
        )
        model = CorrosionModel(config=config)

        # k_c=5, cover=40 → t_dep=64; age=74 → years_since=10
        k_c = 5.0
        cover = 40.0
        age = (cover / k_c) ** 2 + years_since  # = 74

        result = model.predict(
            _input(age_years=age, cover_mm=cover),
            CarbonationProjection(
                depth_mm_now=cover + 1.0,
                time_to_depassivation_years=None,
                carbonation_rate_mm_per_sqrt_year=k_c,
            ),
        )
        assert result.corrosion_probability_now is not None
        assert abs(result.corrosion_probability_now - expected_index) < 1e-4

    def test_zero_years_since_gives_zero_index(self, model: CorrosionModel) -> None:
        """At initiation moment (years_since=0), index must be 0."""
        # Use secondary signal: age=0, severity=SEVERE → years_since=0.0
        result = model.predict(
            _input(age_years=0.0, observed_severity=SeverityLevel.SEVERE),
            _carbonation_not_initiated(),
        )
        assert result.corrosion_probability_now == 0.0

    def test_index_approaches_one_for_large_years_since(self) -> None:
        """Very long elapsed time → index approaches 1 (saturates)."""
        config = CorrosionModelConfig(
            rates={
                ExposureClass.XC3: CorrosionRateEntry(
                    propagation_rate_mm_per_year=0.05,
                    saturation_timescale_years=5.0,  # fast saturation
                )
            }
        )
        model = CorrosionModel(config=config)
        result = model.predict(
            _input(age_years=500.0, cover_mm=1.0),  # cover instantly exceeded
            _carbonation_initiated(),
        )
        assert result.corrosion_probability_now > 0.99


# ---------------------------------------------------------------------------
# Secondary initiation signal (severity fallback)
# ---------------------------------------------------------------------------


class TestSeverityFallback:
    def test_severe_severity_triggers_initiation(self, model: CorrosionModel) -> None:
        """
        SEVERE corrosion severity with no carbonation initiation should still
        trigger the secondary initiation signal.
        """
        result = model.predict(
            _input(observed_severity=SeverityLevel.SEVERE),
            _carbonation_not_initiated(),
        )
        assert result.initiation_status == InitiationStatus.INITIATED

    def test_critical_severity_triggers_initiation(self, model: CorrosionModel) -> None:
        result = model.predict(
            _input(observed_severity=SeverityLevel.CRITICAL),
            _carbonation_not_initiated(),
        )
        assert result.initiation_status == InitiationStatus.INITIATED

    def test_secondary_signal_years_since_is_zero(self, model: CorrosionModel) -> None:
        """Secondary signal sets years_since_initiation = 0.0 (conservative)."""
        result = model.predict(
            _input(observed_severity=SeverityLevel.SEVERE),
            _carbonation_not_initiated(),
        )
        assert result.years_since_initiation == 0.0

    def test_secondary_signal_gives_zero_probability(
        self, model: CorrosionModel
    ) -> None:
        """years_since=0 → index=0."""
        result = model.predict(
            _input(observed_severity=SeverityLevel.CRITICAL),
            _carbonation_not_initiated(),
        )
        assert result.corrosion_probability_now == 0.0

    def test_secondary_signal_propagation_rate_present(
        self, model: CorrosionModel
    ) -> None:
        """Even at initiation moment, propagation rate from config is returned."""
        result = model.predict(
            _input(observed_severity=SeverityLevel.SEVERE),
            _carbonation_not_initiated(),
        )
        assert result.propagation_rate_mm_per_year is not None

    def test_carbonation_initiation_takes_priority_over_secondary(
        self, model: CorrosionModel
    ) -> None:
        """
        When carbonation has already initiated, years_since must be derived
        from carbonation (not forced to 0.0 as secondary signal would give).
        Verify by checking years_since > 0 when age is well past t_dep.
        """
        result = model.predict(
            _input(age_years=100.0, cover_mm=20.0, observed_severity=SeverityLevel.SEVERE),
            _carbonation_initiated(k_c=4.5),
        )
        assert result.years_since_initiation is not None
        assert result.years_since_initiation > 0.0


# ---------------------------------------------------------------------------
# Already-past-depassivation with years-since back-calculation
# ---------------------------------------------------------------------------


class TestPostDepassivation:
    def test_status_initiated(self, model: CorrosionModel) -> None:
        result = model.predict(_input(age_years=80.0), _carbonation_initiated())
        assert result.initiation_status == InitiationStatus.INITIATED

    def test_years_since_non_negative(self, model: CorrosionModel) -> None:
        result = model.predict(_input(age_years=50.0), _carbonation_initiated())
        assert result.years_since_initiation is not None
        assert result.years_since_initiation >= 0.0


# ---------------------------------------------------------------------------
# Config override
# ---------------------------------------------------------------------------


class TestConfigOverride:
    def test_custom_config_propagation_rate_respected(self) -> None:
        custom_rate = 0.999
        config = CorrosionModelConfig(
            rates={
                ExposureClass.XC3: CorrosionRateEntry(
                    propagation_rate_mm_per_year=custom_rate,
                    saturation_timescale_years=20.0,
                )
            },
            engine_version="5.0.0",
        )
        model = CorrosionModel(config=config)
        result = model.predict(_input(), _carbonation_initiated())
        assert result.propagation_rate_mm_per_year == custom_rate

    def test_custom_engine_version(self) -> None:
        config = CorrosionModelConfig(engine_version="2.0.0")
        model = CorrosionModel(config=config)
        assert model._config.engine_version == "2.0.0"

    def test_default_model_instantiates_without_arguments(self) -> None:
        model = CorrosionModel()
        assert model is not None

    @pytest.mark.parametrize(
        "exposure_class",
        [ExposureClass.XC1, ExposureClass.XC2, ExposureClass.XC3, ExposureClass.XC4],
    )
    def test_all_exposure_classes_valid(
        self, model: CorrosionModel, exposure_class: ExposureClass
    ) -> None:
        result = model.predict(
            _input(exposure_class=exposure_class),
            _carbonation_not_initiated(),
        )
        assert isinstance(result, CorrosionProjection)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_input_same_output(self, model: CorrosionModel) -> None:
        ai = _input(age_years=60.0, cover_mm=30.0)
        carb = _carbonation_initiated(k_c=4.5)
        r1 = model.predict(ai, carb)
        r2 = model.predict(ai, carb)
        assert r1.corrosion_probability_now == r2.corrosion_probability_now
        assert r1.years_since_initiation == r2.years_since_initiation
        assert r1.initiation_status == r2.initiation_status
