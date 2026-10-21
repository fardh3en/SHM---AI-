"""
Script to provision YOLO11 segmentation weights for SHM-AI.

Usage:
    python scripts/download_weights.py          # Interactive confirmation
    python scripts/download_weights.py --yes    # Non-interactive confirmation
"""
import argparse
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import get_settings


def download_weights(
    model_name: str | None = None, force: bool = False, assume_yes: bool = False
) -> bool:
    settings = get_settings()
    target_name = model_name or settings.DEFAULT_MODEL_NAME
    dest_path = settings.WEIGHTS_DIR / target_name
    settings.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    if dest_path.is_file() and not force:
        print(f"Model weights already present at '{dest_path}' ({dest_path.stat().st_size:,} bytes).")
        print("Use --force to re-download.")
        return True

    url = f"https://github.com/ultralytics/assets/releases/download/v8.4.0/{target_name}"
    print(f"Target model:   {target_name}")
    print(f"Download URL:   {url}")
    print(f"Destination:    {dest_path}")
    print("Estimated size: ~6 MB")

    if not assume_yes:
        response = input("Proceed with model weight download? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("Download canceled by user.")
            return False

    print(f"Downloading {target_name}...")
    try:
        def reporthook(block_num, block_size, total_size):
            if total_size > 0:
                percent = min(100.0, (block_num * block_size / total_size) * 100)
                sys.stdout.write(f"\rProgress: {percent:.1f}% ({block_num * block_size:,} / {total_size:,} bytes)")
                sys.stdout.flush()

        urllib.request.urlretrieve(url, dest_path, reporthook=reporthook)
        print("\nDownload complete! Verified on disk.")
        return True
    except Exception as exc:
        print(f"\nDownload failed: {exc}", file=sys.stderr)
        if dest_path.is_file():
            dest_path.unlink()
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download YOLO11 segmentation weights for SHM-AI.")
    parser.add_argument("--model", type=str, default=None, help="Model filename (default: from config)")
    parser.add_argument("--force", action="store_true", help="Force re-download even if weights exist")
    parser.add_argument("-y", "--yes", action="store_true", help="Assume yes without interactive prompt")
    args = parser.parse_args()

    success = download_weights(model_name=args.model, force=args.force, assume_yes=args.yes)
    sys.exit(0 if success else 1)
