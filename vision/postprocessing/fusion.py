"""
Instance mask and bounding box fusion services.
"""
import numpy as np


class MaskFusionService:
    """
    Fuses multiple overlapping instance masks into aggregated binary shapes.
    
    Uses logical OR operations to combine detection segments.
    """

    @staticmethod
    def fuse_masks(masks: list[np.ndarray], canvas_shape: tuple[int, int]) -> np.ndarray:
        """
        Merge a list of binary masks into a single combined mask.

        Args:
            masks: List of binary numpy arrays [H, W] with values in {0, 1} or {0, 255}.
            canvas_shape: Tuple representing (height, width) of the target canvas.

        Returns:
            A single unified uint8 binary mask [H, W] with values in {0, 255}.
        """
        if not masks:
            return np.zeros(canvas_shape, dtype=np.uint8)

        # Start with a false boolean mask matching the target canvas shape
        combined = np.zeros(canvas_shape, dtype=bool)

        for mask in masks:
            # Standardise mask to boolean array
            bool_mask = mask.astype(bool)
            
            # Align mask shape if it differs slightly from canvas
            if bool_mask.shape != canvas_shape:
                h_c, w_c = canvas_shape
                h_m, w_m = bool_mask.shape
                
                # Create compatible container and copy
                adapted = np.zeros(canvas_shape, dtype=bool)
                y_limit = min(h_c, h_m)
                x_limit = min(w_c, w_m)
                adapted[0:y_limit, 0:x_limit] = bool_mask[0:y_limit, 0:x_limit]
                bool_mask = adapted

            # Perform logical OR fusion (preserving legacy WhatTheCrack OR approach)
            combined = np.logical_or(combined, bool_mask)

        # Convert back to standard 0 or 255 uint8 format
        return (combined * 255).astype(np.uint8)
