"""Repositories package — data access layer."""
from backend.app.repositories.asset_repository import AssetRepository
from backend.app.repositories.detection_repository import DetectionRepository
from backend.app.repositories.evidence_repository import EvidenceRepository
from backend.app.repositories.health_record_repository import HealthRecordRepository
from backend.app.repositories.inspection_repository import InspectionRepository

__all__ = [
    "AssetRepository",
    "DetectionRepository",
    "EvidenceRepository",
    "HealthRecordRepository",
    "InspectionRepository",
]
