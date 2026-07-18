"""
Unit tests for intelligence.engineering_rules.EngineeringRulesEngine.

All tests are fully deterministic and self-contained — no external services,
no database, no LLM calls. Tests follow the same conventions as the existing
test suite (synchronous, fixture-free where possible).

Coverage matrix
---------------
Category              | What is tested
--------------------- | ----------------------------------------------------------
Empty input           | No observations → empty result
No matching rules     | Observations below all thresholds → empty result
Rule: severe cracking + rebar    | Fires; confidence in [base, ceiling]
Rule: corrosion + rebar          | Fires; correct category; right confidence range
Rule: extensive spalling         | Area threshold gating; count fallback
Rule: multiple major defects     | ≥3 significant categories triggers; 2 does not
Rule: widespread delamination    | Area threshold; count fallback
Rule: crack network instability  | ≥3 cracks with width ≥ 0.5 mm
Rule: significant material loss  | Spalling + corrosion combined area
Rule: corrosion+spalling+rebar   | Trinity rule; highest base confidence
Rule: delamination + spalling    | Combined area gate; pair alone does not qualify
Confidence bounds                | All returned confidences in [0, 1]
Deduplication / independence     | Multiple rules can fire in the same call
Custom config                    | Engine respects injected EngineeringRulesConfig
related_defect_categories        | Correct categories listed per rule
"""
import pytest

from intelligence.engineering_rules import (
    DEFAULT_RULES,
    EngineeringRule,
    EngineeringRulesConfig,
    EngineeringRulesEngine,
)
from intelligence.schemas import (
    AssetType,
    DefectCategory,
    DefectObservation,
    FailureModeCategory,
    HealthAssessmentInput,
    StructuralFailureMode,
)

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _input(*observations: DefectObservation) -> HealthAssessmentInput:
    return HealthAssessmentInput(
        asset_id="test-asset-1",
        asset_type=AssetType.BRIDGE,
        inspection_id="insp-001",
        observations=list(observations),
    )


def _obs(
    category: DefectCategory,
    confidence: float = 0.85,
    *,
    area_mm2: float | None = None,
    width_mm: float | None = None,
    max_width_mm: float | None = None,
) -> DefectObservation:
    return DefectObservation(
        defect_category=category,
        confidence=confidence,
        area_mm2=area_mm2,
        width_mm=width_mm,
        max_width_mm=max_width_mm,
    )


# ---------------------------------------------------------------------------
# Shorthand helpers for common observation types
# ---------------------------------------------------------------------------

CRACK = DefectCategory.CRACK
SPALL = DefectCategory.SPALLING
CORRODE = DefectCategory.CORROSION
REBAR = DefectCategory.EXPOSED_REINFORCEMENT
DELAM = DefectCategory.DELAMINATION
POTHOLE = DefectCategory.POTHOLE
SURFACE = DefectCategory.SURFACE_DAMAGE


# ---------------------------------------------------------------------------
# Fixture — default engine
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> EngineeringRulesEngine:
    return EngineeringRulesEngine()


# ---------------------------------------------------------------------------
# Empty / no-match cases
# ---------------------------------------------------------------------------


def test_empty_observations_returns_empty(engine: EngineeringRulesEngine) -> None:
    result = engine.identify_failure_modes(_input())
    assert result == []


def test_single_low_confidence_crack_no_match(engine: EngineeringRulesEngine) -> None:
    """One hairline crack — no rule should fire."""
    result = engine.identify_failure_modes(
        _input(_obs(CRACK, 0.50, width_mm=0.1, max_width_mm=0.1))
    )
    assert result == []


def test_surface_damage_only_no_match(engine: EngineeringRulesEngine) -> None:
    """Surface damage alone should not trigger any structural failure rule."""
    result = engine.identify_failure_modes(
        _input(
            _obs(SURFACE, 0.90, area_mm2=10_000.0),
            _obs(SURFACE, 0.80, area_mm2=8_000.0),
        )
    )
    assert result == []


def test_pothole_only_no_match(engine: EngineeringRulesEngine) -> None:
    result = engine.identify_failure_modes(
        _input(_obs(POTHOLE, 0.90, area_mm2=50_000.0))
    )
    assert result == []


# ---------------------------------------------------------------------------
# Rule: severe cracking with exposed reinforcement
# ---------------------------------------------------------------------------


