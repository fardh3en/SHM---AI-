"""
Unit tests for degradation.carbonation.CarbonationModel.

Test strategy
-------------
Tests are organized by scenario type:
  - Zero-age asset (no depth accrued)
  - Pre-depassivation (cover not yet reached)
  - Already-past-depassivation (cover exceeded)
  - Exact depassivation boundary (depth == cover)
  - Config override (custom coefficients)
  - w/c ratio adjustment
  - Physics formula verification (d_c = k_c * sqrt(t))
  - Return-type and field-range validity

All tests are synchronous and self-contained.
"""
from __future__ import annotations

import math

import pytest

from degradation.carbonation import CarbonationModel, CarbonationModelConfig
from degradation.config import CarbonationCoefficient
from degradation.models import ExposureClass, MaterialProperties
from degradation.schemas import CarbonationProjection, DegradationAssessmentInput

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _input(
    age_years: float = 20.0,
    cover_mm: float = 40.0,
    exposure_class: ExposureClass = ExposureClass.XC3,
    water_cement_ratio: float | None = None,
) -> DegradationAssessmentInput:
    return DegradationAssessmentInput(
        asset_id="asset-001",
        inspection_id="insp-001",
        asset_age_years=age_years,
        material_properties=MaterialProperties(
            concrete_cover_mm=cover_mm,
            water_cement_ratio=water_cement_ratio,
        ),
        exposure_class=exposure_class,
    )


@pytest.fixture
def model() -> CarbonationModel:
    return CarbonationModel()


# ---------------------------------------------------------------------------
# Return type and schema validity
# ---------------------------------------------------------------------------


class TestReturnTypeAndSchema:
    def test_returns_carbonation_projection(self, model: CarbonationModel) -> None:
        result = model.predict(_input())
        assert isinstance(result, CarbonationProjection)

    def test_depth_mm_now_non_negative(self, model: CarbonationModel) -> None:
        result = model.predict(_input(age_years=10.0))
        assert result.depth_mm_now >= 0.0

    def test_carbonation_rate_non_negative(self, model: CarbonationModel) -> None:
        result = model.predict(_input())
        assert result.carbonation_rate_mm_per_sqrt_year >= 0.0

    def test_time_to_depassivation_none_or_positive(
        self, model: CarbonationModel
    ) -> None:
        result = model.predict(_input())
        if result.time_to_depassivation_years is not None:
            assert result.time_to_depassivation_years > 0.0


# ---------------------------------------------------------------------------
# Zero-age asset
# ---------------------------------------------------------------------------


class TestZeroAge:
    def test_zero_age_depth_is_zero(self, model: CarbonationModel) -> None:
        """At age 0, sqrt(0) = 0, so depth must be 0."""
        result = model.predict(_input(age_years=0.0, cover_mm=40.0))
        assert result.depth_mm_now == 0.0

    def test_zero_age_depassivation_not_none(self, model: CarbonationModel) -> None:
        """At age 0, cover is definitely not yet exceeded — remaining must be positive."""
        result = model.predict(_input(age_years=0.0, cover_mm=40.0))
        assert result.time_to_depassivation_years is not None
        assert result.time_to_depassivation_years > 0.0

    def test_zero_age_rate_positive(self, model: CarbonationModel) -> None:
        result = model.predict(_input(age_years=0.0))
        assert result.carbonation_rate_mm_per_sqrt_year > 0.0


# ---------------------------------------------------------------------------
# Physics formula verification: d_c = k_c * sqrt(t)
# ---------------------------------------------------------------------------


