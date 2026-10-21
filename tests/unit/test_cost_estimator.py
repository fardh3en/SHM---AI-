"""
Unit tests for recommendation.cost_estimator.CostEstimator.

Test strategy
-------------
Tests are organized by scenario type:
  - Config override: custom cost_rates produce expected range.
  - Determinism: identical inputs produce identical CostEstimate.
  - Emergency mobilization: EMERGENCY_INTERVENTION adds mobilization cost;
    all other action types do not.
  - Asset-type multiplier: different asset types scale the range as expected.
  - Area-based vs flat rate: categories with area_mm2 use rate * area;
    categories without use rate_per_unit flat.
  - Basis string: human-readable summary includes relevant details.
  - Decoupling: CostEstimator never constructs or returns a
    RecommendationDecision.
  - Return type validity: output is always a CostEstimate with low <= high.

All tests are synchronous and self-contained.
"""
from __future__ import annotations

import pytest

from intelligence.schemas import (
    AssetType,
    DefectCategory,
    DefectSeverityBreakdown,
    FailureModeCategory,
    HealthAssessmentReport,
    RiskLevel,
    SeverityLevel,
    StructuralFailureMode,
)
from degradation.schemas import (
    CarbonationProjection,
    CorrosionProjection,
    DegradationAssessmentReport,
    InitiationStatus,
    MaintenanceDecision,
)
from recommendation.config import (
    ASSET_TYPE_COST_MULTIPLIER,
    DEFAULT_COST_RATES,
    EMERGENCY_MOBILIZATION_COST,
    CostRate,
)
from recommendation.cost_estimator import CostEstimator, CostEstimatorConfig
from recommendation.engine import RecommendationEngine
from recommendation.schemas import (
    CostEstimate,
    EscalationTrace,
    RecommendationDecision,
    RecommendationInput,
    RecommendedActionType,
)


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _health_report(
    risk_level: RiskLevel = RiskLevel.LOW,
    severity_breakdown: list[DefectSeverityBreakdown] | None = None,
) -> HealthAssessmentReport:
    return HealthAssessmentReport(
        asset_id="asset-001",
        inspection_id="insp-001",
        health_score=80.0,
        risk_level=risk_level,
        severity_breakdown=severity_breakdown or [],
    )


def _decision(
    action: RecommendedActionType = RecommendedActionType.REPAIR,
) -> RecommendationDecision:
    """Build a minimal RecommendationDecision for testing cost-only logic."""
    return RecommendationDecision(
        recommended_action=action,
        escalation=EscalationTrace(
            baseline_action=action,
            degradation_escalation_applied=False,
            failure_mode_escalation_applied=False,
        ),
        next_inspection_interval_years=0.5,
    )


def _recommendation_input(
    asset_type: AssetType = AssetType.BUILDING,
    severity_breakdown: list[DefectSeverityBreakdown] | None = None,
    risk_level: RiskLevel = RiskLevel.HIGH,
) -> RecommendationInput:
    return RecommendationInput(
        asset_id="asset-001",
        inspection_id="insp-001",
        asset_type=asset_type,
        health_report=_health_report(
            risk_level=risk_level,
            severity_breakdown=severity_breakdown,
        ),
    )


def _crack_breakdown(area_mm2: float | None = 10_000.0) -> DefectSeverityBreakdown:
    return DefectSeverityBreakdown(
        defect_category=DefectCategory.CRACK,
        severity=SeverityLevel.MODERATE,
        observation_count=1,
        total_area_mm2=area_mm2,
    )


@pytest.fixture
def estimator() -> CostEstimator:
    return CostEstimator()


# ---------------------------------------------------------------------------
# Return type validity
# ---------------------------------------------------------------------------


