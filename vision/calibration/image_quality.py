"""
Image quality and measurement suitability analyzer.
Evaluates focus blur, exposure balance, resolution limits, and perspective.
"""
from pathlib import Path
import cv2
import numpy as np

from vision.calibration.schemas import ImageQualityAssessment, ImageSuitabilityStatus


class ImageQualityAnalyzer:
    """
    Evaluates optical inspection imagery for geometric measurement suitability.
    Provides human-readable diagnostic reasons rather than uncalibrated probabilities.
    """

    @classmethod
    def analyze(
        cls,
        image: np.ndarray,
        image_id: str | None = None,
        image_format: str | None = None,
    ) -> ImageQualityAssessment:
        """
        Analyze an RGB image numpy array [H, W, 3] or grayscale [H, W].
        """
        if len(image.shape) == 3:
            h, w = image.shape[:2]
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            h, w = image.shape[:2]
            gray = image

        reasons: list[str] = []

        # ── 1. Resolution Check ───────────────────────────────────────────────
        min_dim = min(h, w)
        if min_dim < 480:
            resolution_status = "low"
            reasons.append(
                f"Low image resolution ({w}x{h} px). Hairline cracks below ~2 pixels cannot be resolved reliably."
            )
        elif min_dim >= 1080:
            resolution_status = "high"
        else:
            resolution_status = "adequate"

        # ── 2. Blur / Focus Evaluation (Laplacian variance) ───────────────────
        # Laplacian operator computes second derivative; high variance indicates sharp edges.
        try:
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            blur_score = float(np.var(laplacian))
        except Exception:
            blur_score = 0.0

        if blur_score < 40.0:
            reasons.append(
                f"Severe optical or motion blur detected (focus score: {blur_score:.1f} < 40). "
                "Crack perimeter boundaries and skeleton endpoints may be imprecise."
            )
        elif blur_score < 100.0:
            reasons.append(
                f"Mild optical softening (focus score: {blur_score:.1f}). Centerline measurements are indicative."
            )

        # ── 3. Exposure Balance ───────────────────────────────────────────────
        mean_brightness = float(np.mean(gray))
        if mean_brightness < 40.0:
            exposure_status = "underexposed"
            reasons.append(
                f"Scene underexposure detected (mean luminance {mean_brightness:.1f}/255). "
                "Shadows may obscure crack extremities."
            )
        elif mean_brightness > 220.0:
            exposure_status = "overexposed"
            reasons.append(
                f"Scene overexposure detected (mean luminance {mean_brightness:.1f}/255). "
                "High specular reflection may wash out fine crack edges."
            )
        else:
            exposure_status = "normal"

        # ── 4. Perspective Assessment ─────────────────────────────────────────
        aspect_ratio = max(w, h) / max(min(w, h), 1)
        if aspect_ratio > 3.0:
            perspective_limitation = "oblique"
            reasons.append(
                f"High aspect ratio ({aspect_ratio:.1f}:1) suggests oblique camera viewing angle. "
                "Perspective foreshortening may cause non-uniform scale across the frame."
            )
        else:
            perspective_limitation = "planar"

        # ── 5. Overall Suitability ────────────────────────────────────────────
        if blur_score < 40.0 or min_dim < 320 or mean_brightness < 25.0 or mean_brightness > 235.0:
            suitability = ImageSuitabilityStatus.UNSUITABLE
        elif len(reasons) > 0:
            suitability = ImageSuitabilityStatus.MARGINAL
        else:
            suitability = ImageSuitabilityStatus.SUITABLE

        return ImageQualityAssessment(
            width_px=w,
            height_px=h,
            format=image_format,
            image_id=image_id,
            suitability_status=suitability,
            blur_score=round(blur_score, 1),
            exposure_status=exposure_status,
            resolution_status=resolution_status,
            perspective_limitation=perspective_limitation,
            unsuitable_reasons=reasons,
        )
