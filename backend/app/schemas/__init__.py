"""Pydantic v2 schemas package."""
from backend.app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from backend.app.schemas.common import ErrorResponse, MessageResponse, PaginatedResponse
from backend.app.schemas.inspection import InspectionCreate, InspectionResponse, InspectionUpdate

__all__ = [
    "AssetCreate", "AssetUpdate", "AssetResponse",
    "InspectionCreate", "InspectionUpdate", "InspectionResponse",
    "PaginatedResponse", "MessageResponse", "ErrorResponse",
]