class TestReturnTypeValidity:
    def test_returns_cost_estimate(self, estimator: CostEstimator) -> None:
        inp = _recommendation_input()
        decision = _decision()
        result = estimator.estimate(inp, decision)
        assert isinstance(result, CostEstimate)

    def test_low_le_high(self, estimator: CostEstimator) -> None:
        inp = _recommendation_input(severity_breakdown=[_crack_breakdown()])
        decision = _decision()
        result = estimator.estimate(inp, decision)
        assert result.low <= result.high

    def test_currency_is_usd(self, estimator: CostEstimator) -> None:
        result = estimator.estimate(_recommendation_input(), _decision())
        assert result.currency == "USD"

    def test_basis_is_nonempty_string(self, estimator: CostEstimator) -> None:
        result = estimator.estimate(_recommendation_input(), _decision())
        assert isinstance(result.basis, str) and len(result.basis) > 0

    def test_low_and_high_non_negative(self, estimator: CostEstimator) -> None:
        result = estimator.estimate(_recommendation_input(), _decision())
        assert result.low >= 0.0
        assert result.high >= 0.0


# ---------------------------------------------------------------------------
# Emergency mobilization
# ---------------------------------------------------------------------------


class TestEmergencyMobilization:
    """EMERGENCY_INTERVENTION adds mobilization; other actions do not."""

    @pytest.mark.parametrize(
        "action",
        [
            RecommendedActionType.MONITOR,
            RecommendedActionType.INSPECT,
            RecommendedActionType.REPAIR,
        ],
    )
    def test_non_emergency_no_mobilization(
        self, estimator: CostEstimator, action: RecommendedActionType
    ) -> None:
        """Non-emergency decisions must not include mobilization cost."""
        inp = _recommendation_input(severity_breakdown=[_crack_breakdown()])
        non_emg_decision = _decision(action=action)
        emg_decision = _decision(action=RecommendedActionType.EMERGENCY_INTERVENTION)

        non_emg_result = estimator.estimate(inp, non_emg_decision)
        emg_result = estimator.estimate(inp, emg_decision)

        # Emergency result must be strictly higher (mobilization added).
        assert emg_result.low > non_emg_result.low
        assert emg_result.high > non_emg_result.high

    def test_emergency_adds_mobilization_cost(self, estimator: CostEstimator) -> None:
        """EMERGENCY_INTERVENTION adds exactly the configured mobilization range."""
        emg = EMERGENCY_MOBILIZATION_COST
        asset_multiplier = ASSET_TYPE_COST_MULTIPLIER[AssetType.BUILDING]

        # Use no defect breakdown so only the mobilization cost contributes.
        inp = _recommendation_input(severity_breakdown=[])
        emg_decision = _decision(action=RecommendedActionType.EMERGENCY_INTERVENTION)
        non_emg_decision = _decision(action=RecommendedActionType.REPAIR)

        emg_result = estimator.estimate(inp, emg_decision)
        non_emg_result = estimator.estimate(inp, non_emg_decision)

        expected_low_delta = emg.rate_per_unit * emg.low_multiplier
        expected_high_delta = emg.rate_per_unit * emg.high_multiplier

        assert emg_result.low == pytest.approx(non_emg_result.low + expected_low_delta)
        assert emg_result.high == pytest.approx(non_emg_result.high + expected_high_delta)

    def test_emergency_basis_mentions_mobilization(
        self, estimator: CostEstimator
    ) -> None:
        inp = _recommendation_input()
        decision = _decision(action=RecommendedActionType.EMERGENCY_INTERVENTION)
        result = estimator.estimate(inp, decision)
        assert "emergency mobilization" in result.basis.lower()

    def test_non_emergency_basis_no_mobilization_mention(
        self, estimator: CostEstimator
    ) -> None:
        inp = _recommendation_input()
        decision = _decision(action=RecommendedActionType.REPAIR)
        result = estimator.estimate(inp, decision)
        assert "emergency mobilization" not in result.basis.lower()


# ---------------------------------------------------------------------------
# Asset-type multiplier
# ---------------------------------------------------------------------------