class TestSevereCrackingWithRebar:
    def test_fires_with_wide_crack_and_rebar(self, engine: EngineeringRulesEngine) -> None:
        result = engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.90, width_mm=2.5, max_width_mm=2.5),
                _obs(REBAR, 0.85, area_mm2=5_000.0),
            )
        )
        categories = [fm.category for fm in result]
        assert FailureModeCategory.FLEXURAL in categories

    def test_confidence_within_bounds(self, engine: EngineeringRulesEngine) -> None:
        result = engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.90, width_mm=3.0, max_width_mm=3.0),
                _obs(REBAR, 0.80, area_mm2=10_000.0),
            )
        )
        flexural = next(fm for fm in result if fm.category == FailureModeCategory.FLEXURAL)
        assert 0.65 <= flexural.confidence <= 0.90

    def test_does_not_fire_without_rebar(self, engine: EngineeringRulesEngine) -> None:
        result = engine.identify_failure_modes(
            _input(_obs(CRACK, 0.90, width_mm=3.0, max_width_mm=3.0))
        )
        categories = [fm.category for fm in result]
        assert FailureModeCategory.FLEXURAL not in categories

    def test_does_not_fire_with_narrow_single_crack(
        self, engine: EngineeringRulesEngine
    ) -> None:
        """Crack width < 1.0 mm and count == 1 → does not qualify."""
        result = engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.90, width_mm=0.3, max_width_mm=0.3),
                _obs(REBAR, 0.90, area_mm2=5_000.0),
            )
        )
        categories = [fm.category for fm in result]
        assert FailureModeCategory.FLEXURAL not in categories

    def test_fires_with_multiple_cracks_no_width_data(
        self, engine: EngineeringRulesEngine
    ) -> None:
        """≥ 2 cracks with no width data → conservative fallback triggers rule."""
        result = engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.80),
                _obs(CRACK, 0.75),
                _obs(REBAR, 0.85, area_mm2=3_000.0),
            )
        )
        categories = [fm.category for fm in result]
        assert FailureModeCategory.FLEXURAL in categories

    def test_related_categories_correct(self, engine: EngineeringRulesEngine) -> None:
        result = engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.90, width_mm=2.0, max_width_mm=2.0),
                _obs(REBAR, 0.85, area_mm2=5_000.0),
            )
        )
        flexural = next(fm for fm in result if fm.category == FailureModeCategory.FLEXURAL)
        assert CRACK in flexural.related_defect_categories
        assert REBAR in flexural.related_defect_categories


# ---------------------------------------------------------------------------
# Rule: corrosion with exposed reinforcement
# ---------------------------------------------------------------------------


class TestCorrosionWithRebar:
    def test_fires_when_both_present(self, engine: EngineeringRulesEngine) -> None:
        result = engine.identify_failure_modes(
            _input(
                _obs(CORRODE, 0.85, area_mm2=20_000.0),
                _obs(REBAR, 0.80, area_mm2=5_000.0),
            )
        )
        categories = [fm.category for fm in result]
        assert FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS in categories

    def test_does_not_fire_without_rebar(self, engine: EngineeringRulesEngine) -> None:
        result = engine.identify_failure_modes(
            _input(_obs(CORRODE, 0.90, area_mm2=50_000.0))
        )
        categories = [fm.category for fm in result]
        assert FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS not in categories

    def test_confidence_within_bounds(self, engine: EngineeringRulesEngine) -> None:
        result = engine.identify_failure_modes(
            _input(
                _obs(CORRODE, 0.88, area_mm2=30_000.0),
                _obs(REBAR, 0.82, area_mm2=6_000.0),
            )
        )
        fm = next(
            f
            for f in result
            if f.category == FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS
        )
        assert 0.70 <= fm.confidence <= 0.92

    def test_related_categories(self, engine: EngineeringRulesEngine) -> None:
        result = engine.identify_failure_modes(
            _input(
                _obs(CORRODE, 0.85, area_mm2=15_000.0),
                _obs(REBAR, 0.80),
            )
        )
        fm = next(
            f
            for f in result
            if f.category == FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS
        )
        assert CORRODE in fm.related_defect_categories
        assert REBAR in fm.related_defect_categories


# ---------------------------------------------------------------------------
# Rule: extensive spalling
# ---------------------------------------------------------------------------


