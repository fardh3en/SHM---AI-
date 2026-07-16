"""Repositories package — data access layer."""
from backend.app.repositories.asset_repository import AssetRepository
from backend.app.repositories.inspection_repository import InspectionRepository

__all__ = ["AssetRepository", "InspectionRepository"]