class TestAssetTypeMultiplier:
    """Different asset types scale the cost range as expected."""

    def test_bridge_more_expensive_than_building(
        self, estimator: CostEstimator
    ) -> None:
        breakdown = [_crack_breakdown(area_mm2=5_000.0)]
        decision = _decision()

        bridge_inp = _recommendation_input(
            asset_type=AssetType.BRIDGE, severity_breakdown=breakdown
        )
        building_inp = _recommendation_input(
            asset_type=AssetType.BUILDING, severity_breakdown=breakdown
        )

        bridge_result = estimator.estimate(bridge_inp, decision)
        building_result = estimator.estimate(building_inp, decision)

        # Bridge multiplier (1.8) > building multiplier (1.0)
        assert bridge_result.low > building_result.low
        assert bridge_result.high > building_result.high

    def test_dam_most_expensive(self, estimator: CostEstimator) -> None:
        breakdown = [_crack_breakdown(area_mm2=5_000.0)]
        decision = _decision()

        dam_inp = _recommendation_input(
            asset_type=AssetType.DAM, severity_breakdown=breakdown
        )
        building_inp = _recommendation_input(
            asset_type=AssetType.BUILDING, severity_breakdown=breakdown
        )

        dam_result = estimator.estimate(dam_inp, decision)
        building_result = estimator.estimate(building_inp, decision)

        # Dam multiplier (2.5) > building multiplier (1.0)
        assert dam_result.low > building_result.low

    def test_multiplier_scales_linearly(self, estimator: CostEstimator) -> None:
        """The asset multiplier must scale the result by exactly the configured factor."""
        breakdown = [_crack_breakdown(area_mm2=10_000.0)]
        decision = _decision()

        bridge_inp = _recommendation_input(
            asset_type=AssetType.BRIDGE, severity_breakdown=breakdown
        )
        building_inp = _recommendation_input(
            asset_type=AssetType.BUILDING, severity_breakdown=breakdown
        )

        bridge_result = estimator.estimate(bridge_inp, decision)
        building_result = estimator.estimate(building_inp, decision)

        bridge_multiplier = ASSET_TYPE_COST_MULTIPLIER[AssetType.BRIDGE]
        building_multiplier = ASSET_TYPE_COST_MULTIPLIER[AssetType.BUILDING]

        assert bridge_result.low == pytest.approx(
            building_result.low * (bridge_multiplier / building_multiplier)
        )


# ---------------------------------------------------------------------------
# Area-based vs flat rate
# ---------------------------------------------------------------------------


class TestAreaBasedVsFlat:
    """total_area_mm2 present → rate * area; absent → flat rate_per_unit."""

    def test_area_based_cost_computed_correctly(
        self, estimator: CostEstimator
    ) -> None:
        area = 20_000.0
        rate = DEFAULT_COST_RATES[DefectCategory.CRACK]
        breakdown = [_crack_breakdown(area_mm2=area)]
        inp = _recommendation_input(
            asset_type=AssetType.BUILDING, severity_breakdown=breakdown
        )
        decision = _decision(action=RecommendedActionType.REPAIR)
        result = estimator.estimate(inp, decision)

        asset_mult = ASSET_TYPE_COST_MULTIPLIER[AssetType.BUILDING]
        expected_low = rate.rate_per_unit * area * rate.low_multiplier * asset_mult
        expected_high = rate.rate_per_unit * area * rate.high_multiplier * asset_mult

        assert result.low == pytest.approx(expected_low, rel=1e-6)
        assert result.high == pytest.approx(expected_high, rel=1e-6)

    def test_no_area_uses_flat_rate(self, estimator: CostEstimator) -> None:
        """When total_area_mm2 is None, the flat rate is used."""
        rate = DEFAULT_COST_RATES[DefectCategory.CRACK]
        breakdown_no_area = [_crack_breakdown(area_mm2=None)]
        breakdown_with_area = [_crack_breakdown(area_mm2=1.0)]  # 1mm² → approximately flat

        inp_no_area = _recommendation_input(
            asset_type=AssetType.BUILDING, severity_breakdown=breakdown_no_area
        )
        inp_1mm2 = _recommendation_input(
            asset_type=AssetType.BUILDING, severity_breakdown=breakdown_with_area
        )
        decision = _decision()

        result_no_area = estimator.estimate(inp_no_area, decision)
        result_1mm2 = estimator.estimate(inp_1mm2, decision)

        # Both should produce the same result since flat rate = rate_per_unit * 1mm²
        assert result_no_area.low == pytest.approx(result_1mm2.low, rel=1e-6)
        assert result_no_area.high == pytest.approx(result_1mm2.high, rel=1e-6)


