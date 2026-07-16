"""
Pydantic v2 schemas for Asset API endpoints.

Three schema pattern:
- AssetCreate  — fields required to create a new asset
- AssetUpdate  — all fields optional (PATCH semantics)
- AssetResponse — full representation returned by the API
"""
from datetime import datetime

from pydantic import Field

from backend.app.models.asset import AssetStatus, AssetType
from backend.app.schemas.common import SHMBaseSchema


class AssetCreate(SHMBaseSchema):
    """Request body for POST /assets."""
    name: str = Field(
        ..., min_length=1, max_length=255,
        description="Unique human-readable name for this asset.",
        examples=["Main Street Bridge", "Tunnel A - Section 4"],
    )
    asset_type: AssetType = Field(
        default=AssetType.OTHER,
        description="Physical category of the structure.",
    )
    location: str | None = Field(
        default=None, max_length=512,
        description="Free-text location or GPS coordinates (lat, lon).",
        examples=["51.5074° N, 0.1278° W"],
    )
    description: str | None = Field(
        default=None,
        description="Optional detailed description of the asset.",
    )
    construction_year: int | None = Field(
        default=None, ge=1800, le=2100,
        description="Year the structure was built.",
    )
    material: str | None = Field(
        default=None, max_length=128,
        description="Primary structural material.",
        examples=["reinforced concrete", "prestressed concrete", "steel"],
    )
    design_life_years: float | None = Field(
        default=None, gt=0,
        description="Designed service life in years.",
        examples=[50.0, 100.0],
    )


class AssetUpdate(SHMBaseSchema):
    """Request body for PATCH /assets/{id} — all fields optional."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    asset_type: AssetType | None = None
    location: str | None = Field(default=None, max_length=512)
    description: str | None = None
    status: AssetStatus | None = Field(
        default=None,
        description="Update the operational status of the asset.",
    )
    construction_year: int | None = Field(default=None, ge=1800, le=2100)
    material: str | None = Field(default=None, max_length=128)
    design_life_years: float | None = Field(default=None, gt=0)


class AssetResponse(SHMBaseSchema):
    """Full asset representation returned by the API."""
    id: str
    name: str
    asset_type: AssetType
    location: str | None
    description: str | None
    status: AssetStatus
    construction_year: int | None
    material: str | None
    design_life_years: float | None
    latest_health_score: float | None = Field(
        description="Most recent health score (0–100). Null if never inspected."
    )
    created_at: datetime
    updated_at: datetime
