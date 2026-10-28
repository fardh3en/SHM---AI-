"""
Unit tests for scripts/prepare_crack_dataset.py
Verifies dataset validation logic, polygon line parser, transient network error classifier,
disk space guard, and smoke subset generation.
"""
import http.client
import io
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.prepare_crack_dataset import (
    AnnotationIssue,
    DatasetIntegrityError,
    InsufficientDiskSpaceError,
    SplitValidationStats,
    _is_transient_error,
    check_free_disk_space,
    create_smoke_test_subset,
    extract_dataset_archive,
    generate_dataset_report,
    validate_polygon_line,
    validate_split,
)


class TestValidatePolygonLine:
    """Test individual YOLO polygon annotation line validation."""

    def test_valid_polygon(self):
        # 1 class ID + 4 coordinate pairs (x, y)
        line = "0 0.1 0.2 0.3 0.4 0.5 0.6 0.1 0.2"
        valid, cls_id, points, issue = validate_polygon_line(line, 1, "test.txt")
        assert valid is True
        assert cls_id == 0
        assert len(points) == 4
        assert points[0] == (0.1, 0.2)
        assert points[1] == (0.3, 0.4)
        assert points[2] == (0.5, 0.6)
        assert points[3] == (0.1, 0.2)
        assert issue is None

    def test_empty_or_whitespace_line(self):
        valid, cls_id, points, issue = validate_polygon_line("   \n", 1, "test.txt")
        assert valid is True
        assert cls_id is None
        assert points is None
        assert issue is None

    def test_too_few_coordinates(self):
        # Only 2 points (4 coordinate tokens) -> 5 tokens total (minimum is 7 tokens)
        line = "0 0.1 0.2 0.3 0.4"
        valid, cls_id, points, issue = validate_polygon_line(line, 2, "test.txt")
        assert valid is False
        assert issue is not None
        assert issue.issue_type == "too_few_coordinates"
        assert issue.line_number == 2

    def test_invalid_class_id_non_integer(self):
        line = "crack 0.1 0.2 0.3 0.4 0.5 0.6"
        valid, cls_id, points, issue = validate_polygon_line(line, 3, "test.txt")
        assert valid is False
        assert issue is not None
        assert issue.issue_type == "invalid_class_id"

    def test_odd_coordinate_count(self):
        # 1 class + 7 coords (>= 6 coords, but odd number: 7 coords instead of pairs)
        line = "0 0.1 0.2 0.3 0.4 0.5 0.6 0.7"
        valid, cls_id, points, issue = validate_polygon_line(line, 4, "test.txt")
        assert valid is False
        assert issue is not None
        assert issue.issue_type == "odd_coordinate_count"

    def test_non_numeric_coordinate(self):
        line = "0 0.1 0.2 abc 0.4 0.5 0.6"
        valid, cls_id, points, issue = validate_polygon_line(line, 5, "test.txt")
        assert valid is False
        assert issue is not None
        assert issue.issue_type == "non_numeric_coordinate"

    def test_unnormalized_coordinate_out_of_range(self):
        # Coordinate 2.5 is way beyond normalized [0, 1] range
        line = "0 0.1 0.2 2.5 0.4 0.5 0.6"
        valid, cls_id, points, issue = validate_polygon_line(line, 6, "test.txt")
        assert valid is False
        assert issue is not None
        assert issue.issue_type == "unnormalized_coordinate"

    def test_slight_floating_point_tolerance_clamping(self):
        # Slightly out of bounds e.g. -0.001 and 1.002 should clamp to 0.0 and 1.0
        line = "0 -0.001 0.2 1.002 0.4 0.5 0.6"
        valid, cls_id, points, issue = validate_polygon_line(line, 7, "test.txt")
        assert valid is True
        assert points is not None
        assert points[0] == (0.0, 0.2)
        assert points[1] == (1.0, 0.4)
        assert issue is None


class TestDiskSpaceCheck:
    """Test disk space pre-flight validation."""

    def test_sufficient_space(self, tmp_path):
        with patch("shutil.disk_usage", return_value=(100_000_000_000, 50_000_000_000, 50_000_000_000)):
            free = check_free_disk_space(tmp_path, min_bytes=1_000_000_000)
            assert free == 50_000_000_000

    def test_insufficient_space_raises_exception(self, tmp_path):
        with patch("shutil.disk_usage", return_value=(100_000_000_000, 99_500_000_000, 500_000_000)):
            with pytest.raises(InsufficientDiskSpaceError) as exc_info:
                check_free_disk_space(tmp_path, min_bytes=1_000_000_000)
            assert "Insufficient disk space" in str(exc_info.value)