# ---------------------------------------------------------------------------
# Config override
# ---------------------------------------------------------------------------


class TestConfigOverride:
    def test_custom_cost_rate_produces_expected_range(self) -> None:
        """Custom cost rates must be applied instead of defaults."""
        custom_rates = {
            DefectCategory.CRACK: CostRate(
                rate_per_unit=1.0,  # $1.0/mm²
                unit="mm2",
                low_multiplier=1.0,
                high_multiplier=2.0,
            ),
        }
        custom_multipliers = {AssetType.BUILDING: 1.0}
        config = CostEstimatorConfig(
            cost_rates=custom_rates,  # type: ignore[arg-type]
            asset_multipliers=custom_multipliers,  # type: ignore[arg-type]
        )
        estimator = CostEstimator(config=config)

        area = 500.0
        breakdown = [_crack_breakdown(area_mm2=area)]
        inp = _recommendation_input(
            asset_type=AssetType.BUILDING, severity_breakdown=breakdown
        )
        decision = _decision(action=RecommendedActionType.REPAIR)
        result = estimator.estimate(inp, decision)

        assert result.low == pytest.approx(500.0)   # 1.0 * 500 * 1.0
        assert result.high == pytest.approx(1000.0)  # 1.0 * 500 * 2.0

    def test_custom_emergency_cost(self) -> None:
        """Custom emergency_cost overrides default mobilization amount."""
        custom_emg = CostRate(
            rate_per_unit=1_000.0,
            unit="flat",
            low_multiplier=1.0,
            high_multiplier=1.0,
        )
        config = CostEstimatorConfig(emergency_cost=custom_emg)
        estimator = CostEstimator(config=config)

        inp = _recommendation_input(severity_breakdown=[])
        decision = _decision(action=RecommendedActionType.EMERGENCY_INTERVENTION)
        result = estimator.estimate(inp, decision)

        assert result.low == pytest.approx(1_000.0)
        assert result.high == pytest.approx(1_000.0)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_identical_inputs_produce_identical_estimates(
        self, estimator: CostEstimator
    ) -> None:
        breakdown = [_crack_breakdown(area_mm2=5_000.0)]
        inp = _recommendation_input(severity_breakdown=breakdown)
        decision = _decision()

        r1 = estimator.estimate(inp, decision)
        r2 = estimator.estimate(inp, decision)

        assert r1.low == r2.low
        assert r1.high == r2.high
        assert r1.basis == r2.basis
        assert r1.currency == r2.currency


# ---------------------------------------------------------------------------
# Decoupling enforcement
# ---------------------------------------------------------------------------


class TestDecoupling:
    """CostEstimator must never construct or return a RecommendationDecision."""

    def test_estimate_never_returns_recommendation_decision(
        self, estimator: CostEstimator
    ) -> None:
        inp = _recommendation_input()
        decision = _decision()
        result = estimator.estimate(inp, decision)
        assert not isinstance(result, RecommendationDecision)

    def test_cost_estimator_does_not_import_engine(self) -> None:
        """cost_estimator.py must not import engine.py at the source level."""
        import pathlib

        ce_path = (
            pathlib.Path(__file__).parent.parent.parent
            / "recommendation"
            / "cost_estimator.py"
        )
        source = ce_path.read_text(encoding="utf-8")
        assert "from recommendation.engine" not in source
        assert "import engine" not in source
