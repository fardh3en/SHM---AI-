"""
Health scoring components.

Concrete IHealthScorer implementation lives here. ISeverityClassifier
implementations are a later milestone.
"""
from intelligence.scoring.health_scorer import (
    DEFAULT_SCORING_RULES,
    DefectScoringRule,
    HealthScorer,
    HealthScorerConfig,
)

__all__ = [
    "HealthScorer",
    "HealthScorerConfig",
    "DefectScoringRule",
    "DEFAULT_SCORING_RULES",
]

