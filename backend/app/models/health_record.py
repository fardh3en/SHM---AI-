"""
HealthRecord ORM model.

Stores the output of the Structural Health Intelligence engine (Phase 3).
Generated after each inspection and linked to that inspection.
"""
from __future__ import annotations

from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampedMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.app.models.inspection import Inspection


class RiskLevel(str, PyEnum):
    """
    Discrete risk classification derived from the health score.
    Maps to recommended action urgency in Phase 5.
    """
    LOW = "low"          # Score 75–100 — monitor
    MEDIUM = "medium"    # Score 50–74  — schedule inspection
    HIGH = "high"        # Score 25–49  — repair within 6 months
    CRITICAL = "critical"  # Score 0–24  — immediate action


class HealthRecord(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    """
    Structural health assessment for a single inspection.

    Produced by the intelligence engine in Phase 3. Stores the aggregated
    health score, risk classification, and detailed severity breakdown.
    """

    __tablename__ = "health_records"

    # ── Foreign key ────────────────────────────────────────────────────────────
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inspections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Core assessment ───────────────────────────────────────────────────────
    health_score: Mapped[float] = mapped_column(
        Float, nullable=False,
        doc="Composite structural health score. Range: 0 (critical) – 100 (pristine)."
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level_enum"),
        nullable=False,
        default=RiskLevel.LOW,
    )

    # ── Detailed breakdown (flexible JSON for evolving intelligence engine) ────
    severity_details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        doc="Per-defect-type severity scores as key-value dict."
    )
    failure_modes: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        doc="Identified structural failure modes (e.g., flexural, shear, compression)."
    )
    inspection_priority: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        doc="Recommended next inspection priority: 'immediate' | 'urgent' | 'routine' | 'monitor'."
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="Engineering notes or analyst comments."
    )

    # ── Relationship ──────────────────────────────────────────────────────────
    inspection: Mapped[Inspection] = relationship(
        "Inspection", back_populates="health_records"
    )

    def __repr__(self) -> str:
        return (
            f"<HealthRecord id={self.id!r} score={self.health_score:.1f} "
            f"risk={self.risk_level.value}>"
        )
