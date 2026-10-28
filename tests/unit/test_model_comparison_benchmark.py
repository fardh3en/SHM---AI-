"""
Unit tests for YOLO11 vs YOLO26 evaluation benchmark script.
"""
from pathlib import Path
import numpy as np
import pytest

from scripts.evaluate_yolo11_vs_yolo26 import (
    check_ground_truth_label,
    compute_benchmark_summary,
    compute_latency_statistics,
    compute_mask_iou_dice,
    detect_anomalies,
    generate_markdown_report,
    measure_mask_morphology,
    rasterize_yolo_polygons,
    save_results_csv,
    verify_checkpoints,
)


class TestPolygonRasterizationAndLabelVerification:
    def test_rasterize_valid_polygons(self, tmp_path: Path):
        label_file = tmp_path / "sample.txt"
        label_content = (
            "0 0.1 0.1 0.3 0.1 0.3 0.3 0.1 0.3\n"
            "0 0.6 0.6 0.8 0.6 0.7 0.8\n"
        )
        label_file.write_text(label_content, encoding="utf-8")

        mask, count = rasterize_yolo_polygons(label_file, img_width=100, img_height=100)
        assert mask.shape == (100, 100)
        assert mask.dtype == np.uint8
        assert count == 2
        active_px = np.count_nonzero(mask)
        assert active_px > 0
        assert mask[20, 20] == 1
        assert mask[0, 0] == 0

    def test_check_ground_truth_label_states(self, tmp_path: Path):
        # 1. Missing file -> MISSING_LABEL
        missing_file = tmp_path / "non_existent.txt"
        mask_m, count_m, status_m = check_ground_truth_label(missing_file, 50, 50)
        assert status_m == "MISSING_LABEL"
        assert count_m == 0
        assert np.count_nonzero(mask_m) == 0

        # 2. Empty file -> VERIFIED_NEGATIVE
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("   \n", encoding="utf-8")
        mask_e, count_e, status_e = check_ground_truth_label(empty_file, 50, 50)
        assert status_e == "VERIFIED_NEGATIVE"
        assert count_e == 0
        assert np.count_nonzero(mask_e) == 0

        # 3. Polygon file -> POSITIVE
        poly_file = tmp_path / "crack.txt"
        poly_file.write_text("0 0.2 0.2 0.4 0.2 0.4 0.4 0.2 0.4\n", encoding="utf-8")
        mask_p, count_p, status_p = check_ground_truth_label(poly_file, 50, 50)
        assert status_p == "POSITIVE"
        assert count_p == 1
        assert np.count_nonzero(mask_p) > 0

    def test_rasterize_malformed_lines_graceful(self, tmp_path: Path):
        bad_file = tmp_path / "bad.txt"
        bad_file.write_text("0 0.1 0.2\ncorrupted line\n0 0.1 0.1 0.5 0.1 0.5 0.5 0.1 0.5\n", encoding="utf-8")
        mask, count = rasterize_yolo_polygons(bad_file, 100, 100)
        assert count == 1
        assert np.count_nonzero(mask) > 0


