"""
Measurement service for extracting crack metrics (area, length, width, orientation).

Supports scaling from pixel space to real-world physical dimensions (mm).
"""
import cv2
import numpy as np

from vision.schemas import MeasurementResult


class MeasurementService:
    """
    Computes dimensions of structural defects.
    
    Supports pixel-space calculations and calibration to real-world millimeters.
    """

    def __init__(self, pixel_to_mm_ratio: float | None = None) -> None:
        """
        Args:
            pixel_to_mm_ratio: Physical size of one pixel in millimeters (mm/px).
                               Default is None (no physical scaling).
        """
        self.pixel_to_mm_ratio = pixel_to_mm_ratio

    def measure_defect(
        self,
        binary_mask: np.ndarray,
        skeleton_mask: np.ndarray | None = None,
    ) -> MeasurementResult:
        """
        Calculate metrics for a binary defect mask and optional skeleton centerline.

        Args:
            binary_mask: Binary mask of the defect [H, W], values 0 or 255.
            skeleton_mask: Optional 1-px wide skeleton [H, W], values 0 or 255.

        Returns:
            MeasurementResult Pydantic schema containing pixel and mm dimensions.
        """
        # Ensure standard binary uint8 format
        mask = (binary_mask > 127).astype(np.uint8) * 255
        
        # ── Area Calculation ──────────────────────────────────────────────────
        area_px = float(np.count_nonzero(mask))

        # Defaults if no skeleton is provided
        length_px = None
        width_px = None
        max_width_px = None
        orientation_deg = None

        if skeleton_mask is not None and np.any(skeleton_mask > 127):
            skel = (skeleton_mask > 127).astype(np.uint8) * 255
            
            # ── Length Calculation (precision step weighting) ────────────────
            length_px = self._calculate_skeleton_length(skel)

            # ── Width Calculation (L2 Distance Transform) ─────────────────────
            width_px, max_width_px = self._calculate_skeleton_widths(mask, skel)

            # ── Orientation (PCA on skeleton coordinates) ─────────────────────
            orientation_deg = self._calculate_orientation(skel)

        return MeasurementResult.create_calibrated(
            area_px=area_px,
            length_px=length_px,
            width_px=width_px,
            max_width_px=max_width_px,
            orientation_deg=orientation_deg,
            pixel_to_mm_ratio=self.pixel_to_mm_ratio,
        )

    def _calculate_skeleton_length(self, skel: np.ndarray) -> float:
        """
        Compute skeleton length by summing pixel step distances.
        Assigns 1.0 for orthogonal steps, 1.414 for diagonal steps.
        """
        # Find coordinates of all active pixels [y, x]
        y_indices, x_indices = np.where(skel > 0)
        coords = set(zip(x_indices, y_indices, strict=True))
        
        length = 0.0
        visited_edges = set()

        # 8-neighborhood offsets
        offsets = [
            (1, 0, 1.0),   # Right
            (0, 1, 1.0),   # Down
            (1, 1, 1.414), # Down-Right
            (-1, 1, 1.414) # Down-Left
        ]

        for cx, cy in coords:
            for dx, dy, weight in offsets:
                nx, ny = cx + dx, cy + dy
                if (nx, ny) in coords:
                    edge = frozenset({(cx, cy), (nx, ny)})
                    if edge not in visited_edges:
                        visited_edges.add(edge)
                        length += weight

        # If length is completely isolated/dot, fallback to single pixel count
        if length == 0.0:
            length = float(len(coords))

        return length

    def _calculate_skeleton_widths(
        self, mask: np.ndarray, skel: np.ndarray
    ) -> tuple[float, float]:
        """
        Evaluate average and maximum crack width using L2 Distance Transform
        along the skeleton centerline.
        """
        # Distance transform values represent radius to closest boundary.
        # cv2.DIST_L2 calculates Euclidean distance.
        dist_transform = cv2.distanceTransform(mask, cv2.DIST_L2, 5)

        # Retrieve distance values along the skeleton centerline
        skel_y, skel_x = np.where(skel > 0)
        radii = dist_transform[skel_y, skel_x]

        # Local width = 2 * radius
        widths = radii * 2.0

        if len(widths) == 0:
            return 0.0, 0.0

        avg_width = float(np.mean(widths))
        max_width = float(np.max(widths))

        return avg_width, max_width

    def _calculate_orientation(self, skel: np.ndarray) -> float:
        """
        Estimate dominant orientation using PCA on skeleton coordinates.
        Returns angle in degrees (-90 to 90), 0 being horizontal.
        """
        skel_y, skel_x = np.where(skel > 0)
        if len(skel_x) < 2:
            return 0.0

        # Stack coordinates as column vectors [X, Y]
        data = np.vstack([skel_x, skel_y]).T
        
        # Center the data
        mean = np.mean(data, axis=0)
        centered = data - mean

        # Compute Covariance Matrix
        cov = np.cov(centered, rowvar=False)
        
        # Calculate Eigenvalues and Eigenvectors
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        
        # Dominant direction is the eigenvector of the largest eigenvalue
        # (eigh returns them in ascending order, so index -1)
        dom_vector = eigenvectors[:, -1]

        # Calculate angle of dominant vector relative to horizontal axis
        angle_rad = np.arctan2(dom_vector[1], dom_vector[0])
        angle_deg = np.degrees(angle_rad)

        # Standardise range to [-90, 90]
        if angle_deg > 90:
            angle_deg -= 180
        elif angle_deg < -90:
            angle_deg += 180

        return float(angle_deg)
