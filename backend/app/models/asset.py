"""
Asset ORM model.

An Asset represents a monitored civil infrastructure structure such as a
bridge, building, tunnel, or road. It is the top-level entity that groups
all inspections, health records, and degradation predictions.
"""
from __future__ import annotations

from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampedMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.app.models.degradation_record import DegradationRecord
    from backend.app.models.inspection import Inspection


class AssetType(str, PyEnum):
    """Physical category of the monitored structure."""
    BRIDGE = "bridge"
    BUILDING = "building"
    TUNNEL = "tunnel"
    ROAD = "road"
    DAM = "dam"
    PIPELINE = "pipeline"
    OTHER = "other"


class AssetStatus(str, PyEnum):
    """Operational status of the asset."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNDER_MAINTENANCE = "under_maintenance"
    DECOMMISSIONED = "decommissioned"


class Asset(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    """
    Structural asset entity.

    Represents a real-world civil infrastructure object being monitored
    for health, damage, and material degradation.
    """

    __tablename__ = "assets"

    # ── Core identity ──────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        doc="Human-readable display name for the asset."
    )
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="asset_type_enum"),
        nullable=False,
        default=AssetType.OTHER,
    )
    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus, name="asset_status_enum"),
        nullable=False,
        default=AssetStatus.ACTIVE,
    )
    location: Mapped[str | None] = mapped_column(
        String(512), nullable=True,
        doc="Free-text location or GPS coordinates."
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Physical / engineering metadata ───────────────────────────────────────
    construction_year: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        doc="Year the structure was originally constructed."
    )
    material: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        doc="Primary structural material (e.g., 'reinforced concrete', 'steel')."
    )
    design_life_years: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Designed service life in years from construction year."
    )

    # ── Denormalised health (fast dashboard queries) ───────────────────────────
    latest_health_score: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Most recent health score (0–100). Updated after each inspection."
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    inspections: Mapped[list[Inspection]] = relationship(
        "Inspection",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="Inspection.created_at.desc()",
    )
    degradation_records: Mapped[list[DegradationRecord]] = relationship(
        "DegradationRecord",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Asset id={self.id!r} name={self.name!r} type={self.asset_type.value}>"
