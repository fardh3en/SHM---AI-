"""
Binary mask to GeoJSON-style polygon conversion.

Detection records store segmentation masks as lightweight polygon coordinate
lists (rather than full raster masks) to keep database rows small. This module
converts a binary mask into that storage format using contour extraction.
"""
from typing import Any

import cv2
import numpy as np


class MaskPolygonConverter:
    """
    Converts binary instance masks into GeoJSON-style polygon dictionaries.
    """

    @staticmethod
    def mask_to_polygon(
        mask: np.ndarray,
        simplify_tolerance: float = 1.5,
    ) -> dict[str, Any] | None:
        """
        Extract the outer contour of a binary mask and return it as a polygon.

        Args:
            mask: Binary mask [H, W] with values in {0, 1} or {0, 255}.
            simplify_tolerance: Douglas-Peucker approximation tolerance in pixels.
                Higher values produce fewer points (smaller storage, coarser shape).

        Returns:
            GeoJSON-style dict: {'type': 'Polygon', 'coordinates': [[x, y], ...]},
            or None if the mask contains no foreground pixels / no valid contour
            could be extracted.
        """
        binary = (mask > 0).astype(np.uint8) * 255

        if not np.any(binary):
            return None

        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return None

        # Use the largest contour by area (a mask should generally be one
        # connected component after fusion, but guard against noise/fragments).
        largest = max(contours, key=cv2.contourArea)

        if cv2.contourArea(largest) <= 0:
            return None

        # Simplify to reduce point count while preserving overall shape.
        simplified = cv2.approxPolyDP(largest, simplify_tolerance, closed=True)

        # Need at least 3 points to form a valid polygon.
        if len(simplified) < 3:
            return None

        coordinates = [[float(pt[0][0]), float(pt[0][1])] for pt in simplified]

        # Close the ring per GeoJSON convention (first point == last point).
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])

        return {"type": "Polygon", "coordinates": [coordinates]}
