"""
Unit tests for the Google Colab concrete crack training notebook:
notebooks/SHM_AI_YOLOv8_Concrete_Training.ipynb
"""
import ast
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "SHM_AI_YOLOv8_Concrete_Training.ipynb"


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
    assert len(notebook_data["cells"]) == 12

    metadata = notebook_data.get("metadata", {})
    assert metadata.get("accelerator") == "GPU"
    assert "colab" in metadata


def test_code_cells_syntax_validity(notebook_data):
    """Ensure every Python code cell is syntactically valid."""
    code_cells = [c for c in notebook_data["cells"] if c.get("cell_type") == "code"]
    assert len(code_cells) == 6

    for idx, cell in enumerate(code_cells, start=1):
        source = "".join(cell.get("source", []))
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"Code cell {idx} has syntax error: {e}")


def test_hardware_gpu_guard(notebook_data):
    """Verify GPU check and default safe abort behavior."""
    cell_sources = ["".join(c.get("source", [])) for c in notebook_data["cells"]]
    env_cell = cell_sources[1]

    assert "ALLOW_CPU = False" in env_cell
    assert "torch.cuda.is_available()" in env_cell
    assert "SystemExit" in env_cell
    assert "Runtime -> Change runtime type" in env_cell


def test_persistent_storage_google_drive(notebook_data):
    """Verify Google Drive integration for persistent checkpoints and weights."""
    all_code = "\n".join("".join(c.get("source", [])) for c in notebook_data["cells"] if c.get("cell_type") == "code")

    assert "drive.mount" in all_code
    assert "/content/drive/MyDrive/SHM_AI_Training/crack_yolov8n_concrete" in all_code
    assert "OUTPUT_DIR" in all_code


def test_dataset_setup_and_integrity(notebook_data):
    """Verify concrete dataset extraction, split structure, and hard negative handling."""
    all_content = "\n".join("".join(c.get("source", [])) for c in notebook_data["cells"])

    assert "crack-concrete.zip" in all_content
    assert "crack-concrete.yaml" in all_content
    assert "train: images/train" in all_content
    assert "val: images/val" in all_content
    assert "test: images/test" in all_content
    assert "576 verified hard negatives" in all_content or "hard negative" in all_content


def test_option_a_warm_start_and_candidate_name(notebook_data):
    """Verify Option A warm start loads v1 checkpoint and targets v2 candidate."""
    all_code = "\n".join("".join(c.get("source", [])) for c in notebook_data["cells"] if c.get("cell_type") == "code")

    assert "FINE_TUNE_PREV = True" in all_code
    assert "crack_yolov8n_concrete.pt" in all_code
    assert 'CANDIDATE_MODEL_NAME = "crack_yolov8n_concrete_v2.pt"' in all_code
    assert 'EPOCHS = 30' in all_code
    assert 'PATIENCE = 10' in all_code


def test_safety_guard_full_training_disabled(notebook_data):
    """Verify full training is disabled by default."""
    all_code = "\n".join("".join(c.get("source", [])) for c in notebook_data["cells"] if c.get("cell_type") == "code")

    assert "RUN_FULL_TRAINING = False" in all_code


def test_held_out_test_set_evaluation_and_baseline_delta(notebook_data):
    """Verify evaluation is strictly on split='test' and compares against baseline."""
    all_code = "\n".join("".join(c.get("source", [])) for c in notebook_data["cells"] if c.get("cell_type") == "code")

    assert 'split="test"' in all_code
    assert "BASELINE_V1" in all_code
    assert "test_evaluation_summary_v2.json" in all_code
