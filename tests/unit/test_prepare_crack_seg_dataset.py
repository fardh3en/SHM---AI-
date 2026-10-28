"""
Unit tests for SHM-AI YOLO11 Crack Segmentation Dataset Preparation & Colab Notebook.

Verifies:
1. Prepared dataset directory structure and counts (4,217 train, 275 val, 112 test).
2. Genuine polygon annotations are preserved without conversion to bounding boxes.
3. Background negatives have 0-byte label files.
4. Independent test set preserved at exactly 112 positive images.
5. Absolute isolation from the 100-image negative benchmark (zero leakage).
6. Manifest and YAML configuration accuracy.
7. Original datasets and model weights remain completely unmodified.
8. Colab training notebook syntax and cell structure.
"""
import ast
import hashlib
import json
from pathlib import Path
import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "datasets" / "prepared_crack_seg_v1"
ORIG_SEG_DIR = PROJECT_ROOT / "datasets" / "crack-seg"
ORIG_DET_DIR = PROJECT_ROOT / "datasets" / "crack-concrete"
BENCHMARK_DIR = PROJECT_ROOT / "datasets" / "concrete-negatives-benchmark"
WEIGHTS_DIR = PROJECT_ROOT / "weights"
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "SHM_AI_YOLO11_Seg_Training.ipynb"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def test_prepared_dataset_splits_and_counts():
    """Verify prepared dataset has expected counts across train, val, and test splits."""
    assert DATASET_DIR.is_dir(), f"Prepared dataset directory missing: {DATASET_DIR}"

    expected_counts = {
        "train": (4217, 500),  # (total images, background negatives)
        "val": (275, 76),
        "test": (112, 0),
    }

    for split, (exp_total, exp_neg) in expected_counts.items():
        img_dir = DATASET_DIR / "images" / split
        lbl_dir = DATASET_DIR / "labels" / split

        assert img_dir.is_dir(), f"Missing images/{split}"
        assert lbl_dir.is_dir(), f"Missing labels/{split}"

        imgs = list(img_dir.glob("*.jpg"))
        lbls = list(lbl_dir.glob("*.txt"))

        assert len(imgs) == exp_total, f"Split {split}: expected {exp_total} images, got {len(imgs)}"
        assert len(lbls) == exp_total, f"Split {split}: expected {exp_total} labels, got {len(lbls)}"

        empty_lbls = sum(1 for l in lbls if l.stat().st_size == 0)
        assert empty_lbls == exp_neg, f"Split {split}: expected {exp_neg} empty labels, got {empty_lbls}"


def test_polygon_labels_not_converted_to_bboxes():
    """Verify that positive crack annotations remain multi-vertex polygons (>5 tokens), not 5-token bboxes."""
    for split in ("train", "val", "test"):
        lbl_dir = DATASET_DIR / "labels" / split
        for lbl_path in lbl_dir.glob("*.txt"):
            if lbl_path.stat().st_size == 0:
                continue
            content = lbl_path.read_text(encoding="utf-8").strip()
            for line in content.splitlines():
                tokens = line.strip().split()
                if not tokens:
                    continue
                assert tokens[0] == "0", f"Class mismatch in {lbl_path.name}: {tokens[0]}"
                assert len(tokens) >= 7, f"Line appears to be bbox (len={len(tokens)}), expected polygon in {lbl_path.name}"
                assert len(tokens) % 2 == 1, f"Odd coordinate count in {lbl_path.name}"
                # Verify coordinates normalized [0, 1]
                for coord_str in tokens[1:]:
                    val = float(coord_str)
                    assert 0.0 <= val <= 1.0, f"Coordinate {val} out of bounds in {lbl_path.name}"


def test_benchmark_isolation():
    """Verify that zero images in the 100-image negative benchmark appear in prepared_crack_seg_v1."""
    bench_imgs = list((BENCHMARK_DIR / "images").glob("*.jpg"))
    assert len(bench_imgs) == 100, f"Expected 100 benchmark images, found {len(bench_imgs)}"
    bench_shas = {compute_sha256(p) for p in bench_imgs}

    for split in ("train", "val", "test"):
        split_imgs = list((DATASET_DIR / "images" / split).glob("*.jpg"))
        for img in split_imgs:
            sha = compute_sha256(img)
            assert sha not in bench_shas, f"Leakage detected! Benchmark image {img.name} found in {split} split."


def test_yaml_configuration_and_manifest():
    """Verify dataset YAML content and provenance manifest."""
    yaml_path = DATASET_DIR / "crack_seg_prepared.yaml"
    assert yaml_path.is_file(), f"Missing dataset YAML: {yaml_path}"

    content = yaml_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)

    assert parsed["names"] == {0: "crack"} or parsed["names"] == ["crack"]
    assert parsed["train"] == "images/train"
    assert parsed["val"] == "images/val"
    assert parsed["test"] == "images/test"

    # Verify manifest
    manifest_path = DATASET_DIR / "manifest.json"
    assert manifest_path.is_file(), f"Missing manifest: {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["dataset_name"] == "prepared_crack_seg_v1"
    assert manifest["splits"]["train"]["total_images"] == 4217
    assert manifest["splits"]["val"]["total_images"] == 275
    assert manifest["splits"]["test"]["total_images"] == 112


def test_source_datasets_and_models_unmodified():
    """Verify that source datasets and candidate weights hashes remain untouched."""
    # Source dataset counts
    assert len(list((ORIG_SEG_DIR / "images" / "train").glob("*.jpg"))) == 3717
    assert len(list((ORIG_SEG_DIR / "images" / "val").glob("*.jpg"))) == 200
    assert len(list((ORIG_SEG_DIR / "images" / "test").glob("*.jpg"))) == 112

    assert len(list((ORIG_DET_DIR / "images" / "train").glob("*.jpg"))) == 3723
    assert len(list((ORIG_DET_DIR / "images" / "val").glob("*.jpg"))) == 477
    assert len(list((ORIG_DET_DIR / "images" / "test").glob("*.jpg"))) == 404

    # Checkpoint hashes
    yolo11_seg_path = WEIGHTS_DIR / "yolo11n-seg.pt"
    assert yolo11_seg_path.is_file()
    assert compute_sha256(yolo11_seg_path) == "55ed65c56c91713d23e8402371c6c49a6fd84f257f7dce452e8d70e41dcbe152"

    yolov8_det_path = WEIGHTS_DIR / "crack_yolov8n_concrete.pt"
    assert yolov8_det_path.is_file()
    assert compute_sha256(yolov8_det_path) == "290d3cd26749dddc8ede4173e3ca245df865993664085ae66affd363d500bc4a"


def test_colab_notebook_structure_and_syntax():
    """Verify the Colab notebook is valid JSON and all code cells parse with ast."""
    assert NOTEBOOK_PATH.is_file(), f"Notebook missing at: {NOTEBOOK_PATH}"
    data = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))

    cells = data.get("cells", [])
    assert len(cells) >= 12, f"Expected at least 12 cells, found {len(cells)}"

    code_cells = [c for c in cells if c["cell_type"] == "code"]
    assert len(code_cells) >= 6, "Expected at least 6 code cells"

    for idx, c in enumerate(code_cells):
        src = "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
        # Code cells must parse cleanly without syntax errors
        try:
            ast.parse(src)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in notebook code cell {idx}: {e}")
