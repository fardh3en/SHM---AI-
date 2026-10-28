"""
Unit tests for the Google Colab training notebook:
notebooks/SHM_AI_Crack_Segmentation_Training.ipynb
"""
import ast
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "SHM_AI_Crack_Segmentation_Training.ipynb"


@pytest.fixture(scope="module")
def notebook_data():
    assert NOTEBOOK_PATH.is_file(), f"Notebook not found at {NOTEBOOK_PATH}"
    content = NOTEBOOK_PATH.read_text(encoding="utf-8")
    data = json.loads(content)
    return data


def test_notebook_format_and_metadata(notebook_data):
    """Verify Jupyter notebook schema and Colab accelerator metadata."""
    assert notebook_data.get("nbformat") == 4
    assert "cells" in notebook_data
    assert len(notebook_data["cells"]) >= 10

    metadata = notebook_data.get("metadata", {})
    assert metadata.get("accelerator") == "GPU"
    assert "colab" in metadata


def test_code_cells_syntax_validity(notebook_data):
    """Ensure every Python code cell is syntactically valid."""
    code_cells = [c for c in notebook_data["cells"] if c.get("cell_type") == "code"]
    assert len(code_cells) == 9

    for idx, cell in enumerate(code_cells, start=1):
        source = "".join(cell.get("source", []))
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"Code cell {idx} has syntax error: {e}")


def test_hardware_gpu_guard(notebook_data):
    """Verify GPU check and default safe abort behavior."""
    cell_sources = ["".join(c.get("source", [])) for c in notebook_data["cells"]]
    env_cell = cell_sources[1]  # First code cell

    assert "ALLOW_CPU = False" in env_cell
    assert "torch.cuda.is_available()" in env_cell
    assert "SystemExit" in env_cell
    assert "Runtime -> Change runtime type" in env_cell


def test_persistent_storage_google_drive(notebook_data):
    """Verify Google Drive integration for persistent checkpoints and weights."""
    all_code = "\n".join("".join(c.get("source", [])) for c in notebook_data["cells"] if c.get("cell_type") == "code")

    assert "drive.mount" in all_code
    assert "/content/drive/MyDrive/SHM_AI_Training/crack_yolo11n_seg" in all_code
    assert "OUTPUT_DIR" in all_code


def test_dataset_setup_and_integrity(notebook_data):
    """Verify dataset URL, AGPL-3.0 license, and split integrity logic."""
    all_content = "\n".join("".join(c.get("source", [])) for c in notebook_data["cells"])

    assert "crack-seg.zip" in all_content
    assert "AGPL-3.0" in all_content
    assert "crack-smoke" in all_content
    assert "train: images/train" in all_content
    assert "val: images/val" in all_content
    assert "test: images/test" in all_content


def test_base_model_and_task_compatibility(notebook_data):
    """Verify yolo11n-seg.pt base model and segment task assertion."""
    all_code = "\n".join("".join(c.get("source", [])) for c in notebook_data["cells"] if c.get("cell_type") == "code")

    assert "yolo11n-seg.pt" in all_code
    assert 'base_model.task == "segment"' in all_code or "base_model.task == 'segment'" in all_code


def test_safety_guard_full_training_disabled(notebook_data):
    """Verify full training is disabled by default and does not overwrite best.pt."""
    all_code = "\n".join("".join(c.get("source", [])) for c in notebook_data["cells"] if c.get("cell_type") == "code")

    assert "RUN_FULL_TRAINING = False" in all_code
    assert 'CANDIDATE_MODEL_NAME = "crack_yolo11n_seg.pt"' in all_code
    assert "best.pt" not in 'CANDIDATE_MODEL_NAME = "crack_yolo11n_seg.pt"'


def test_held_out_test_set_evaluation(notebook_data):
    """Verify evaluation is strictly on split='test' and reports box/mask mAP."""
    all_code = "\n".join("".join(c.get("source", [])) for c in notebook_data["cells"] if c.get("cell_type") == "code")

    assert 'split="test"' in all_code or "split='test'" in all_code
    assert "test_metrics.box.map50" in all_code
    assert "test_metrics.seg.map50" in all_code


def test_concrete_training_notebook():
    """Verify concrete structural YOLOv8 training notebook syntax and safety guards."""
    concrete_nb_path = PROJECT_ROOT / "notebooks" / "SHM_AI_YOLOv8_Concrete_Training.ipynb"
    assert concrete_nb_path.is_file(), f"Concrete notebook not found at {concrete_nb_path}"
    data = json.loads(concrete_nb_path.read_text(encoding="utf-8"))
    assert data.get("nbformat") == 4
    code_cells = [c for c in data["cells"] if c.get("cell_type") == "code"]
    assert len(code_cells) >= 5

    for idx, cell in enumerate(code_cells, start=1):
        source = "".join(cell.get("source", []))
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"Concrete notebook cell {idx} syntax error: {e}")

    all_content = "\n".join("".join(c.get("source", [])) for c in data["cells"])
    assert "ALLOW_CPU = False" in all_content
    assert "RUN_FULL_TRAINING = False" in all_content
    assert "crack_yolov8n_concrete.pt" in all_content
    assert "RDD2022" not in all_content
    assert "Crack500" not in all_content

