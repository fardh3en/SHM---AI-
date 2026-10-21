"""
Pydantic schemas for AssetEvidence API endpoints.
"""
from datetime import datetime
from pydantic import Field

from backend.app.models.asset_evidence import EvidenceClassification
from backend.app.schemas.common import SHMBaseSchema


class AssetEvidenceCreate(SHMBaseSchema):
    """Schema for registering a new visual evidence asset."""
    asset_id: str = Field(..., description="UUID of the parent asset.")
    filename: str = Field(..., min_length=1, max_length=255)
    file_path: str = Field(..., min_length=1, max_length=1024)
    thumbnail_path: str | None = Field(default=None, max_length=1024)
    caption: str = Field(..., min_length=1, max_length=512)
    component_description: str | None = Field(default=None)
    classification: EvidenceClassification = Field(
        default=EvidenceClassification.VERIFIED_STRUCTURE,
        description="Truthful provenance classification.",
    )
    source_url: str | None = Field(default=None, max_length=1024)
    creator: str | None = Field(default=None, max_length=255)
    license: str | None = Field(default=None, max_length=128)
    is_sample: bool = Field(default=True)


class AssetEvidenceResponse(SHMBaseSchema):
    """Complete representation of an AssetEvidence record."""
    id: str
    asset_id: str
    filename: str
    file_path: str
    thumbnail_path: str | None
    caption: str
    component_description: str | None
    classification: EvidenceClassification
    source_url: str | None
    creator: str | None
    license: str | None
    is_sample: bool
    created_at: datetime
    updated_at: datetime