class TestIoUAndDiceMetrics:
    def test_both_empty_masks_explicit_handling(self):
        m1 = np.zeros((50, 50), dtype=np.uint8)
        m2 = np.zeros((50, 50), dtype=np.uint8)
        # Default empty handling returns (None, None) because foreground crack IoU is undefined
        iou, dice = compute_mask_iou_dice(m1, m2)
        assert iou is None
        assert dice is None

        # When explicitly requested with custom empty_value
        iou_val, dice_val = compute_mask_iou_dice(m1, m2, empty_value=1.0)
        assert iou_val == 1.0
        assert dice_val == 1.0

    def test_mask_dimension_mismatch_raises_error(self):
        m1 = np.zeros((50, 50), dtype=np.uint8)
        m2 = np.zeros((60, 60), dtype=np.uint8)
        with pytest.raises(ValueError, match="Shape mismatch"):
            compute_mask_iou_dice(m1, m2)

    def test_identical_positive_masks(self):
        m = np.zeros((50, 50), dtype=np.uint8)
        m[10:30, 10:30] = 1
        iou, dice = compute_mask_iou_dice(m, m)
        assert iou == 1.0
        assert dice == 1.0

    def test_disjoint_masks(self):
        m1 = np.zeros((50, 50), dtype=np.uint8)
        m2 = np.zeros((50, 50), dtype=np.uint8)
        m1[0:10, 0:10] = 1
        m2[20:30, 20:30] = 1
        iou, dice = compute_mask_iou_dice(m1, m2)
        assert iou == 0.0
        assert dice == 0.0

    def test_partial_overlap(self):
        m1 = np.zeros((50, 50), dtype=np.uint8)
        m2 = np.zeros((50, 50), dtype=np.uint8)
        # m1 has 100 pixels, m2 has 100 pixels, 50 pixels overlap
        m1[10:20, 10:20] = 1
        m2[10:20, 15:25] = 1
        iou, dice = compute_mask_iou_dice(m1, m2)
        assert iou == pytest.approx(0.3333, abs=1e-3)
        assert dice == pytest.approx(0.5000, abs=1e-3)

    def test_false_positive_and_false_negative(self):
        empty = np.zeros((50, 50), dtype=np.uint8)
        non_empty = np.zeros((50, 50), dtype=np.uint8)
        non_empty[5:15, 5:15] = 1

        # False positive: GT is empty, pred is non-empty
        iou_fp, dice_fp = compute_mask_iou_dice(pred_mask=non_empty, gt_mask=empty)
        assert iou_fp == 0.0
        assert dice_fp == 0.0

        # False negative: GT is non-empty, pred is empty
        iou_fn, dice_fn = compute_mask_iou_dice(pred_mask=empty, gt_mask=non_empty)
        assert iou_fn == 0.0
        assert dice_fn == 0.0


