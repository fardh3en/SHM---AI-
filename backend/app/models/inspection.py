"""
Inspection ORM model.

An Inspection is a single data-collection event for an asset.
It groups one or more images/video frames analysed in a single session.
Results (detections, health records) are linked to this entity.
"""
from __future__ import annotations

from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampedMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.app.models.asset import Asset
    from backend.app.models.detection import Detection
    from backend.app.models.health_record import HealthRecord


class InspectionStatus(str, PyEnum):
    """Processing lifecycle state of an inspection."""
    PENDING = "pending"          # created, not yet processed
    PROCESSING = "processing"    # vision engine is running
    COMPLETED = "completed"      # all results stored
    FAILED = "failed"            # unrecoverable error during processing


class InspectionSource(str, PyEnum):
    """Origin of the input media for this inspection."""
    IMAGE = "image"
    VIDEO = "video"
    DRONE = "drone"
    CAMERA_FEED = "camera_feed"
    MANUAL = "manual"            # human-annotated, no AI processing


class Inspection(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    """
    Inspection event entity.

    Represents a single inspection session — may cover one or many images/frames
    captured at a specific point in time. Links to detections and health records.
    """

    __tablename__ = "inspections"

    # ── Foreign key ────────────────────────────────────────────────────────────
    asset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Status & source ───────────────────────────────────────────────────────
    status: Mapped[InspectionStatus] = mapped_column(
        Enum(InspectionStatus, name="inspection_status_enum"),
        nullable=False,
        default=InspectionStatus.PENDING,
    )
    source: Mapped[InspectionSource] = mapped_column(
        Enum(InspectionSource, name="inspection_source_enum"),
        nullable=False,
        default=InspectionSource.IMAGE,
    )

    # ── Input media ───────────────────────────────────────────────────────────
    input_path: Mapped[str | None] = mapped_column(
        String(1024), nullable=True,
        doc="File path or URL of the input image/video."
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Results summary (populated by Phase 2 vision engine) ──────────────────
    defect_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    health_score: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Composite health score (0–100) computed by the intelligence engine."
    )
    processing_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    asset: Mapped[Asset] = relationship("Asset", back_populates="inspections")
    detections: Mapped[list[Detection]] = relationship(
        "Detection",
        back_populates="inspection",
        cascade="all, delete-orphan",
        lazy="select",
    )
    health_records: Mapped[list[HealthRecord]] = relationship(
        "HealthRecord",
        back_populates="inspection",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Inspection id={self.id!r} asset={self.asset_id!r} "
            f"status={self.status.value}>"
        )
