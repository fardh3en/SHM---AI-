"""
Sample inference runner for YOLO11 concrete crack segmentation model.
"""
import json
from pathlib import Path
from vision.detectors.yolo import YOLO11Detector
from vision.pipeline.cv_pipeline import CVInferencePipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEIGHTS_PATH = PROJECT_ROOT / "weights" / "shm_ai_crack_seg_finetune_15e_best.pt"
SAMPLE_IMG = PROJECT_ROOT / "datasets" / "prepared_crack_seg_v1" / "images" / "test" / "1616.rf.c868709931a671796794fdbb95352c5a.jpg"


def main():
    detector = YOLO11Detector(model_path=WEIGHTS_PATH, device="cpu", default_conf=0.25)
    pipeline = CVInferencePipeline(detector=detector, slice_if_large=False)
    results = pipeline.run(SAMPLE_IMG)

    output = {
        "image": str(SAMPLE_IMG.name),
        "detector_model": detector.model_name,
        "task": detector.task,
        "supports_segmentation": detector.supports_segmentation,
        "defect_count": len(results),
        "detections": [
            {
                "defect_type": r.defect_type.value,
                "confidence": round(r.confidence, 4),
                "bbox": [round(r.bbox_x1, 4), round(r.bbox_y1, 4), round(r.bbox_x2, 4), round(r.bbox_y2, 4)],
                "image_width": r.image_width,
                "image_height": r.image_height,
                "model_name": r.model_name,
                "class_id": r.class_id,
                "measurements": {
                    "area_px": round(r.measurements.area_px, 2),
                    "length_px": round(r.measurements.length_px, 2) if r.measurements.length_px else None,
                    "width_px": round(r.measurements.width_px, 2) if r.measurements.width_px else None,
                    "max_width_px": round(r.measurements.max_width_px, 2) if r.measurements.max_width_px else None,
                    "orientation_deg": round(r.measurements.orientation_deg, 1) if r.measurements.orientation_deg else None,
                    "calibration_status": "uncalibrated_pixel_space",
                },
                "mask_polygon": {
                    "type": r.mask_polygon.get("type") if r.mask_polygon else None,
                    "ring_count": len(r.mask_polygon.get("coordinates", [])) if r.mask_polygon else 0,
                    "vertex_count": len(r.mask_polygon.get("coordinates", [[]])[0]) if r.mask_polygon else 0,
                    "sample_vertices": r.mask_polygon.get("coordinates", [[]])[0][:5] if r.mask_polygon else [],
                },
            }
            for r in results
        ],
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
