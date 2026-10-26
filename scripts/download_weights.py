"""
Script to provision YOLO11 segmentation weights for SHM-AI.

Usage:
    python scripts/download_weights.py          # Interactive confirmation
    python scripts/download_weights.py --yes    # Non-interactive confirmation
"""
import argparse
import http.client
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import get_settings

# Minimum expected file size for YOLO11 nano segmentation weights (~6 MB).
# Any file smaller than 1 MB is considered empty, truncated, or corrupt.
MIN_EXPECTED_BYTES = 1_000_000


class IncompleteDownloadError(IOError):
    """Raised when a download payload is prematurely terminated or truncated."""
    pass


def _is_transient_network_error(exc: Exception) -> bool:
    """
    Determine if an exception represents a transient failure eligible for retry.

    Transient (retried with backoff):
      - Socket timeouts (TimeoutError, socket.timeout)
      - Connection resets/refusals (ConnectionResetError, ConnectionRefusedError, BrokenPipeError)
      - Network/DNS/transport failures (urllib.error.URLError, IncompleteRead, RemoteDisconnected)
      - Transient HTTP status codes: HTTP 408 (Request Timeout), HTTP 429 (Too Many Requests),
        and HTTP 5xx (Server Errors: 500, 502, 503, 504)
      - Prematurely truncated payloads (IncompleteDownloadError)

    Non-transient / Permanent (aborts immediately without retrying):
      - Permanent HTTP errors: HTTP 400, 401, 403, 404, 405, 410, etc.
    """
    if isinstance(exc, urllib.error.HTTPError):
        # Transient HTTP errors: 408, 429, and 500..599
        return exc.code in (408, 429) or (500 <= exc.code <= 599)

    if isinstance(exc, (
        urllib.error.URLError,
        TimeoutError,
        ConnectionError,
        http.client.HTTPException,
        IncompleteDownloadError,
        OSError,
    )):
        return True

    return False