class TestExtensiveSpalling:
    def test_fires_above_area_threshold(self, engine: EngineeringRulesEngine) -> None:
        result = engine.identify_failure_modes(
            _input(_obs(SPALL, 0.85, area_mm2=35_000.0))
        )
        categories = [fm.category for fm in result]
        assert FailureModeCategory.COMPRESSION_BUCKLING in categories

    def test_does_not_fire_below_area_threshold(
        self, engine: EngineeringRulesEngine
    ) -> None:
        result = engine.identify_failure_modes(
            _input(_obs(SPALL, 0.90, area_mm2=10_000.0))
        )
        categories = [fm.category for fm in result]
        assert FailureModeCategory.COMPRESSION_BUCKLING not in categories

    def test_fires_with_count_fallback(self, engine: EngineeringRulesEngine) -> None:
        """≥ 3 spalling observations with no area → conservative trigger."""
        result = engine.identify_failure_modes(
            _input(
                _obs(SPALL, 0.80),
                _obs(SPALL, 0.75),
                _obs(SPALL, 0.70),
            )
        )
        categories = [fm.category for fm in result]
        assert FailureModeCategory.COMPRESSION_BUCKLING in categories

    def test_does_not_fire_with_two_counts_no_area(
        self, engine: EngineeringRulesEngine
    ) -> None:
        engine.identify_failure_modes(
            _input(_obs(SPALL, 0.80), _obs(SPALL, 0.75))
        )
        # Two observations without area data should NOT fire (threshold is ≥3)
        # unless co-occurring with other rules; check spalling-specific rule only
        # by using a custom config with just that rule
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(r for r in DEFAULT_RULES if r.name == "extensive_spalling")
            )
        )
        result2 = solo_engine.identify_failure_modes(
            _input(_obs(SPALL, 0.80), _obs(SPALL, 0.75))
        )
        assert result2 == []

    def test_confidence_within_bounds(self, engine: EngineeringRulesEngine) -> None:
        engine.identify_failure_modes(
            _input(_obs(SPALL, 0.85, area_mm2=60_000.0))
        )
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(r for r in DEFAULT_RULES if r.name == "extensive_spalling")
            )
        )
        result2 = solo_engine.identify_failure_modes(
            _input(_obs(SPALL, 0.85, area_mm2=60_000.0))
        )
        fm = result2[0]
        assert 0.55 <= fm.confidence <= 0.85


# ---------------------------------------------------------------------------
# Rule: multiple major defects
# ---------------------------------------------------------------------------


class TestMultipleMajorDefects:
    def test_fires_with_three_significant_categories(
        self, engine: EngineeringRulesEngine
    ) -> None:
        result = engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.85, width_mm=0.5),
                _obs(SPALL, 0.80, area_mm2=15_000.0),
                _obs(CORRODE, 0.75, area_mm2=10_000.0),
            )
        )
        categories = [fm.category for fm in result]
        assert FailureModeCategory.UNKNOWN in categories

    def test_does_not_fire_with_two_significant_categories(
        self, engine: EngineeringRulesEngine
    ) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(r for r in DEFAULT_RULES if r.name == "multiple_major_defects")
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.85, width_mm=2.0),
                _obs(CORRODE, 0.80, area_mm2=20_000.0),
            )
        )
        assert result == []

    def test_pothole_and_surface_not_counted_as_significant(
        self, engine: EngineeringRulesEngine
    ) -> None:
        """POTHOLE + SURFACE_DAMAGE + CRACK = only 1 significant category → no UNKNOWN."""
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(r for r in DEFAULT_RULES if r.name == "multiple_major_defects")
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(POTHOLE, 0.90, area_mm2=50_000.0),
                _obs(SURFACE, 0.85, area_mm2=30_000.0),
                _obs(CRACK, 0.80, width_mm=1.0),
            )
        )
        assert result == []

    def test_fires_with_four_significant_categories(
        self, engine: EngineeringRulesEngine
    ) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(r for r in DEFAULT_RULES if r.name == "multiple_major_defects")
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.85),
                _obs(SPALL, 0.80, area_mm2=10_000.0),
                _obs(CORRODE, 0.78, area_mm2=8_000.0),
                _obs(REBAR, 0.90, area_mm2=3_000.0),
            )
        )
        assert len(result) == 1
        assert result[0].category == FailureModeCategory.UNKNOWN


# ---------------------------------------------------------------------------
# Rule: widespread delamination
# ---------------------------------------------------------------------------