class TestPhysicsFormula:
    def test_depth_matches_formula(self) -> None:
        """
        For known k_c and age, depth_mm_now must equal k_c * sqrt(age).
        Use a custom config with a known coefficient.
        """
        k_c = 5.0
        age = 16.0  # sqrt(16) = 4  →  depth = 20.0
        config = CarbonationModelConfig(
            coefficients={
                ExposureClass.XC3: CarbonationCoefficient(
                    k_c_base=k_c, wc_adjustment_slope=0.0
                )
            }
        )
        model = CarbonationModel(config=config)
        result = model.predict(_input(age_years=age, cover_mm=100.0))
        expected = k_c * math.sqrt(age)
        assert abs(result.depth_mm_now - expected) < 1e-6

    def test_depth_increases_with_age(self, model: CarbonationModel) -> None:
        r1 = model.predict(_input(age_years=10.0, cover_mm=100.0))
        r2 = model.predict(_input(age_years=20.0, cover_mm=100.0))
        assert r2.depth_mm_now > r1.depth_mm_now

    def test_depassivation_time_closed_form(self) -> None:
        """
        t_dep = (cover / k_c)^2.  remaining = t_dep - age.
        """
        k_c = 4.0
        cover = 40.0
        age = 10.0
        t_dep = (cover / k_c) ** 2  # = 100 years
        expected_remaining = t_dep - age  # = 90 years

        config = CarbonationModelConfig(
            coefficients={
                ExposureClass.XC3: CarbonationCoefficient(
                    k_c_base=k_c, wc_adjustment_slope=0.0
                )
            }
        )
        model = CarbonationModel(config=config)
        result = model.predict(_input(age_years=age, cover_mm=cover))
        assert result.time_to_depassivation_years is not None
        assert abs(result.time_to_depassivation_years - expected_remaining) < 1e-4


# ---------------------------------------------------------------------------
# Pre-depassivation (cover not yet reached)
# ---------------------------------------------------------------------------


class TestPreDepassivation:
    def test_time_to_depassivation_is_positive(self, model: CarbonationModel) -> None:
        """Young asset, thick cover — depassivation is in the future."""
        result = model.predict(_input(age_years=5.0, cover_mm=60.0))
        assert result.time_to_depassivation_years is not None
        assert result.time_to_depassivation_years > 0.0

    def test_depth_less_than_cover(self, model: CarbonationModel) -> None:
        result = model.predict(_input(age_years=5.0, cover_mm=60.0))
        assert result.depth_mm_now < 60.0

    def test_remaining_decreases_as_age_increases(
        self, model: CarbonationModel
    ) -> None:
        r_early = model.predict(_input(age_years=5.0, cover_mm=80.0))
        r_later = model.predict(_input(age_years=10.0, cover_mm=80.0))
        assert r_early.time_to_depassivation_years is not None
        assert r_later.time_to_depassivation_years is not None
        assert r_later.time_to_depassivation_years < r_early.time_to_depassivation_years


# ---------------------------------------------------------------------------
# Already-past-depassivation (cover exceeded)
# ---------------------------------------------------------------------------


class TestPostDepassivation:
    def test_time_to_depassivation_is_none(self, model: CarbonationModel) -> None:
        """Old asset, thin cover — cover already exceeded."""
        result = model.predict(_input(age_years=100.0, cover_mm=10.0))
        assert result.time_to_depassivation_years is None

    def test_depth_exceeds_cover(self, model: CarbonationModel) -> None:
        result = model.predict(_input(age_years=100.0, cover_mm=10.0))
        assert result.depth_mm_now > 10.0

    def test_no_error_on_deeply_past_depassivation(
        self, model: CarbonationModel
    ) -> None:
        """Should not raise even when depth far exceeds cover."""
        result = model.predict(_input(age_years=200.0, cover_mm=5.0))
        assert result.depth_mm_now > 0.0
        assert result.time_to_depassivation_years is None


# ---------------------------------------------------------------------------
# Boundary: depth exactly equals cover
# ---------------------------------------------------------------------------


class TestDepassivationBoundary:
    def test_depth_equal_to_cover_returns_none(self) -> None:
        """
        When age is exactly t_dep = (cover/k_c)^2, remaining = 0.
        remaining <= 0 → None.
        """
        k_c = 5.0
        cover = 50.0
        t_dep = (cover / k_c) ** 2  # exactly 100 years

        config = CarbonationModelConfig(
            coefficients={
                ExposureClass.XC3: CarbonationCoefficient(
                    k_c_base=k_c, wc_adjustment_slope=0.0
                )
            }
        )
        model = CarbonationModel(config=config)
        result = model.predict(_input(age_years=t_dep, cover_mm=cover))
        assert result.time_to_depassivation_years is None


# ---------------------------------------------------------------------------
# w/c ratio adjustment
# ---------------------------------------------------------------------------