class TestMorphologicalMeasurements:
    def test_measure_crack_geometry(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        # Vertical crack line: height=40, width=3
        mask[20:60, 48:51] = 255
        m = measure_mask_morphology(mask)

        assert m["area_px"] == 120.0
        assert m["length_px"] > 30.0
        assert 2.5 <= m["width_px"] <= 4.5
        assert m["max_width_px"] >= 3.0

    def test_measure_empty_or_subpixel_mask(self):
        mask = np.zeros((50, 50), dtype=np.uint8)
        m = measure_mask_morphology(mask)
        assert m["area_px"] == 0.0
        assert m["length_px"] == 0.0
        assert m["width_px"] == 0.0
        assert m["max_width_px"] == 0.0

        mask[10, 10] = 1  # 1 pixel (< 3 px threshold)
        m_sub = measure_mask_morphology(mask)
        assert m_sub["area_px"] == 1.0
        assert m_sub["length_px"] == 0.0


class TestAnomalyDetection:
    def test_missed_crack_heuristic(self):
        anomalies = detect_anomalies(
            det_count=0,
            gt_polygon_count=1,
            gt_area_px=500.0,
            det_measurements=[],
            iou=0.0,
            gt_status="POSITIVE",
        )
        assert anomalies["missed_crack_heuristic"] is True
        assert anomalies["anomaly_missed_crack"] is True
        assert anomalies["fragmentation_proxy"] is False
        assert anomalies["broad_mask_heuristic"] is False

    def test_fragmentation_proxy(self):
        # GT is 1 crack, but model returned 4 fragmented detections
        meas = [{"area_px": 50, "length_px": 20, "width_px": 2.5, "max_width_px": 3.0}] * 4
        anomalies = detect_anomalies(
            det_count=4,
            gt_polygon_count=1,
            gt_area_px=500.0,
            det_measurements=meas,
            iou=0.6,
            gt_status="POSITIVE",
        )
        assert anomalies["fragmentation_proxy"] is True
        assert anomalies["anomaly_fragmented"] is True
        assert anomalies["missed_crack_heuristic"] is False

    def test_suspiciously_broad_mask_heuristic(self):
        # Measurement with average width > 25px
        meas = [{"area_px": 2000, "length_px": 50, "width_px": 40.0, "max_width_px": 55.0}]
        anomalies = detect_anomalies(
            det_count=1,
            gt_polygon_count=1,
            gt_area_px=1000.0,
            det_measurements=meas,
            iou=0.5,
            gt_status="POSITIVE",
        )
        assert anomalies["broad_mask_heuristic"] is True
        assert anomalies["anomaly_broad_mask"] is True

    def test_false_positive_on_verified_clean_surface(self):
        meas = [{"area_px": 100, "length_px": 30, "width_px": 3.0, "max_width_px": 4.0}]
        anomalies = detect_anomalies(
            det_count=1,
            gt_polygon_count=0,
            gt_area_px=0.0,
            det_measurements=meas,
            iou=0.0,
            gt_status="VERIFIED_NEGATIVE",
        )
        assert anomalies["false_positive"] is True

    def test_missing_label_does_not_falsely_trigger_false_positive(self):
        meas = [{"area_px": 100, "length_px": 30, "width_px": 3.0, "max_width_px": 4.0}]
        anomalies = detect_anomalies(
            det_count=1,
            gt_polygon_count=0,
            gt_area_px=0.0,
            det_measurements=meas,
            iou=None,
            gt_status="MISSING_LABEL",
        )
        # Should NOT be flagged as false positive because ground truth is missing
        assert anomalies["false_positive"] is False


class TestLatencyStatistics:
    def test_compute_latency_statistics(self):
        latencies = [50.0, 60.0, 70.0, 80.0, 100.0, 200.0]
        stats = compute_latency_statistics(latencies)
        assert stats["mean_ms"] == pytest.approx(93.33, abs=0.1)
        assert stats["median_ms"] == 75.0
        assert stats["p95_ms"] > 150.0
        assert stats["min_ms"] == 50.0
        assert stats["max_ms"] == 200.0

    def test_empty_latency_list(self):
        stats = compute_latency_statistics([])
        assert stats["mean_ms"] == 0.0
        assert stats["median_ms"] == 0.0
        assert stats["p95_ms"] == 0.0


class TestBenchmarkSummaryComputation:
    def test_summary_separates_positive_and_negative_metrics(self):
        records = [
            # 1. Positive image with detection
            {
                "image_name": "pos_1.jpg",
                "gt_status": "POSITIVE",
                "gt_crack_count": 1,
                "gt_mask_area_px": 1000.0,
                "detection_count": 1,
                "total_mask_area_px": 900.0,
                "total_skeleton_length_px": 150.0,
                "mean_crack_width_px": 6.0,
                "max_crack_width_px": 8.0,
                "inference_time_ms": 60.0,
                "mask_iou": 0.80,
                "mask_dice": 0.88,
                "anomaly_missed_crack_heuristic": False,
                "anomaly_fragmentation_proxy": False,
                "anomaly_broad_mask_heuristic": False,
                "anomaly_false_positive": False,
            },
            # 2. Positive image with missed detection
            {
                "image_name": "pos_2.jpg",
                "gt_status": "POSITIVE",
                "gt_crack_count": 1,
                "gt_mask_area_px": 500.0,
                "detection_count": 0,
                "total_mask_area_px": 0.0,
                "total_skeleton_length_px": 0.0,
                "mean_crack_width_px": 0.0,
                "max_crack_width_px": 0.0,
                "inference_time_ms": 50.0,
                "mask_iou": 0.0,
                "mask_dice": 0.0,
                "anomaly_missed_crack_heuristic": True,
                "anomaly_fragmentation_proxy": False,
                "anomaly_broad_mask_heuristic": False,
                "anomaly_false_positive": False,
            },
            # 3. Clean negative image with true negative
            {
                "image_name": "neg_1.jpg",
                "gt_status": "VERIFIED_NEGATIVE",
                "gt_crack_count": 0,
                "gt_mask_area_px": 0.0,
                "detection_count": 0,
                "total_mask_area_px": 0.0,
                "total_skeleton_length_px": 0.0,
                "mean_crack_width_px": 0.0,
                "max_crack_width_px": 0.0,
                "inference_time_ms": 55.0,
                "mask_iou": None,
                "mask_dice": None,
                "anomaly_missed_crack_heuristic": False,
                "anomaly_fragmentation_proxy": False,
                "anomaly_broad_mask_heuristic": False,
                "anomaly_false_positive": False,
            },
            # 4. Clean negative image with false positive
            {
                "image_name": "neg_2.jpg",
                "gt_status": "VERIFIED_NEGATIVE",
                "gt_crack_count": 0,
                "gt_mask_area_px": 0.0,
                "detection_count": 1,
                "total_mask_area_px": 100.0,
                "total_skeleton_length_px": 20.0,
                "mean_crack_width_px": 4.0,
                "max_crack_width_px": 5.0,
                "inference_time_ms": 65.0,
                "mask_iou": 0.0,
                "mask_dice": 0.0,
                "anomaly_missed_crack_heuristic": False,
                "anomaly_fragmentation_proxy": False,
                "anomaly_broad_mask_heuristic": False,
                "anomaly_false_positive": True,
            },
        ]

        summary = compute_benchmark_summary(records)

        assert summary["total_images"] == 4
        assert summary["positive_images_count"] == 2
        assert summary["negative_images_count"] == 2
        # IoU should be strictly averaged over positive images: (0.80 + 0.0) / 2 = 0.40
        assert summary["mean_iou_positive_gt"] == 0.40
        assert summary["mean_dice_positive_gt"] == 0.44
        # Negative FP rate: 1 out of 2 = 50%
        assert summary["negative_fp_count"] == 1
        assert summary["negative_fp_rate"] == 0.50
        # Measurements on valid detections: 2 images have detections (pos_1 and neg_2)
        assert summary["images_with_valid_detections"] == 2
        assert summary["images_without_detections"] == 2
        assert summary["mean_width_detected_px"] == pytest.approx(5.0, abs=0.1)


class TestCheckpointVerification:
    def test_missing_model2_without_single_model_flag(self, tmp_path: Path):
        m1 = tmp_path / "model1.pt"
        m1.write_bytes(b"dummy_weights")
        m2 = tmp_path / "model2.pt"  # does not exist

        can_proceed, msg = verify_checkpoints(m1, m2, allow_single_model=False)
        assert can_proceed is False
        assert "Comparative evaluation cannot proceed" in msg
        assert str(m2.resolve()) in msg

    def test_missing_model2_with_single_model_flag(self, tmp_path: Path):
        m1 = tmp_path / "model1.pt"
        m1.write_bytes(b"dummy_weights")
        m2 = tmp_path / "model2.pt"

        can_proceed, msg = verify_checkpoints(m1, m2, allow_single_model=True)
        assert can_proceed is True
        assert "Proceeding with Model 1 baseline" in msg

    def test_both_checkpoints_present(self, tmp_path: Path):
        m1 = tmp_path / "model1.pt"
        m1.write_bytes(b"dummy1")
        m2 = tmp_path / "model2.pt"
        m2.write_bytes(b"dummy2")

        can_proceed, msg = verify_checkpoints(m1, m2, allow_single_model=False)
        assert can_proceed is True
        assert "Both checkpoints found and verified" in msg


class TestReporting:
    def test_csv_and_markdown_generation(self, tmp_path: Path):
        records = [
            {
                "image_name": "test_01.jpg",
                "image_width": 416,
                "image_height": 416,
                "gt_status": "POSITIVE",
                "gt_crack_count": 1,
                "gt_mask_area_px": 1500.0,
                "model_name": "YOLO11n-seg",
                "detection_count": 1,
                "total_mask_area_px": 1450.0,
                "total_skeleton_length_px": 180.0,
                "mean_crack_width_px": 8.0,
                "max_crack_width_px": 11.2,
                "inference_time_ms": 65.4,
                "mask_iou": 0.65,
                "mask_dice": 0.78,
                "anomaly_missed_crack_heuristic": False,
                "anomaly_fragmentation_proxy": False,
                "anomaly_broad_mask_heuristic": False,
                "anomaly_false_positive": False,
                "anomaly_missed_crack": False,
                "anomaly_fragmented": False,
                "anomaly_broad_mask": False,
                "calibration_status": "uncalibrated_pixel_space",
            }
        ]

        csv_path = tmp_path / "out.csv"
        save_results_csv(records, csv_path)
        assert csv_path.is_file()
        content = csv_path.read_text(encoding="utf-8")
        assert "test_01.jpg" in content
        assert "uncalibrated_pixel_space" in content
        assert "anomaly_fragmentation_proxy" in content

        md_path = tmp_path / "out.md"
        md_text = generate_markdown_report(records, "YOLO11n-seg", None, md_path)
        assert md_path.is_file()
        assert "Benchmark Report" in md_text
        assert "0.65" in md_text
        assert "pixel units" in md_text.lower()
        assert "not coco instance-level" in md_text.lower()
