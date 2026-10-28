"""
Packages `datasets/prepared_crack_seg_v1/` and `datasets/concrete-negatives-benchmark/`
into clean ZIP archives for Google Colab execution, and verifies their internal counts.
"""
from pathlib import Path
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "datasets" / "prepared_crack_seg_v1"
BENCHMARK_DIR = PROJECT_ROOT / "datasets" / "concrete-negatives-benchmark"

ZIP_DATASET_PATH = PROJECT_ROOT / "datasets" / "prepared_crack_seg_v1.zip"
ZIP_BENCHMARK_PATH = PROJECT_ROOT / "datasets" / "concrete-negatives-benchmark.zip"


def package_directory(src_dir: Path, zip_path: Path) -> dict[str, int]:
    """Compresses a directory into a zip file preserving internal relative paths."""
    print(f"Creating archive: {zip_path} from {src_dir}...")
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in src_dir.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(src_dir.parent)
                zf.write(file_path, arcname=rel_path.as_posix())
                file_count += 1
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Archived {file_count} files ({size_mb:.2f} MB).")
    return {"files": file_count, "size_mb": round(size_mb, 2)}


def verify_dataset_zip(zip_path: Path):
    """Verifies that the packaged zip contains all expected images, labels, YAML, and manifest."""
    print(f"\nVerifying archive: {zip_path}...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()

    train_imgs = [n for n in namelist if n.startswith("prepared_crack_seg_v1/images/train/") and n.endswith(".jpg")]
    val_imgs = [n for n in namelist if n.startswith("prepared_crack_seg_v1/images/val/") and n.endswith(".jpg")]
    test_imgs = [n for n in namelist if n.startswith("prepared_crack_seg_v1/images/test/") and n.endswith(".jpg")]

    train_lbls = [n for n in namelist if n.startswith("prepared_crack_seg_v1/labels/train/") and n.endswith(".txt")]
    val_lbls = [n for n in namelist if n.startswith("prepared_crack_seg_v1/labels/val/") and n.endswith(".txt")]
    test_lbls = [n for n in namelist if n.startswith("prepared_crack_seg_v1/labels/test/") and n.endswith(".txt")]

    has_yaml = "prepared_crack_seg_v1/crack_seg_prepared.yaml" in namelist
    has_manifest = "prepared_crack_seg_v1/manifest.json" in namelist

    print(f"  Archive contains {len(namelist)} entries:")
    print(f"  - Train Images: {len(train_imgs)} (expected 4217)")
    print(f"  - Train Labels: {len(train_lbls)} (expected 4217)")
    print(f"  - Val Images:   {len(val_imgs)} (expected 275)")
    print(f"  - Val Labels:   {len(val_lbls)} (expected 275)")
    print(f"  - Test Images:  {len(test_imgs)} (expected 112)")
    print(f"  - Test Labels:  {len(test_lbls)} (expected 112)")
    print(f"  - YAML present:     {has_yaml}")
    print(f"  - Manifest present: {has_manifest}")

    assert len(train_imgs) == 4217, f"Train images mismatch: {len(train_imgs)}"
    assert len(val_imgs) == 275, f"Val images mismatch: {len(val_imgs)}"
    assert len(test_imgs) == 112, f"Test images mismatch: {len(test_imgs)}"
    assert has_yaml, "crack_seg_prepared.yaml missing from zip!"
    assert has_manifest, "manifest.json missing from zip!"
    print("  [VERIFICATION PASSED] Prepared dataset archive is 100% complete and verified.")


if __name__ == "__main__":
    package_directory(DATASET_DIR, ZIP_DATASET_PATH)
    verify_dataset_zip(ZIP_DATASET_PATH)
    package_directory(BENCHMARK_DIR, ZIP_BENCHMARK_PATH)
