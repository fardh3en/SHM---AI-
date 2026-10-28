"""
Script to provision YOLO weights for SHM-AI.

Supports:
1. Default production weights (yolo11n-seg.pt) from Ultralytics official release assets.
2. Preview crack-specific weights (best.pt) from Hugging Face (cazzz307/yolov8-crack-detection, MIT license)
   via authenticated user token (HF_TOKEN) or custom private URL (MODEL_WEIGHTS_URL).

Usage:
    python scripts/download_weights.py          # Interactive confirmation
    python scripts/download_weights.py --yes    # Non-interactive confirmation
"""
import argparse
import http.client
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import get_settings

# Minimum expected file size for YOLO nano weights (~5.5 - 6.2 MB).
# Any file smaller than 1 MB is considered empty, truncated, or corrupt.
MIN_EXPECTED_BYTES = 1_000_000

# Upstream repository definitions
ULTRALYTICS_RELEASE_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0"
HF_CRACK_MODEL_NAME = "best.pt"
HF_CRACK_REPO = "cazzz307/yolov8-crack-detection"
HF_CRACK_URL = f"https://huggingface.co/{HF_CRACK_REPO}/resolve/main/best.pt"


class IncompleteDownloadError(IOError):
    """Raised when a download payload is prematurely terminated or truncated."""
    pass


class SafeAuthRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    HTTP redirect handler that preserves Authorization headers ONLY when
    redirecting within trusted Hugging Face origins (huggingface.co, *.huggingface.co)
    and strips Authorization headers when redirecting to external CDNs or storage hosts.
    """
    TRUSTED_AUTH_HOSTS = ("huggingface.co", "www.huggingface.co")

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is None:
            return None
        target_host = (urlparse(newurl).hostname or "").lower()
        # Strip credentials if redirect target is not a trusted Hugging Face host
        if target_host not in self.TRUSTED_AUTH_HOSTS and not target_host.endswith(".huggingface.co"):
            new_req.headers.pop("Authorization", None)
            new_req.unredirected_hdrs.pop("Authorization", None)
        return new_req


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
      - Format validation failures on completed model files
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


def _resolve_download_source(target_name: str, target_filename: str | None = None) -> tuple[str, dict[str, str]]:
    """
    Resolve the download URL and request headers for the requested model.

    Returns:
        tuple[url, headers]
    """
    resolved_file = target_filename or target_name
    custom_url = os.environ.get("MODEL_WEIGHTS_URL")
    if custom_url:
        return custom_url.strip(), {}

    if target_name == HF_CRACK_MODEL_NAME or resolved_file == HF_CRACK_MODEL_NAME:
        token = (
            os.environ.get("HF_TOKEN")
            or os.environ.get("HUGGINGFACE_TOKEN")
            or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        )
        if not token:
            print(
                f"\n[Provisioning Error] Candidate model '{target_name}' requires an authenticated Hugging Face token.\n"
                f"Repository '{HF_CRACK_REPO}' is gated under the MIT License.\n"
                "To provision this candidate model in a preview deployment:\n"
                f"  1. Accept access conditions at https://huggingface.co/{HF_CRACK_REPO}\n"
                "  2. Set the secret environment variable 'HF_TOKEN' on your Render preview service.",
                file=sys.stderr,
            )
            raise PermissionError(f"Missing HF_TOKEN for candidate model '{target_name}'")

        headers = {
            "Authorization": f"Bearer {token.strip()}",
            "User-Agent": "SHM-AI-Provisioner/1.0 (Render-Preview; +https://github.com/fardh3en/SHM---AI-)",
            "Accept": "application/octet-stream,*/*",
        }
        return HF_CRACK_URL, headers

    # Default production models from Ultralytics or upstream assets
    headers = {
        "User-Agent": "SHM-AI-Provisioner/1.0 (Render-Build; +https://github.com/fardh3en/SHM---AI-)",
        "Accept": "application/octet-stream,*/*",
    }
    return f"{ULTRALYTICS_RELEASE_URL}/{resolved_file}", headers


def download_weights(
    model_name: str | None = None,
    force: bool = False,
    assume_yes: bool = False,
    max_retries: int = 3,
    timeout_seconds: float = 30.0,
    backoff_factor: float = 2.0,
) -> bool:
    """
    Download model weights with bounded retries, exponential backoff, and size/format verification.

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
    target_name = (model_name or getattr(settings, "DEFAULT_MODEL_NAME", "yolo11n-seg.pt")).strip()
    aliases = getattr(settings, "MODEL_ALIASES", {})
    if isinstance(aliases, dict):
        target_filename = aliases.get(target_name.lower(), target_name)
    else:
        target_filename = target_name
    dest_path = settings.WEIGHTS_DIR / target_filename
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

    try:
        url, req_headers = _resolve_download_source(target_name, target_filename)
    except (PermissionError, FileNotFoundError) as perm_err:
        print(f"Provisioning aborted: {perm_err}", file=sys.stderr)
        return False

    display_source = (
        f"Hugging Face ({HF_CRACK_REPO})"
        if target_name == HF_CRACK_MODEL_NAME and not os.environ.get("MODEL_WEIGHTS_URL")
        else "Ultralytics GitHub Assets"
        if "github.com/ultralytics" in url
        else "Configured Remote URL"
    )

    print(f"Target model:   {target_name}")
    print(f"Download source: {display_source}")
    print(f"Destination:    {dest_path}")
    print("Estimated size: ~6 MB")
    print(f"Retry policy:   up to {max_retries} retries on transient errors, timeout={timeout_seconds}s")
    if "Authorization" in req_headers:
        print("Authentication: Bearer token configured (credentials masked)")

    if not assume_yes:
        response = input("Proceed with model weight download? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("Download canceled by user.")
            return False

    max_attempts = max(1, max_retries + 1)
    part_path = dest_path.with_name(f"{dest_path.name}.part")
    opener = urllib.request.build_opener(SafeAuthRedirectHandler)

    for attempt in range(1, max_attempts + 1):
        print(f"Downloading {target_name} (attempt {attempt}/{max_attempts})...")
        try:
            # Clean up any leftover partial file before starting attempt
            if part_path.exists():
                part_path.unlink()

            req = urllib.request.Request(url, headers=req_headers)

            with opener.open(req, timeout=timeout_seconds) as response:
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

            # ── PyTorch / Ultralytics Model Format & Task Validation ─────────
            try:
                from ultralytics import YOLO
                test_model = YOLO(str(part_path))
                expected_task = "detect" if target_name == HF_CRACK_MODEL_NAME else "segment"
                actual_task = str(getattr(test_model, "task", "unknown"))
                if actual_task != expected_task:
                    raise ValueError(
                        f"Model task mismatch: expected '{expected_task}', got '{actual_task}'"
                    )
            except Exception as format_err:
                raise ValueError(
                    f"Downloaded model weights failed format inspection: {format_err}"
                ) from format_err

            # Atomic swap to target destination (leaves existing dest_path intact until verified)
            part_path.replace(dest_path)
            print(f"Download complete and verified on disk at '{dest_path}' ({part_size:,} bytes).")
            print(
                "[Model Integrity Notice] Verified file size and model format architecture via PyTorch/Ultralytics. "
                "Upstream distributor does not publish cryptographic checksums for this release; "
                "integrity is established through format task loading and byte size thresholds."
            )
            return True

        except Exception as exc:
            # Mask any credentials if present in exception string
            exc_str = str(exc)
            if "Bearer" in exc_str:
                exc_str = "[Authorization Bearer masked]"

            print(f"\nDownload attempt {attempt}/{max_attempts} failed: {exc_str}", file=sys.stderr)
            if part_path.exists():
                try:
                    part_path.unlink()
                except OSError:
                    pass

            is_transient = _is_transient_network_error(exc)
            if not is_transient:
                print(
                    f"Permanent error encountered ({exc_str}). Aborting download without further retries.",
                    file=sys.stderr,
                )
                return False

            if attempt < max_attempts:
                sleep_time = min(30.0, backoff_factor ** (attempt - 1))
                print(
                    f"Retrying in {sleep_time:.1f}s (transient error recovery)...",
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
    parser = argparse.ArgumentParser(description="Download YOLO weights for SHM-AI.")
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