class TestWidespreadDelamination:
    def test_fires_above_area_threshold(self, engine: EngineeringRulesEngine) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(r for r in DEFAULT_RULES if r.name == "widespread_delamination")
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(_obs(DELAM, 0.85, area_mm2=50_000.0))
        )
        assert len(result) == 1
        assert result[0].category == FailureModeCategory.DELAMINATION_INDUCED

    def test_does_not_fire_below_threshold(self, engine: EngineeringRulesEngine) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(r for r in DEFAULT_RULES if r.name == "widespread_delamination")
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(_obs(DELAM, 0.85, area_mm2=10_000.0))
        )
        assert result == []

    def test_fires_with_count_fallback(self, engine: EngineeringRulesEngine) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(r for r in DEFAULT_RULES if r.name == "widespread_delamination")
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(_obs(DELAM, 0.80), _obs(DELAM, 0.75), _obs(DELAM, 0.70))
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Rule: crack network instability
# ---------------------------------------------------------------------------


class TestCrackNetworkInstability:
    def test_fires_with_three_or_more_wide_cracks(
        self, engine: EngineeringRulesEngine
    ) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r for r in DEFAULT_RULES if r.name == "crack_network_instability"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.85, width_mm=1.0, max_width_mm=1.2),
                _obs(CRACK, 0.80, width_mm=0.8, max_width_mm=1.0),
                _obs(CRACK, 0.75, width_mm=0.6, max_width_mm=0.8),
            )
        )
        assert len(result) == 1
        assert result[0].category == FailureModeCategory.SHEAR

    def test_does_not_fire_with_two_cracks(self, engine: EngineeringRulesEngine) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r for r in DEFAULT_RULES if r.name == "crack_network_instability"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.90, width_mm=2.0, max_width_mm=2.0),
                _obs(CRACK, 0.85, width_mm=1.5, max_width_mm=1.5),
            )
        )
        assert result == []

    def test_does_not_fire_with_very_narrow_cracks(
        self, engine: EngineeringRulesEngine
    ) -> None:
        """Three cracks but max width < 0.5 mm → does not qualify."""
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r for r in DEFAULT_RULES if r.name == "crack_network_instability"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.90, width_mm=0.1, max_width_mm=0.2),
                _obs(CRACK, 0.85, width_mm=0.2, max_width_mm=0.3),
                _obs(CRACK, 0.80, width_mm=0.1, max_width_mm=0.4),
            )
        )
        assert result == []

    def test_fires_with_no_width_data_conservative(
        self, engine: EngineeringRulesEngine
    ) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r for r in DEFAULT_RULES if r.name == "crack_network_instability"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(_obs(CRACK, 0.80), _obs(CRACK, 0.75), _obs(CRACK, 0.70))
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Rule: significant material loss (spalling + corrosion)
# ---------------------------------------------------------------------------


class TestSignificantMaterialLoss:
    def test_fires_when_combined_area_above_threshold(
        self, engine: EngineeringRulesEngine
    ) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r for r in DEFAULT_RULES if r.name == "significant_material_loss"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(SPALL, 0.85, area_mm2=30_000.0),
                _obs(CORRODE, 0.80, area_mm2=25_000.0),
            )
        )
        assert len(result) == 1
        assert result[0].category == FailureModeCategory.COMPRESSION_BUCKLING

    def test_does_not_fire_when_combined_area_below_threshold(
        self, engine: EngineeringRulesEngine
    ) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r for r in DEFAULT_RULES if r.name == "significant_material_loss"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(SPALL, 0.85, area_mm2=10_000.0),
                _obs(CORRODE, 0.80, area_mm2=5_000.0),
            )
        )
        assert result == []

    def test_does_not_fire_with_only_spalling(
        self, engine: EngineeringRulesEngine
    ) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r for r in DEFAULT_RULES if r.name == "significant_material_loss"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(_obs(SPALL, 0.85, area_mm2=80_000.0))
        )
        assert result == []

    def test_fires_conservatively_when_one_area_missing(
        self, engine: EngineeringRulesEngine
    ) -> None:
        """One category has no calibrated area → conservative trigger."""
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r for r in DEFAULT_RULES if r.name == "significant_material_loss"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(SPALL, 0.85, area_mm2=30_000.0),
                _obs(CORRODE, 0.80),  # no area_mm2
            )
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Rule: corrosion + spalling + rebar trinity
# ---------------------------------------------------------------------------


