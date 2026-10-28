"""
Pydantic v2 schemas for Reports API endpoints.
"""
from datetime import datetime
from pydantic import Field
from backend.app.schemas.common import SHMBaseSchema


class ReportGenerateRequest(SHMBaseSchema):
    """Payload to generate an engineering report."""
    asset_id: str = Field(..., description="UUID of the asset to report on.")
    inspection_id: str = Field(..., description="UUID of the completed inspection.")
    format: str = Field(default="html", description="Report format: 'html' or 'pdf'.")


class ReportSummary(SHMBaseSchema):
    """Summary of a persisted engineering report on disk."""
    filename: str
    file_path: str
    asset_id: str | None = None
    inspection_id: str | None = None
    created_at: datetime
    size_bytes: int
    format: str


class ReportGenerateResponse(SHMBaseSchema):
    """Result of generating an engineering report."""
    report_id: str
    filename: str
    format: str
    created_at: datetime
    asset_id: str
    asset_name: str
    inspection_id: str
    health_score: float | None
    recommended_action: str
    cost_estimate_low: float
    cost_estimate_high: float
    currency: str
    html_content: str
    pdf_available: bool = False
    pdf_filename: str | None = None
    notes: str | None = None
