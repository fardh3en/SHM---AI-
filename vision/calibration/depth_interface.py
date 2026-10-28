"""
Subsurface Crack Depth Measurement Interface & Ingestion Service.

Governs the explicit distinction between 2D optical surface observations and
subsurface depth penetration. Optical imagery CANNOT determine crack depth.
Sensor-based measurements (UPV, Impact-Echo) can be attached via this interface.
"""
from abc import ABC, abstractmethod
from typing import Any

from vision.calibration.schemas import CrackDepthRecord, DepthStatus


class IDepthMeasurementService(ABC):
    """Abstract interface for crack depth assessment and sensor ingestion."""

    @abstractmethod
    def get_default_optical_depth(self) -> CrackDepthRecord:
        """Return the transparent default record for 2D optical photography."""
        pass

    @abstractmethod
    def record_sensor_depth(
        self,
        depth_mm: float,
        method: str,
        uncertainty_mm: float | None = None,
        provenance: str | None = None,
    ) -> CrackDepthRecord:
        """Create a validated sensor-derived depth record."""
        pass


class DepthMeasurementService(IDepthMeasurementService):
    """
    Standard implementation of crack depth management.
    Strictly forbids guessing subsurface depth from surface crack opening width.
    """

    def get_default_optical_depth(self) -> CrackDepthRecord:
        """
        Produces the honest unmeasured record for 2D surface imagery.
        """
        return CrackDepthRecord(
            depth_status=DepthStatus.NOT_MEASURED,
            depth_mm=None,
            uncertainty_mm=None,
            method=None,
            provenance="2D Optical Surface Imagery",
            notes=(
                "Subsurface crack depth cannot be measured from 2D optical surface photography. "
                "Non-destructive testing (such as ultrasonic pulse velocity, impact-echo, or core drilling) "
                "is required to quantify internal structural penetration."
            ),
        )

    def record_sensor_depth(
        self,
        depth_mm: float,
        method: str,
        uncertainty_mm: float | None = None,
        provenance: str | None = None,
    ) -> CrackDepthRecord:
        """
        Stores validated sensor-derived depth measurements.
        """
        if depth_mm < 0:
            raise ValueError(f"Crack depth cannot be negative: {depth_mm} mm")

        return CrackDepthRecord(
            depth_status=DepthStatus.SENSOR_MEASURED,
            depth_mm=round(depth_mm, 2),
            uncertainty_mm=round(uncertainty_mm, 2) if uncertainty_mm is not None else None,
            method=method,
            provenance=provenance or "Non-Destructive Sensor Telemetry",
            notes=f"Subsurface crack depth quantified via {method} sensor testing.",
        )
