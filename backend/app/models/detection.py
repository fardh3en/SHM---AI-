"""
Detection ORM model.

A Detection stores one defect instance found within an inspection.
Each detection has a type, confidence score, bounding box, optional mask polygon,
and computed measurements (area, length, width, orientation).

Measurements are in pixel coordinates during Phase 2. Real-world unit conversion
(requiring camera calibration data) is planned for Phase 3.
"""
from __future__ import annotations

from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampedMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.app.models.inspection import Inspection


class DefectType(str, PyEnum):
    """
    Structural defect categories detected by the vision engine.
    These map to YOLO model class labels.
    """
    CRACK = "crack"
    SPALLING = "spalling"
    CORROSION = "corrosion"
    EXPOSED_REINFORCEMENT = "exposed_reinforcement"
    DELAMINATION = "delamination"
    POTHOLE = "pothole"
    SURFACE_DAMAGE = "surface_damage"
    UNKNOWN = "unknown"


class Detection(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    """
    Individual defect detection result.

    One Detection = one defect instance identified by the YOLO11 model.
    If sliced inference is used, the tile coordinates are stored so the
    detection can be projected back to the full-image coordinate space.
    """

    __tablename__ = "detections"

    # ── Foreign key ────────────────────────────────────────────────────────────
    inspection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inspections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Classification ────────────────────────────────────────────────────────
    defect_type: Mapped[DefectType] = mapped_column(
        Enum(DefectType, name="defect_type_enum"),
        nullable=False,
        default=DefectType.CRACK,
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False,
        doc="Model confidence score [0.0, 1.0]."
    )

    # ── Bounding box (normalised to [0, 1] relative to image dimensions) ──────
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x2: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y2: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Measurements (pixel-space — calibration required for real-world units) ─
    area_px: Mapped[float | None] = mapped_column(
        Float, nullable=True, doc="Defect area in pixels²."
    )
    length_px: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Crack skeleton length in pixels (from skeletonization algorithm)."
    )
    width_px: Mapped[float | None] = mapped_column(
        Float, nullable=True, doc="Average crack width in pixels."
    )
    orientation_deg: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Dominant crack orientation in degrees (0° = horizontal)."
    )

    # ── Sliced inference provenance ───────────────────────────────────────────
    tile_x: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        doc="X offset of the source tile in the full image (sliced inference)."
    )
    tile_y: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        doc="Y offset of the source tile in the full image (sliced inference)."
    )
    source_image: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # ── Segmentation mask ─────────────────────────────────────────────────────
    mask_polygon: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        doc=(
            "Segmentation mask stored as GeoJSON-style polygon: "
            "{'type': 'Polygon', 'coordinates': [[x, y], ...]}."
        ),
    )

    # ── Relationship ──────────────────────────────────────────────────────────
    inspection: Mapped[Inspection] = relationship(
        "Inspection", back_populates="detections"
    )

    def __repr__(self) -> str:
        return (
            f"<Detection id={self.id!r} type={self.defect_type.value} "
            f"conf={self.confidence:.2f}>"
        )