class TestCorrosionSpallingRebarTrinity:
    def test_fires_when_all_three_present(self, engine: EngineeringRulesEngine) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r
                    for r in DEFAULT_RULES
                    if r.name == "corrosion_induced_spalling_rebar"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(CORRODE, 0.88, area_mm2=15_000.0),
                _obs(SPALL, 0.85, area_mm2=20_000.0),
                _obs(REBAR, 0.82, area_mm2=5_000.0),
            )
        )
        assert len(result) == 1
        assert result[0].category == FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS

    def test_does_not_fire_with_two_of_three(
        self, engine: EngineeringRulesEngine
    ) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r
                    for r in DEFAULT_RULES
                    if r.name == "corrosion_induced_spalling_rebar"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(CORRODE, 0.88, area_mm2=20_000.0),
                _obs(SPALL, 0.85, area_mm2=25_000.0),
            )
        )
        assert result == []

    def test_confidence_at_high_end(self, engine: EngineeringRulesEngine) -> None:
        """Trinity rule has high base confidence 0.75 — verify it's respected."""
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r
                    for r in DEFAULT_RULES
                    if r.name == "corrosion_induced_spalling_rebar"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(CORRODE, 0.95, area_mm2=40_000.0),
                _obs(SPALL, 0.95, area_mm2=30_000.0),
                _obs(REBAR, 0.95, area_mm2=10_000.0),
            )
        )
        assert result[0].confidence >= 0.75
        assert result[0].confidence <= 0.95

    def test_related_categories_all_three(self, engine: EngineeringRulesEngine) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r
                    for r in DEFAULT_RULES
                    if r.name == "corrosion_induced_spalling_rebar"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(CORRODE, 0.85, area_mm2=15_000.0),
                _obs(SPALL, 0.80, area_mm2=20_000.0),
                _obs(REBAR, 0.80, area_mm2=4_000.0),
            )
        )
        fm = result[0]
        assert CORRODE in fm.related_defect_categories
        assert SPALL in fm.related_defect_categories
        assert REBAR in fm.related_defect_categories


# ---------------------------------------------------------------------------
# Rule: delamination with spalling
# ---------------------------------------------------------------------------


class TestDelaminationWithSpalling:
    def test_fires_above_combined_area_threshold(
        self, engine: EngineeringRulesEngine
    ) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r for r in DEFAULT_RULES if r.name == "delamination_with_spalling"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(DELAM, 0.85, area_mm2=15_000.0),
                _obs(SPALL, 0.80, area_mm2=12_000.0),
            )
        )
        assert len(result) == 1
        assert result[0].category == FailureModeCategory.DELAMINATION_INDUCED

    def test_does_not_fire_below_threshold(self, engine: EngineeringRulesEngine) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r for r in DEFAULT_RULES if r.name == "delamination_with_spalling"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(
                _obs(DELAM, 0.85, area_mm2=5_000.0),
                _obs(SPALL, 0.80, area_mm2=8_000.0),
            )
        )
        assert result == []

    def test_does_not_fire_with_only_delamination(
        self, engine: EngineeringRulesEngine
    ) -> None:
        solo_engine = EngineeringRulesEngine(
            EngineeringRulesConfig(
                rules=tuple(
                    r for r in DEFAULT_RULES if r.name == "delamination_with_spalling"
                )
            )
        )
        result = solo_engine.identify_failure_modes(
            _input(_obs(DELAM, 0.85, area_mm2=60_000.0))
        )
        assert result == []


# ---------------------------------------------------------------------------
# Confidence bounds — all modes must be in [0, 1]
# ---------------------------------------------------------------------------


class TestConfidenceBounds:
    def test_all_confidence_values_in_unit_interval(
        self, engine: EngineeringRulesEngine
    ) -> None:
        """Stress test with extreme observation values."""
        result = engine.identify_failure_modes(
            _input(
                _obs(CRACK, 1.0, width_mm=100.0, max_width_mm=100.0),
                _obs(SPALL, 1.0, area_mm2=1_000_000.0),
                _obs(CORRODE, 1.0, area_mm2=1_000_000.0),
                _obs(REBAR, 1.0, area_mm2=500_000.0),
                _obs(DELAM, 1.0, area_mm2=500_000.0),
            )
        )
        for fm in result:
            assert 0.0 <= fm.confidence <= 1.0, (
                f"{fm.category}.confidence={fm.confidence} out of [0,1]"
            )

    def test_confidence_never_negative(self, engine: EngineeringRulesEngine) -> None:
        result = engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.01, width_mm=0.001, max_width_mm=0.001),
                _obs(REBAR, 0.01, area_mm2=0.1),
            )
        )
        for fm in result:
            assert fm.confidence >= 0.0