class TestTransientErrorClassifier:
    """Test classification of network errors for resilient retry."""

    def test_http_transient_status_codes(self):
        for code in (408, 429, 500, 502, 503, 504):
            err = urllib.error.HTTPError("http://example.com", code, "Error", hdrs=None, fp=None)
            assert _is_transient_error(err) is True

    def test_http_permanent_status_codes(self):
        for code in (400, 401, 403, 404, 405):
            err = urllib.error.HTTPError("http://example.com", code, "Error", hdrs=None, fp=None)
            assert _is_transient_error(err) is False

    def test_network_connection_errors(self):
        assert _is_transient_error(TimeoutError("timed out")) is True
        assert _is_transient_error(ConnectionResetError("reset")) is True
        assert _is_transient_error(urllib.error.URLError("connection refused")) is True
        assert _is_transient_error(http.client.IncompleteRead(b"partial")) is True

    def test_non_network_exceptions(self):
        assert _is_transient_error(ValueError("bad value")) is False
        assert _is_transient_error(KeyError("missing key")) is False


class TestZipExtractionAndSecurity:
    """Test zip extraction and Zip Slip path traversal mitigation."""

    def test_extract_valid_archive_with_top_level_prefix(self, tmp_path):
        archive_path = tmp_path / "test_dataset.zip"
        extract_dir = tmp_path / "extracted"

        # Create zip with 'crack-seg/images/train/sample.jpg'
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("crack-seg/images/train/sample.jpg", b"fake-jpg-content")
            zf.writestr("crack-seg/labels/train/sample.txt", "0 0.1 0.2 0.3 0.4 0.5 0.6\n")

        out_root = extract_dataset_archive(archive_path, extract_dir)
        assert out_root == extract_dir
        # Confirm redundant 'crack-seg/' was stripped and images/ is directly under extract_dir
        assert (extract_dir / "images" / "train" / "sample.jpg").is_file()
        assert (extract_dir / "labels" / "train" / "sample.txt").is_file()
        assert not (extract_dir / "crack-seg").exists()

    def test_extract_archive_without_top_level_prefix(self, tmp_path):
        archive_path = tmp_path / "test_flat.zip"
        extract_dir = tmp_path / "extracted_flat"

        # Create zip directly with 'images/val/sample.jpg'
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("images/val/sample.jpg", b"fake-jpg-content")
            zf.writestr("labels/val/sample.txt", "0 0.1 0.2 0.3 0.4 0.5 0.6\n")

        out_root = extract_dataset_archive(archive_path, extract_dir)
        assert out_root == extract_dir
        assert (extract_dir / "images" / "val" / "sample.jpg").is_file()
        assert (extract_dir / "labels" / "val" / "sample.txt").is_file()


class TestSmokeSubsetAndReport:
    """Test 10-image smoke test subset creation and report export."""

    def test_create_smoke_test_subset(self, tmp_path):
        mock_ds = tmp_path / "mock_dataset"
        smoke_ds = tmp_path / "mock_smoke"

        # Create sample train/val/test images and labels
        for split, count in [("train", 8), ("val", 3), ("test", 3)]:
            (mock_ds / "images" / split).mkdir(parents=True, exist_ok=True)
            (mock_ds / "labels" / split).mkdir(parents=True, exist_ok=True)
            for i in range(count):
                (mock_ds / "images" / split / f"img_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff\xe0mock")
                (mock_ds / "labels" / split / f"img_{i:02d}.txt").write_text(
                    "0 0.1 0.2 0.3 0.4 0.5 0.6\n", encoding="utf-8"
                )

        manifest = create_smoke_test_subset(
            dataset_root=mock_ds,
            target_root=smoke_ds,
            num_train=6,
            num_val=2,
            num_test=2,
        )

        assert len(manifest["samples"]["train"]) == 6
        assert len(manifest["samples"]["val"]) == 2
        assert len(manifest["samples"]["test"]) == 2

        # Check smoke yaml was generated
        yaml_path = smoke_ds / "crack-smoke.yaml"
        assert yaml_path.is_file()
        yaml_content = yaml_path.read_text(encoding="utf-8")
        assert "0: crack" in yaml_content
        assert "train: images/train" in yaml_content

    def test_generate_dataset_report(self, tmp_path):
        stats = [
            SplitValidationStats(
                split_name="train",
                total_images=100,
                valid_images=100,
                corrupt_images=0,
                images_with_labels=90,
                empty_label_files=10,
                missing_label_files=0,
                orphan_label_files=0,
                total_polygon_instances=150,
                class_id_counts={0: 150},
                issues=[],
            )
        ]

        report = generate_dataset_report(tmp_path, stats)
        assert report["totals"]["total_images"] == 100
        assert report["totals"]["valid_images"] == 100
        assert report["totals"]["empty_label_files"] == 10
        assert report["totals"]["total_polygon_instances"] == 150
        assert (tmp_path / "dataset_report.json").is_file()
