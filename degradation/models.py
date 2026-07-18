"""
Phase 4 Material Degradation — Domain Vocabulary.

Pure data classes and enumerations.  No behaviour, no scoring logic,
no formulas.  Mirrors the style of intelligence/schemas.py.

Scope boundary
--------------
This module defines the shared vocabulary consumed by config.py,
schemas.py, and the two engine modules (carbonation.py, corrosion.py).
It does NOT:
  - Import from backend.app.models (ORM decoupling — an adapter layer is
    a later, separate task).
  - Contain any physics formulas or business logic.
  - Define output schemas (those live in degradation/schemas.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# ── Exposure classification (EN 206 / EN 1992-1-1) ───────────────────────────


class ExposureClass(StrEnum):
    """
    Carbonation-induced corrosion exposure classes per EN 206 Table 1 /
    EN 1992-1-1.

    XC1 – Dry or permanently wet (indoor, submerged)
    XC2 – Wet, rarely dry (foundations, water-retaining)
    XC3 – Moderate humidity (exterior sheltered, interior high humidity)
    XC4 – Cyclic wet and dry (exterior exposed to rain)

    These classes govern the carbonation coefficient used in the
    square-root-of-time depth model and the corrosion propagation rate.
    """

    XC1 = "XC1"
    XC2 = "XC2"
    XC3 = "XC3"
    XC4 = "XC4"


# ── Material properties ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class MaterialProperties:
    """
    Physical properties of the concrete structural member under assessment.

    Attributes:
        concrete_cover_mm: Nominal concrete cover to reinforcement in mm.
            Required for carbonation depassivation calculations.
        water_cement_ratio: w/c ratio of the concrete mix, if known.
            Used to adjust the carbonation coefficient when provided.
            Typical range: 0.35 – 0.65.
        compressive_strength_mpa: 28-day characteristic compressive strength
            (f_ck) in MPa, if known.  Recorded for context and future
            chloride-model extensions; not consumed by Phase 4 formulas
            directly.
    """

    concrete_cover_mm: float
    water_cement_ratio: float | None = None
    compressive_strength_mpa: float | None = None