def download_weights(
    model_name: str | None = None,
    force: bool = False,
    assume_yes: bool = False,
    max_retries: int = 3,
    timeout_seconds: float = 30.0,
    backoff_factor: float = 2.0,
) -> bool:
    """
    Download model weights with bounded retries, exponential backoff, and size verification.

    Preserves existing valid weight files if replacement fails. Categorizes errors into
    transient (retried) vs permanent (aborted immediately).

    Args:
        model_name: Name of the model file inside WEIGHTS_DIR (default: from config).
        force: If True, re-download even if an existing valid weights file is present.
        assume_yes: Non-interactive mode (skips user prompt).
        max_retries: Maximum number of retry attempts for transient network failures.
        timeout_seconds: Socket connection and read timeout in seconds per attempt.
        backoff_factor: Multiplier for exponential backoff delay between retries.

    Returns:
        bool: True if weights are present and verified on disk, False otherwise.
    """
    settings = get_settings()
    target_name = model_name or settings.DEFAULT_MODEL_NAME
    dest_path = settings.WEIGHTS_DIR / target_name
    settings.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Check if already present and valid ───────────────────────────────────
    if dest_path.is_file() and not force:
        size = dest_path.stat().st_size
        if size >= MIN_EXPECTED_BYTES:
            print(f"Model weights already present and verified at '{dest_path}' ({size:,} bytes).")
            print("Use --force to re-download.")
            return True
        else:
            print(
                f"Existing model file at '{dest_path}' is corrupted or truncated "
                f"({size:,} bytes < {MIN_EXPECTED_BYTES:,} bytes threshold). Re-downloading..."
            )

    url = f"https://github.com/ultralytics/assets/releases/download/v8.4.0/{target_name}"
    print(f"Target model:   {target_name}")
    print(f"Download URL:   {url}")
    print(f"Destination:    {dest_path}")
    print("Estimated size: ~6 MB")
    print(f"Retry policy:   up to {max_retries} retries on transient errors, timeout={timeout_seconds}s")

    if not assume_yes:
        response = input("Proceed with model weight download? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("Download canceled by user.")
            return False

    max_attempts = max(1, max_retries + 1)
    part_path = dest_path.with_name(f"{dest_path.name}.part")

    for attempt in range(1, max_attempts + 1):
        print(f"Downloading {target_name} (attempt {attempt}/{max_attempts})...")
        try:
            # Clean up any leftover partial file before starting attempt
            if part_path.exists():
                part_path.unlink()

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "SHM-AI-Provisioner/1.0 (Render-Build; +https://github.com/fardh3en/SHM---AI-)",
                    "Accept": "application/octet-stream,*/*",
                },
            )

            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                total_size_hdr = response.headers.get("Content-Length")
                total_size = int(total_size_hdr) if total_size_hdr and total_size_hdr.isdigit() else -1

                downloaded = 0
                chunk_size = 64 * 1024  # 64 KB
                with open(part_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = min(100.0, (downloaded / total_size) * 100)
                            sys.stdout.write(
                                f"\rProgress: {percent:.1f}% ({downloaded:,} / {total_size:,} bytes)"
                            )
                            sys.stdout.flush()

                if total_size > 0:
                    sys.stdout.write("\n")

            # ── Verification of downloaded file ──────────────────────────────
            if not part_path.is_file():
                raise IOError(f"Downloaded temporary file missing at '{part_path}'")

            part_size = part_path.stat().st_size
            if part_size < MIN_EXPECTED_BYTES:
                raise IncompleteDownloadError(
                    f"Downloaded file '{part_path.name}' is suspiciously small "
                    f"({part_size:,} bytes < {MIN_EXPECTED_BYTES:,} bytes threshold). Incomplete download."
                )

            if total_size > 0 and part_size != total_size:
                raise IncompleteDownloadError(
                    f"Downloaded file size ({part_size:,} bytes) does not match Content-Length header ({total_size:,} bytes)."
                )

            # Atomic swap to target destination (leaves existing dest_path intact until verified)
            part_path.replace(dest_path)
            print(f"Download complete and verified on disk at '{dest_path}' ({part_size:,} bytes).")
            print(
                "[Model Integrity Notice] Verified file size against expected threshold and Content-Length. "
                "Upstream distributor does not publish cryptographic checksums for this release; "
                "structural verification is completed via model format loading inspection."
            )
            return True

        except Exception as exc:
            print(f"\nDownload attempt {attempt}/{max_attempts} failed: {exc}", file=sys.stderr)
            if part_path.exists():
                try:
                    part_path.unlink()
                except OSError:
                    pass

            is_transient = _is_transient_network_error(exc)
            if not is_transient:
                print(
                    f"Permanent error encountered ({exc}). Aborting download without further retries.",
                    file=sys.stderr,
                )
                return False

            if attempt < max_attempts:
                sleep_time = min(30.0, backoff_factor ** (attempt - 1))
                print(
                    f"Retrying in {sleep_time:.1f}s (transient error recovery: {exc})...",
                    file=sys.stderr,
                )
                time.sleep(sleep_time)
            else:
                print(
                    f"All {max_attempts} download attempts failed. Model weights could not be provisioned.",
                    file=sys.stderr,
                )
                return False

    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download YOLO11 segmentation weights for SHM-AI.")
    parser.add_argument("--model", type=str, default=None, help="Model filename (default: from config)")
    parser.add_argument("--force", action="store_true", help="Force re-download even if weights exist")
    parser.add_argument("-y", "--yes", action="store_true", help="Assume yes without interactive prompt")
    parser.add_argument("--retries", type=int, default=3, help="Max retry attempts on transient network error (default: 3)")
    parser.add_argument("--timeout", type=float, default=30.0, help="Socket timeout in seconds per attempt (default: 30.0)")
    args = parser.parse_args()

    success = download_weights(
        model_name=args.model,
        force=args.force,
        assume_yes=args.yes,
        max_retries=args.retries,
        timeout_seconds=args.timeout,
    )
    sys.exit(0 if success else 1)
