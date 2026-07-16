"""ORM models package. Import all models here to ensure they register with Base."""
from backend.app.models.asset import Asset
from backend.app.models.degradation_record import DegradationRecord
from backend.app.models.detection import Detection
from backend.app.models.health_record import HealthRecord
from backend.app.models.inspection import Inspection

__all__ = [
    "Asset",
    "Inspection",
    "Detection",
    "HealthRecord",
    "DegradationRecord",
]