# ---------------------------------------------------------------------------
# Multiple rules firing simultaneously
# ---------------------------------------------------------------------------


class TestMultipleRulesFiring:
    def test_complex_scene_produces_multiple_modes(
        self, engine: EngineeringRulesEngine
    ) -> None:
        """
        A heavily deteriorated asset should trigger several rules at once.
        No single rule output should prevent another from firing.
        """
        result = engine.identify_failure_modes(
            _input(
                _obs(CRACK, 0.90, width_mm=3.0, max_width_mm=3.5),
                _obs(CRACK, 0.85, width_mm=2.0, max_width_mm=2.5),
                _obs(CRACK, 0.80, width_mm=1.5, max_width_mm=2.0),
                _obs(SPALL, 0.88, area_mm2=40_000.0),
                _obs(CORRODE, 0.85, area_mm2=35_000.0),
                _obs(REBAR, 0.82, area_mm2=8_000.0),
                _obs(DELAM, 0.78, area_mm2=45_000.0),
            )
        )
        # At minimum, several rules should have fired
        assert len(result) >= 4, f"Expected ≥4 failure modes, got {len(result)}"

    def test_result_is_list_of_structural_failure_modes(
        self, engine: EngineeringRulesEngine
    ) -> None:
        result = engine.identify_failure_modes(
            _input(
                _obs(CORRODE, 0.85, area_mm2=20_000.0),
                _obs(REBAR, 0.80, area_mm2=5_000.0),
            )
        )
        for item in result:
            assert isinstance(item, StructuralFailureMode)


# ---------------------------------------------------------------------------
# Custom configuration
# ---------------------------------------------------------------------------


class TestCustomConfig:
    def test_custom_empty_rules_returns_empty(self) -> None:
        engine = EngineeringRulesEngine(EngineeringRulesConfig(rules=()))
        result = engine.identify_failure_modes(
            _input(
                _obs(CORRODE, 0.90, area_mm2=50_000.0),
                _obs(REBAR, 0.85, area_mm2=10_000.0),
            )
        )
        assert result == []

    def test_custom_single_rule_only_that_rule_fires(self) -> None:
        corrosion_rebar_rule = next(
            r for r in DEFAULT_RULES if r.name == "corrosion_with_exposed_rebar"
        )
        engine = EngineeringRulesEngine(
            EngineeringRulesConfig(rules=(corrosion_rebar_rule,))
        )
        result = engine.identify_failure_modes(
            _input(
                _obs(CORRODE, 0.85, area_mm2=20_000.0),
                _obs(REBAR, 0.80, area_mm2=5_000.0),
                _obs(CRACK, 0.90, width_mm=3.0, max_width_mm=3.5),
            )
        )
        # Only the corrosion+rebar rule is active — all others are excluded
        assert all(
            fm.category == FailureModeCategory.CORROSION_INDUCED_SECTION_LOSS
            for fm in result
        )

    def test_custom_rule_can_be_injected(self) -> None:
        """Verify the extension point: a third-party rule added to config is evaluated."""

        def always_fires(
            cats: dict[DefectCategory, object],
        ) -> object:
            return StructuralFailureMode(
                category=FailureModeCategory.PUNCHING_SHEAR,
                description="Custom rule always fires.",
                confidence=0.99,
                related_defect_categories=[],
            )

        custom_rule = EngineeringRule(name="always_fires", evaluator=always_fires)  # type: ignore[arg-type]
        engine = EngineeringRulesEngine(
            EngineeringRulesConfig(rules=(custom_rule,))
        )
        result = engine.identify_failure_modes(
            _input(_obs(CRACK, 0.50))
        )
        assert len(result) == 1
        assert result[0].category == FailureModeCategory.PUNCHING_SHEAR


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_input_same_output(self, engine: EngineeringRulesEngine) -> None:
        assessment = _input(
            _obs(CRACK, 0.85, width_mm=2.0, max_width_mm=2.5),
            _obs(REBAR, 0.80, area_mm2=5_000.0),
            _obs(CORRODE, 0.78, area_mm2=15_000.0),
        )
        result_a = engine.identify_failure_modes(assessment)
        result_b = engine.identify_failure_modes(assessment)

        assert len(result_a) == len(result_b)
        for a, b in zip(result_a, result_b, strict=True):
            assert a.category == b.category
            assert a.confidence == b.confidence
            assert a.related_defect_categories == b.related_defect_categories
