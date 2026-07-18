"""
Phase 4 Material Degradation Engine.

Deterministic, physics-based material degradation models for reinforced
concrete structures.

Public surface
--------------
  CarbonationModel       — carbonation depth prediction (degradation/carbonation.py)
  CorrosionModel         — corrosion propagation prediction (degradation/corrosion.py)
  ServiceLifeEstimator   — orchestrator (degradation/service_life.py)

Schemas and configuration are in degradation/schemas.py, degradation/models.py,
and degradation/config.py respectively.
"""
from degradation.carbonation import CarbonationModel, CarbonationModelConfig
from degradation.corrosion import CorrosionModel, CorrosionModelConfig
from degradation.models import ExposureClass, MaterialProperties
from degradation.schemas import MaintenanceDecision
from degradation.service_life import ServiceLifeEstimator, ServiceLifeEstimatorConfig

__all__ = [
    "CarbonationModel",
    "CarbonationModelConfig",
    "CorrosionModel",
    "CorrosionModelConfig",
    "ExposureClass",
    "MaterialProperties",
    "MaintenanceDecision",
    "ServiceLifeEstimator",
    "ServiceLifeEstimatorConfig",
]
