"""
Unit and integration tests for degradation.service_life.ServiceLifeEstimator.

Test strategy
-------------
Tests are split into:
  1. Orchestration tests — verify each model is called exactly once and
     outputs are assembled correctly.
  2. Maintenance decision tests — verify typed MaintenanceDecision schema,
     threshold evaluations, and secondary initiation maintenance triggering.
  3. Integration tests — wire real concrete models and verify report
     schema validity and physical coherence.
  4. DI / config tests — verify constructor injection and config flags.
  5. Metadata tests — verify metadata keys and version tracking.
  6. Edge-case tests — zero-age asset, no inspection_id, determinism.

All tests are synchronous and self-contained.
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest

from degradation.carbonation import CarbonationModel
from degradation.config import MaintenanceThreshold
from degradation.corrosion import CorrosionModel
from degradation.models import ExposureClass, MaterialProperties
from degradation.schemas import (
    CarbonationProjection,
    CorrosionProjection,
    DegradationAssessmentInput,
    DegradationAssessmentReport,
    InitiationStatus,
    MaintenanceDecision,
)
from degradation.service_life import ServiceLifeEstimator, ServiceLifeEstimatorConfig
from intelligence.schemas import SeverityLevel  # noqa: TC001

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _input(
    age_years: float = 20.0,
    cover_mm: float = 40.0,
    exposure_class: ExposureClass = ExposureClass.XC3,
    asset_id: str = "asset-001",
    inspection_id: str | None = "insp-001",
    observed_severity: SeverityLevel | None = None,
) -> DegradationAssessmentInput:
    return DegradationAssessmentInput(
        asset_id=asset_id,
        inspection_id=inspection_id,
        asset_age_years=age_years,
        material_properties=MaterialProperties(concrete_cover_mm=cover_mm),
        exposure_class=exposure_class,
        observed_corrosion_severity=observed_severity,
    )


def _fake_carbonation(remaining: float | None = 50.0) -> CarbonationProjection:
    return CarbonationProjection(
        depth_mm_now=10.0,
        time_to_depassivation_years=remaining,
        carbonation_rate_mm_per_sqrt_year=4.5,
    )


def _fake_corrosion(
    status: InitiationStatus = InitiationStatus.NOT_INITIATED,
    index: float = 0.0,
) -> CorrosionProjection:
    return CorrosionProjection(
        initiation_status=status,
        years_since_initiation=None,
        corrosion_probability_now=index,
        propagation_rate_mm_per_year=None,
    )


@pytest.fixture
def estimator() -> ServiceLifeEstimator:
    return ServiceLifeEstimator()


# ---------------------------------------------------------------------------
# Return type and schema validity
# ---------------------------------------------------------------------------


class TestReturnTypeAndSchema:
    def test_returns_degradation_report(self, estimator: ServiceLifeEstimator) -> None:
        result = estimator.assess(_input())
        assert isinstance(result, DegradationAssessmentReport)

    def test_asset_id_propagated(self, estimator: ServiceLifeEstimator) -> None:
        result = estimator.assess(_input(asset_id="bridge-99"))
        assert result.asset_id == "bridge-99"

    def test_inspection_id_propagated(self, estimator: ServiceLifeEstimator) -> None:
        result = estimator.assess(_input(inspection_id="insp-XYZ"))
        assert result.inspection_id == "insp-XYZ"

    def test_inspection_id_none_propagated(self, estimator: ServiceLifeEstimator) -> None:
        result = estimator.assess(_input(inspection_id=None))
        assert result.inspection_id is None

    def test_carbonation_is_carbonation_projection(
        self, estimator: ServiceLifeEstimator
    ) -> None:
        result = estimator.assess(_input())
        assert isinstance(result.carbonation, CarbonationProjection)

    def test_corrosion_is_corrosion_projection(
        self, estimator: ServiceLifeEstimator
    ) -> None:
        result = estimator.assess(_input())
        assert isinstance(result.corrosion, CorrosionProjection)

    def test_maintenance_decision_is_typed(
        self, estimator: ServiceLifeEstimator
    ) -> None:
        result = estimator.assess(_input())
        assert isinstance(result.maintenance_decision, MaintenanceDecision)

    def test_metadata_is_dict(self, estimator: ServiceLifeEstimator) -> None:
        result = estimator.assess(_input())
        assert isinstance(result.metadata, dict)


# ---------------------------------------------------------------------------
# Orchestration: models called exactly once, in order
# ---------------------------------------------------------------------------


class TestOrchestration:
    def test_carbonation_model_called_exactly_once(self) -> None:
        mock_carbonation = MagicMock(spec=CarbonationModel)
        mock_carbonation.predict.return_value = _fake_carbonation()
        mock_corrosion = MagicMock(spec=CorrosionModel)
        mock_corrosion.predict.return_value = _fake_corrosion()

        estimator = ServiceLifeEstimator(
            carbonation_model=mock_carbonation,
            corrosion_model=mock_corrosion,
        )
        ai = _input()
        estimator.assess(ai)
        mock_carbonation.predict.assert_called_once_with(ai)

    def test_corrosion_model_called_exactly_once(self) -> None:
        fake_carb = _fake_carbonation()
        mock_carbonation = MagicMock(spec=CarbonationModel)
        mock_carbonation.predict.return_value = fake_carb
        mock_corrosion = MagicMock(spec=CorrosionModel)
        mock_corrosion.predict.return_value = _fake_corrosion()

        estimator = ServiceLifeEstimator(
            carbonation_model=mock_carbonation,
            corrosion_model=mock_corrosion,
        )
        ai = _input()
        estimator.assess(ai)
        mock_corrosion.predict.assert_called_once_with(ai, fake_carb)

    def test_carbonation_output_passed_to_corrosion(self) -> None:
        """The exact CarbonationProjection instance returned by the carbonation
        model must be forwarded to the corrosion model."""
        fake_carb = _fake_carbonation(remaining=None)
        mock_carbonation = MagicMock(spec=CarbonationModel)
        mock_carbonation.predict.return_value = fake_carb
        mock_corrosion = MagicMock(spec=CorrosionModel)
        mock_corrosion.predict.return_value = _fake_corrosion()

        estimator = ServiceLifeEstimator(
            carbonation_model=mock_carbonation,
            corrosion_model=mock_corrosion,
        )
        ai = _input()
        estimator.assess(ai)

        # The second argument to corrosion.predict must be the same object
        _, corr_call_args, _ = mock_corrosion.predict.mock_calls[0]
        assert corr_call_args[1] is fake_carb

    def test_carbonation_output_in_report(self) -> None:
        fake_carb = _fake_carbonation()
        mock_carbonation = MagicMock(spec=CarbonationModel)
        mock_carbonation.predict.return_value = fake_carb
        mock_corrosion = MagicMock(spec=CorrosionModel)
        mock_corrosion.predict.return_value = _fake_corrosion()

        estimator = ServiceLifeEstimator(
            carbonation_model=mock_carbonation,
            corrosion_model=mock_corrosion,
        )
        result = estimator.assess(_input())
        assert result.carbonation is fake_carb

    def test_corrosion_output_in_report(self) -> None:
        fake_corr = _fake_corrosion(InitiationStatus.INITIATED, 0.35)
        mock_carbonation = MagicMock(spec=CarbonationModel)
        mock_carbonation.predict.return_value = _fake_carbonation()
        mock_corrosion = MagicMock(spec=CorrosionModel)
        mock_corrosion.predict.return_value = fake_corr

        estimator = ServiceLifeEstimator(
            carbonation_model=mock_carbonation,
            corrosion_model=mock_corrosion,
        )
        result = estimator.assess(_input())
        assert result.corrosion is fake_corr


# ---------------------------------------------------------------------------
# Maintenance Decision logic
# ---------------------------------------------------------------------------


class TestMaintenanceDecision:
    def test_corrosion_ceiling_exceeded_triggers_maintenance(self) -> None:
        """When corrosion probability exceeds ceiling, maintenance_required is True."""
        config = ServiceLifeEstimatorConfig(
            maintenance_threshold=MaintenanceThreshold(corrosion_probability_ceiling=0.30)
        )
        mock_carb = MagicMock(spec=CarbonationModel)
        mock_carb.predict.return_value = _fake_carbonation()
        mock_corr = MagicMock(spec=CorrosionModel)
        mock_corr.predict.return_value = _fake_corrosion(
            InitiationStatus.INITIATED, index=0.50  # above 0.30 ceiling
        )
        estimator = ServiceLifeEstimator(
            carbonation_model=mock_carb,
            corrosion_model=mock_corr,
            config=config,
        )
        result = estimator.assess(_input())
        assert result.maintenance_decision.corrosion_index_exceeds_ceiling is True
        assert result.maintenance_decision.maintenance_required is True

    def test_below_thresholds_no_maintenance_required(self) -> None:
        config = ServiceLifeEstimatorConfig(
            maintenance_threshold=MaintenanceThreshold(corrosion_probability_ceiling=0.80)
        )
        mock_carb = MagicMock(spec=CarbonationModel)
        mock_carb.predict.return_value = _fake_carbonation()
        mock_corr = MagicMock(spec=CorrosionModel)
        mock_corr.predict.return_value = _fake_corrosion(index=0.10)
        estimator = ServiceLifeEstimator(
            carbonation_model=mock_carb,
            corrosion_model=mock_corr,
            config=config,
        )
        result = estimator.assess(_input())
        assert result.maintenance_decision.corrosion_index_exceeds_ceiling is False
        assert result.maintenance_decision.carbonation_exceeds_cover_fraction is False
        assert result.maintenance_decision.secondary_initiation_triggered is False
        assert result.maintenance_decision.maintenance_required is False

    def test_secondary_initiation_triggers_maintenance_required(self) -> None:
        """
        Resolves the contradiction: when secondary initiation is triggered by
        observed SEVERE corrosion, maintenance_required must be True even if
        carbonation depth has not reached cover (time_to_depassivation is not None)
        and corrosion_probability_now is 0.0.
        """
        estimator = ServiceLifeEstimator()
        result = estimator.assess(
            _input(
                age_years=5.0,
                cover_mm=50.0,  # thick cover -> carbonation hasn't reached cover
                observed_severity=SeverityLevel.SEVERE,
            )
        )
        assert result.corrosion.initiation_status == InitiationStatus.INITIATED
        assert result.carbonation.time_to_depassivation_years is not None
        assert result.corrosion.corrosion_probability_now == 0.0
        assert result.maintenance_decision.secondary_initiation_triggered is True
        assert result.maintenance_decision.maintenance_required is True


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_metadata_contains_service_key(self, estimator: ServiceLifeEstimator) -> None:
        result = estimator.assess(_input())
        assert result.metadata["service"] == "ServiceLifeEstimator"

    def test_metadata_contains_service_version(
        self, estimator: ServiceLifeEstimator
    ) -> None:
        result = estimator.assess(_input())
        assert "service_version" in result.metadata

    def test_metadata_contains_assessed_at_utc(
        self, estimator: ServiceLifeEstimator
    ) -> None:
        result = estimator.assess(_input())
        ts = result.metadata["assessed_at_utc"]
        assert isinstance(ts, str)
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts)

    def test_metadata_contains_asset_age(self, estimator: ServiceLifeEstimator) -> None:
        result = estimator.assess(_input(age_years=35.0))
        assert result.metadata["asset_age_years"] == 35.0

    def test_metadata_contains_exposure_class(
        self, estimator: ServiceLifeEstimator
    ) -> None:
        result = estimator.assess(_input(exposure_class=ExposureClass.XC4))
        assert result.metadata["exposure_class"] == ExposureClass.XC4

    def test_engine_versions_present_with_real_models(
        self, estimator: ServiceLifeEstimator
    ) -> None:
        result = estimator.assess(_input())
        versions = result.metadata.get("engine_versions", {})
        assert len(versions) > 0

    def test_engine_versions_suppressed_by_config(self) -> None:
        config = ServiceLifeEstimatorConfig(include_engine_versions=False)
        estimator = ServiceLifeEstimator(config=config)
        result = estimator.assess(_input())
        assert "engine_versions" not in result.metadata

    def test_custom_service_version(self) -> None:
        config = ServiceLifeEstimatorConfig(service_version="3.1.4")
        estimator = ServiceLifeEstimator(config=config)
        result = estimator.assess(_input())
        assert result.metadata["service_version"] == "3.1.4"


# ---------------------------------------------------------------------------
# Integration: real engines end-to-end
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_zero_age_asset(self, estimator: ServiceLifeEstimator) -> None:
        """Age 0: no carbonation accrued, no initiation."""
        result = estimator.assess(_input(age_years=0.0, cover_mm=40.0))
        assert result.carbonation.depth_mm_now == 0.0
        assert result.corrosion.initiation_status == InitiationStatus.NOT_INITIATED
        assert result.corrosion.corrosion_probability_now == 0.0
        assert result.maintenance_decision.maintenance_required is False
        assert result.requires_maintenance is False

    def test_young_asset_not_initiated(self, estimator: ServiceLifeEstimator) -> None:
        """5-year-old asset with 60 mm cover: carbonation hasn't reached cover."""
        result = estimator.assess(_input(age_years=5.0, cover_mm=60.0))
        assert result.corrosion.initiation_status == InitiationStatus.NOT_INITIATED
        assert result.carbonation.time_to_depassivation_years is not None
        assert result.carbonation.time_to_depassivation_years > 0.0
        assert result.maintenance_decision.maintenance_required is False
        assert result.requires_maintenance is False

    def test_old_thin_cover_asset_initiated(self, estimator: ServiceLifeEstimator) -> None:
        """
        100-year-old asset with only 10 mm cover in XC4 (k_c≈6):
        d_c = 6*sqrt(100) = 60mm >> 10mm → initiated.
        """
        result = estimator.assess(
            _input(
                age_years=100.0,
                cover_mm=10.0,
                exposure_class=ExposureClass.XC4,
            )
        )
        assert result.corrosion.initiation_status == InitiationStatus.INITIATED
        assert result.corrosion.corrosion_probability_now > 0.0
        assert result.maintenance_decision.maintenance_required is True
        assert result.requires_maintenance is True

    def test_report_depth_non_negative(self, estimator: ServiceLifeEstimator) -> None:
        for age in (0.0, 1.0, 10.0, 50.0, 100.0):
            result = estimator.assess(_input(age_years=age))
            assert result.carbonation.depth_mm_now >= 0.0

    def test_report_corrosion_index_in_range(
        self, estimator: ServiceLifeEstimator
    ) -> None:
        for age in (0.0, 20.0, 100.0):
            result = estimator.assess(_input(age_years=age))
            assert 0.0 <= result.corrosion.corrosion_probability_now <= 1.0

    def test_ids_match_input(self, estimator: ServiceLifeEstimator) -> None:
        ai = DegradationAssessmentInput(
            asset_id="bridge-007",
            inspection_id="insp-ABC",
            asset_age_years=30.0,
            material_properties=MaterialProperties(concrete_cover_mm=40.0),
            exposure_class=ExposureClass.XC3,
        )
        result = estimator.assess(ai)
        assert result.asset_id == "bridge-007"
        assert result.inspection_id == "insp-ABC"

    def test_determinism(self, estimator: ServiceLifeEstimator) -> None:
        ai = _input(age_years=45.0, cover_mm=35.0, exposure_class=ExposureClass.XC4)
        r1 = estimator.assess(ai)
        r2 = estimator.assess(ai)
        assert r1.carbonation.depth_mm_now == r2.carbonation.depth_mm_now
        assert (
            r1.corrosion.corrosion_probability_now
            == r2.corrosion.corrosion_probability_now
        )
        assert r1.corrosion.initiation_status == r2.corrosion.initiation_status
        assert r1.maintenance_decision == r2.maintenance_decision
        assert r1.requires_maintenance == r2.requires_maintenance

    def test_severity_fallback_triggers_requires_maintenance(
        self, estimator: ServiceLifeEstimator
    ) -> None:
        """
        Young asset (carbonation has NOT reached cover) but inspector observed
        CRITICAL corrosion severity. The secondary signal must still result in
        requires_maintenance=True, even though the numeric corrosion index is
        0.0 at the moment of initiation. This is the exact scenario the
        severity fallback exists to catch — regression test for the bug where
        requires_maintenance silently read False here.
        """
        result = estimator.assess(
            _input(age_years=5.0, cover_mm=60.0, observed_severity=SeverityLevel.CRITICAL)
        )
        assert result.corrosion.initiation_status == InitiationStatus.INITIATED
        assert result.corrosion.corrosion_probability_now == 0.0  # formula is still correct
        assert result.requires_maintenance is True  # but the DECISION must not be False

    def test_no_severity_no_carbonation_no_maintenance_required(
        self, estimator: ServiceLifeEstimator
    ) -> None:
        """Young asset, no observed severity, carbonation nowhere near cover:
        requires_maintenance must be False."""
        result = estimator.assess(_input(age_years=5.0, cover_mm=60.0))
        assert result.requires_maintenance is False


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------


class TestDependencyInjection:
    def test_default_estimator_instantiates_without_arguments(self) -> None:
        estimator = ServiceLifeEstimator()
        assert estimator is not None

    def test_partial_injection_uses_default_for_other(self) -> None:
        """Injecting only carbonation_model: corrosion_model defaults."""
        mock_carb = MagicMock(spec=CarbonationModel)
        mock_carb.predict.return_value = _fake_carbonation()
        estimator = ServiceLifeEstimator(carbonation_model=mock_carb)
        result = estimator.assess(_input())
        assert isinstance(result, DegradationAssessmentReport)

    def test_multiple_assess_calls_are_independent(
        self, estimator: ServiceLifeEstimator
    ) -> None:
        r_young = estimator.assess(_input(age_years=5.0, cover_mm=60.0))
        r_old = estimator.assess(_input(age_years=100.0, cover_mm=10.0))
        assert r_young.carbonation.depth_mm_now < r_old.carbonation.depth_mm_now
        assert r_young is not r_old
