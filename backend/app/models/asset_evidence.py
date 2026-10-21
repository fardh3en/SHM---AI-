"""
AssetEvidence ORM model.

Represents visual evidence files (photographs, drone captures, reference imagery)
associated with structural assets, maintaining complete provenance, attribution,
and licensing metadata.
"""
from __future__ import annotations

from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampedMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.app.models.asset import Asset


class EvidenceClassification(str, PyEnum):
    """
    Truthful classification of structural evidence media:
    - VERIFIED_STRUCTURE: Authenticated photograph of the exact named structure.
    - COMPARABLE_REFERENCE: Genuine photograph of a comparable structure with matching materials.
    - SYNTHETIC_DEMO: Synthetic demonstration image created for workflow demonstration.
    """
    VERIFIED_STRUCTURE = "verified_structure"
    COMPARABLE_REFERENCE = "comparable_reference"
    SYNTHETIC_DEMO = "synthetic_demo"


class AssetEvidence(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    """
    Structural asset visual evidence entity.
    """

    __tablename__ = "asset_evidence"

    # ── Asset relation ─────────────────────────────────────────────────────────
    asset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="UUID of the associated structural asset.",
    )

    # ── File paths ─────────────────────────────────────────────────────────────
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Base filename of the image on disk.",
    )
    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        doc="Publicly accessible URL path, e.g. /uploads/evidence/filename.jpg",
    )
    thumbnail_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        doc="Optional path to a smaller thumbnail resolution.",
    )

    # ── Semantic & structural context ──────────────────────────────────────────
    caption: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        doc="Concise descriptive title of the photograph.",
    )
    component_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed engineering description of structural components depicted.",
    )

    # ── Provenance & licensing ─────────────────────────────────────────────────
    classification: Mapped[EvidenceClassification] = mapped_column(
        Enum(EvidenceClassification, name="evidence_classification_enum"),
        nullable=False,
        default=EvidenceClassification.VERIFIED_STRUCTURE,
        doc="Truthful provenance classification.",
    )
    source_url: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        doc="Authoritative origin URL (e.g. Wikimedia Commons or HAER page).",
    )
    creator: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Photographer or author attribution.",
    )
    license: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        doc="License terms (e.g. Public Domain, CC BY-SA 4.0, CC BY 2.0).",
    )
    is_sample: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Flag indicating development/demo sample data vs user upload.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    asset: Mapped[Asset] = relationship("Asset", back_populates="evidence")
