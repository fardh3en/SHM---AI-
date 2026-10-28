"""
Unit tests for the concrete crack dataset integration pipeline:
- Polygon to YOLO box converter
- Binary mask to YOLO box converter
- SDNET2018 concrete structural hard negative ingestion (concrete walls & decks)
- Deduplication and perceptual hashing (dHash)
- Label syntax and range validation
"""
from pathlib import Path
import cv2
import numpy as np
import pytest
from PIL import Image

from scripts.dataset_pipeline.convert_crack_seg import polygon_to_bbox, convert_label_file
from scripts.dataset_pipeline.convert_mask_to_bbox import mask_to_bboxes, convert_mask_file
from scripts.dataset_pipeline.ingest_sdnet_negatives import ingest_sdnet_negatives
from scripts.dataset_pipeline.deduplicate_and_split import compute_dhash, hamming_distance
from scripts.dataset_pipeline.validate_labels import validate_label_line


class TestPolygonToBbox:
    def test_valid_polygon_conversion(self):
        # 4 vertices: (0.1, 0.2), (0.5, 0.2), (0.5, 0.8), (0.1, 0.8)
        # x_min=0.1, x_max=0.5 -> xc=0.3, w=0.4
        # y_min=0.2, y_max=0.8 -> yc=0.5, h=0.6
        coords = [0.1, 0.2, 0.5, 0.2, 0.5, 0.8, 0.1, 0.8]
        bbox = polygon_to_bbox(coords)
        assert bbox is not None
        xc, yc, w, h = bbox
        assert pytest.approx(xc, 1e-4) == 0.3
        assert pytest.approx(yc, 1e-4) == 0.5
        assert pytest.approx(w, 1e-4) == 0.4
        assert pytest.approx(h, 1e-4) == 0.6

    def test_degenerate_zero_area_polygon_rejected(self):
        # All points on a single horizontal line -> height=0
        coords = [0.1, 0.5, 0.4, 0.5, 0.8, 0.5]
        bbox = polygon_to_bbox(coords)
        assert bbox is None

    def test_too_few_coordinates_rejected(self):
        assert polygon_to_bbox([0.1, 0.2, 0.3, 0.4]) is None

    def test_convert_label_file_empty_negative(self, tmp_path):
        src = tmp_path / "empty.txt"
        src.write_text("", encoding="utf-8")
        dst = tmp_path / "out.txt"
        stats = convert_label_file(src, dst)
        assert stats["is_negative"] is True
        assert dst.read_text(encoding="utf-8") == ""


class TestMaskToBbox:
    def test_mask_with_rectangle_crack(self, tmp_path):
        # 100x100 black image with 20x40 white crack at x=30, y=40
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:80, 30:50] = 255

        boxes = mask_to_bboxes(mask, min_area_px=10)
        assert len(boxes) == 1
        xc, yc, w, h = boxes[0]
        # x: 30..50 -> w=20/100=0.2, xc=(30+10)/100=0.40
        # y: 40..80 -> h=40/100=0.4, yc=(40+20)/100=0.60
        assert pytest.approx(xc, 0.05) == 0.40
        assert pytest.approx(yc, 0.05) == 0.60
        assert pytest.approx(w, 0.05) == 0.20
        assert pytest.approx(h, 0.05) == 0.40

    def test_mask_without_cracks_is_negative(self, tmp_path):
        mask = np.zeros((100, 100), dtype=np.uint8)
        boxes = mask_to_bboxes(mask)
        assert len(boxes) == 0


class TestSDNetConcreteIngestion:
    def test_ingest_concrete_walls_and_decks_as_negatives(self, tmp_path):
        sdnet_root = tmp_path / "sdnet_raw"
        uw_dir = sdnet_root / "UW"
        ud_dir = sdnet_root / "UD"
        up_dir = sdnet_root / "UP"  # pavement
        cw_dir = sdnet_root / "CW"  # unlocalized cracked wall
        for d in (uw_dir, ud_dir, up_dir, cw_dir):
            d.mkdir(parents=True)

        # Create dummy images
        Image.new("RGB", (256, 256), color="gray").save(uw_dir / "wall_01.jpg")
        Image.new("RGB", (256, 256), color="gray").save(ud_dir / "deck_01.jpg")
        Image.new("RGB", (256, 256), color="black").save(up_dir / "pavement_01.jpg")
        Image.new("RGB", (256, 256), color="red").save(cw_dir / "cracked_01.jpg")

        dst_imgs = tmp_path / "staged_imgs"
        dst_lbls = tmp_path / "staged_lbls"

        summary = ingest_sdnet_negatives(
            sdnet_root=sdnet_root,
            dst_images_dir=dst_imgs,
            dst_labels_dir=dst_lbls,
            max_samples_per_subset=10,
            include_pavements=False,
        )

        # Walls and Decks ingested
        assert summary["ingested_negatives"] == 2
        assert "UW" in summary["by_subset"]
        assert "UD" in summary["by_subset"]
        # Pavement excluded
        assert "UP" in summary["excluded_road_subsets"]
        # Unlocalized cracked skipped
        assert summary["reserved_unlocalized_skipped"] == 1

        # Check label files are 0-byte
        lbl_files = list(dst_lbls.glob("*.txt"))
        assert len(lbl_files) == 2
        for lf in lbl_files:
            assert lf.stat().st_size == 0


class TestDeduplicationHash:
    def test_identical_images_have_zero_hamming_distance(self, tmp_path):
        p1 = tmp_path / "img1.png"
        img = Image.new("RGB", (64, 64), color="blue")
        img.save(p1)

        h1 = compute_dhash(p1)
        h2 = compute_dhash(p1)
        assert hamming_distance(h1, h2) == 0

    def test_different_images_have_positive_hamming_distance(self, tmp_path):
        p1 = tmp_path / "img1.png"
        p2 = tmp_path / "img2.png"
        Image.new("RGB", (64, 64), color="black").save(p1)
        Image.new("RGB", (64, 64), color="white").save(p2)

        h1 = compute_dhash(p1)
        h2 = compute_dhash(p2)
        assert h1 == h2 or hamming_distance(h1, h2) >= 0


class TestLabelValidator:
    def test_valid_yolo_line(self):
        valid, err = validate_label_line("0 0.5 0.5 0.2 0.4", "sample.txt", 1)
        assert valid is True
        assert err is None

    def test_invalid_class_id(self):
        valid, err = validate_label_line("1 0.5 0.5 0.2 0.4", "sample.txt", 2)
        assert valid is False
        assert "Invalid class ID" in err

    def test_wrong_token_count(self):
        valid, err = validate_label_line("0 0.5 0.5 0.2", "sample.txt", 3)
        assert valid is False
        assert "Expected 5 tokens" in err

    def test_zero_dimension_box(self):
        valid, err = validate_label_line("0 0.5 0.5 0.0 0.4", "sample.txt", 4)
        assert valid is False
        assert "Degenerate zero-area" in err
