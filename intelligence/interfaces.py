"""
Abstract interfaces for the Structural Health Intelligence engine.

Each interface has a single, narrow responsibility so concrete
implementations can be developed, tested, and swapped independently
(e.g. a rule-based ISeverityClassifier today, a learned model later).

No concrete logic lives here — implementations are later Phase 3
milestones, built once this foundation is approved.
"""
from abc import ABC, abstractmethod

from intelligence.schemas import (
    DefectSeverityBreakdown,
    HealthAssessmentInput,
    RiskLevel,
    StructuralFailureMode,
)


class IHealthScorer(ABC):
    """
    Computes a single composite health score for an asset from its
    defect observations.
    """

    @abstractmethod
    def calculate_score(self, assessment_input: HealthAssessmentInput) -> float:
        """
        Args:
            assessment_input: Aggregated defect observations and asset context.

        Returns:
            Composite health score in the range 0 (critical) - 100 (pristine).
        """
        ...


class ISeverityClassifier(ABC):
    """
    Groups and classifies defect observations by category and severity.
    """

    @abstractmethod
    def classify(
        self, assessment_input: HealthAssessmentInput
    ) -> list[DefectSeverityBreakdown]:
        """
        Args:
            assessment_input: Aggregated defect observations and asset context.

        Returns:
            One DefectSeverityBreakdown per distinct defect category present
            in the input observations.
        """
        ...


class IEngineeringRulesEngine(ABC):
    """
    Applies engineering domain rules to identify likely structural failure
    modes from observed defect patterns.
    """

    @abstractmethod
    def identify_failure_modes(
        self, assessment_input: HealthAssessmentInput
    ) -> list[StructuralFailureMode]:
        """
        Args:
            assessment_input: Aggregated defect observations and asset context.

        Returns:
            Identified failure modes, which may be empty if no defect
            pattern matches a known rule.
        """
        ...


class IRiskEngine(ABC):
    """
    Maps a composite health score to a discrete asset risk classification.
    """

    @abstractmethod
    def determine_risk_level(self, health_score: float) -> RiskLevel:
        """
        Args:
            health_score: Composite health score in the range 0-100, as
                produced by an IHealthScorer implementation.

        Returns:
            The corresponding discrete RiskLevel.
        """
        ...