class TestWaterCementAdjustment:
    def test_higher_wc_gives_larger_k_c(self) -> None:
        """Higher w/c → more permeable → faster carbonation."""
        r_low = CarbonationModel().predict(
            _input(water_cement_ratio=0.40, age_years=20.0, cover_mm=100.0)
        )
        r_high = CarbonationModel().predict(
            _input(water_cement_ratio=0.65, age_years=20.0, cover_mm=100.0)
        )
        assert r_high.depth_mm_now > r_low.depth_mm_now
        assert (
            r_high.carbonation_rate_mm_per_sqrt_year
            > r_low.carbonation_rate_mm_per_sqrt_year
        )

    def test_none_wc_uses_base_k_c(self) -> None:
        """No w/c data: k_c should equal k_c_base (no adjustment)."""
        k_c_base = 4.5
        config = CarbonationModelConfig(
            coefficients={
                ExposureClass.XC3: CarbonationCoefficient(
                    k_c_base=k_c_base,
                    wc_adjustment_slope=5.0,
                    wc_reference=0.50,
                )
            }
        )
        model = CarbonationModel(config=config)
        result = model.predict(_input(water_cement_ratio=None))
        assert abs(result.carbonation_rate_mm_per_sqrt_year - k_c_base) < 1e-9

    def test_reference_wc_gives_zero_adjustment(self) -> None:
        """w/c == wc_reference → k_c == k_c_base (zero deviation)."""
        k_c_base = 4.5
        wc_ref = 0.50
        config = CarbonationModelConfig(
            coefficients={
                ExposureClass.XC3: CarbonationCoefficient(
                    k_c_base=k_c_base,
                    wc_adjustment_slope=5.0,
                    wc_reference=wc_ref,
                )
            }
        )
        model = CarbonationModel(config=config)
        result = model.predict(_input(water_cement_ratio=wc_ref))
        assert abs(result.carbonation_rate_mm_per_sqrt_year - k_c_base) < 1e-9


# ---------------------------------------------------------------------------
# Exposure class variation
# ---------------------------------------------------------------------------


class TestExposureClassVariation:
    @pytest.mark.parametrize(
        "exposure_class",
        [ExposureClass.XC1, ExposureClass.XC2, ExposureClass.XC3, ExposureClass.XC4],
    )
    def test_all_exposure_classes_produce_valid_output(
        self, model: CarbonationModel, exposure_class: ExposureClass
    ) -> None:
        result = model.predict(
            _input(age_years=20.0, cover_mm=40.0, exposure_class=exposure_class)
        )
        assert result.depth_mm_now >= 0.0
        assert result.carbonation_rate_mm_per_sqrt_year > 0.0

    def test_xc4_deeper_than_xc1(self, model: CarbonationModel) -> None:
        """XC4 (harshest) must produce deeper carbonation than XC1 (mildest)."""
        r_xc1 = model.predict(_input(age_years=20.0, exposure_class=ExposureClass.XC1))
        r_xc4 = model.predict(_input(age_years=20.0, exposure_class=ExposureClass.XC4))
        assert r_xc4.depth_mm_now > r_xc1.depth_mm_now


# ---------------------------------------------------------------------------
# Config override
# ---------------------------------------------------------------------------


class TestConfigOverride:
    def test_custom_config_respected(self) -> None:
        custom_k_c = 10.0
        config = CarbonationModelConfig(
            coefficients={
                ExposureClass.XC3: CarbonationCoefficient(
                    k_c_base=custom_k_c, wc_adjustment_slope=0.0
                )
            },
            engine_version="9.9.9",
        )
        model = CarbonationModel(config=config)
        result = model.predict(_input(age_years=4.0, cover_mm=100.0))
        # depth = 10 * sqrt(4) = 20.0
        assert abs(result.depth_mm_now - 20.0) < 1e-6
        assert abs(result.carbonation_rate_mm_per_sqrt_year - custom_k_c) < 1e-9
        assert model._config.engine_version == "9.9.9"

    def test_default_model_instantiates_without_arguments(self) -> None:
        model = CarbonationModel()
        assert model is not None

    def test_engine_version_default(self) -> None:
        model = CarbonationModel()
        assert model._config.engine_version == "1.0.0"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_input_same_output(self, model: CarbonationModel) -> None:
        ai = _input(age_years=25.0, cover_mm=40.0, water_cement_ratio=0.55)
        r1 = model.predict(ai)
        r2 = model.predict(ai)
        assert r1.depth_mm_now == r2.depth_mm_now
        assert r1.time_to_depassivation_years == r2.time_to_depassivation_years
        assert r1.carbonation_rate_mm_per_sqrt_year == r2.carbonation_rate_mm_per_sqrt_year
