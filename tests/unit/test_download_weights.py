"""
Unit tests for YOLO weight downloading, retry classification, and file integrity.

Tests:
1. An already-valid weights file (size >= 1MB) is not re-downloaded unless force=True.
2. A corrupted or empty (0-byte) weights file is detected and re-downloaded.
3. Transient connection failures (e.g. timeout / Errno 110) trigger retries with backoff and succeed.
4. Transient HTTP errors (e.g. HTTP 503, HTTP 429) trigger retries with backoff and succeed.
5. Permanent HTTP errors (e.g. HTTP 404, HTTP 403) fail immediately without retrying.
6. A failed replacement download (force=True) never deletes a previously valid weights file.
7. Persistent failures stop after the retry limit and clean up temporary .part files.
8. Truncated downloads (< 1MB) are rejected and temporary files cleaned up.
"""
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch
import urllib.error

import pytest

from scripts.download_weights import MIN_EXPECTED_BYTES, download_weights


def test_already_valid_weights_file_skips_download(tmp_path: Path):
    """An existing file >= MIN_EXPECTED_BYTES must not trigger network requests when force=False."""
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()
    valid_file = weights_dir / "yolo11n-seg.pt"
    # Write 2 MB of dummy data
    valid_file.write_bytes(b"\x00" * 2_000_000)

    with patch("scripts.download_weights.get_settings") as mock_settings:
        mock_settings.return_value.DEFAULT_MODEL_NAME = "yolo11n-seg.pt"
        mock_settings.return_value.WEIGHTS_DIR = weights_dir

        with patch("urllib.request.urlopen") as mock_urlopen:
            success = download_weights(assume_yes=True, force=False)
            assert success is True
            mock_urlopen.assert_not_called()


def test_corrupted_small_file_triggers_redownload(tmp_path: Path):
    """An existing file < MIN_EXPECTED_BYTES must be detected as corrupt and re-downloaded."""
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()
    corrupt_file = weights_dir / "yolo11n-seg.pt"
    # Write only 100 bytes (suspiciously small/corrupted)
    corrupt_file.write_bytes(b"\x00" * 100)

    fake_data = b"X" * 1_500_000
    mock_resp = MagicMock()
    mock_resp.headers.get.return_value = str(len(fake_data))
    mock_resp.read.side_effect = [fake_data, b""]
    mock_resp.__enter__.return_value = mock_resp

    with patch("scripts.download_weights.get_settings") as mock_settings:
        mock_settings.return_value.DEFAULT_MODEL_NAME = "yolo11n-seg.pt"
        mock_settings.return_value.WEIGHTS_DIR = weights_dir

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            success = download_weights(assume_yes=True, force=False)
            assert success is True
            mock_urlopen.assert_called_once()
            assert corrupt_file.stat().st_size == len(fake_data)


def test_transient_network_timeout_retries_and_succeeds(tmp_path: Path):
    """Transient timeouts trigger exponential backoff retries and succeed on subsequent attempt."""
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()

    fake_data = b"Y" * 1_200_000
    mock_success_resp = MagicMock()
    mock_success_resp.headers.get.return_value = str(len(fake_data))
    mock_success_resp.read.side_effect = [fake_data, b""]
    mock_success_resp.__enter__.return_value = mock_success_resp

    # Simulate timeout on attempt 1, success on attempt 2
    timeout_err = urllib.error.URLError("[Errno 110] Connection timed out")

    with patch("scripts.download_weights.get_settings") as mock_settings:
        mock_settings.return_value.DEFAULT_MODEL_NAME = "yolo11n-seg.pt"
        mock_settings.return_value.WEIGHTS_DIR = weights_dir

        with (
            patch("urllib.request.urlopen", side_effect=[timeout_err, mock_success_resp]) as mock_urlopen,
            patch("time.sleep") as mock_sleep,
        ):
            success = download_weights(assume_yes=True, max_retries=2, timeout_seconds=15.0)
            assert success is True
            assert mock_urlopen.call_count == 2
            mock_sleep.assert_called_once_with(1.0)  # 2.0 ** 0 = 1.0s backoff
            dest = weights_dir / "yolo11n-seg.pt"
            assert dest.is_file()
            assert dest.stat().st_size == len(fake_data)
            # Ensure no leftover .part file
            assert not (weights_dir / "yolo11n-seg.pt.part").exists()


def test_transient_http_503_retries_and_succeeds(tmp_path: Path):
    """Transient HTTP 503 Service Unavailable triggers retry with backoff and succeeds."""
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()

    fake_data = b"S" * 1_300_000
    mock_success_resp = MagicMock()
    mock_success_resp.headers.get.return_value = str(len(fake_data))
    mock_success_resp.read.side_effect = [fake_data, b""]
    mock_success_resp.__enter__.return_value = mock_success_resp

    http_503_err = urllib.error.HTTPError(
        url="http://test.url", code=503, msg="Service Unavailable", hdrs={}, fp=None
    )

    with patch("scripts.download_weights.get_settings") as mock_settings:
        mock_settings.return_value.DEFAULT_MODEL_NAME = "yolo11n-seg.pt"
        mock_settings.return_value.WEIGHTS_DIR = weights_dir

        with (
            patch("urllib.request.urlopen", side_effect=[http_503_err, mock_success_resp]) as mock_urlopen,
            patch("time.sleep") as mock_sleep,
        ):
            success = download_weights(assume_yes=True, max_retries=2)
            assert success is True
            assert mock_urlopen.call_count == 2
            mock_sleep.assert_called_once_with(1.0)
            dest = weights_dir / "yolo11n-seg.pt"
            assert dest.is_file()
            assert dest.stat().st_size == len(fake_data)


def test_transient_http_429_retries_and_succeeds(tmp_path: Path):
    """Transient HTTP 429 Too Many Requests triggers retry with backoff and succeeds."""
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()

    fake_data = b"R" * 1_300_000
    mock_success_resp = MagicMock()
    mock_success_resp.headers.get.return_value = str(len(fake_data))
    mock_success_resp.read.side_effect = [fake_data, b""]
    mock_success_resp.__enter__.return_value = mock_success_resp

    http_429_err = urllib.error.HTTPError(
        url="http://test.url", code=429, msg="Too Many Requests", hdrs={}, fp=None
    )

    with patch("scripts.download_weights.get_settings") as mock_settings:
        mock_settings.return_value.DEFAULT_MODEL_NAME = "yolo11n-seg.pt"
        mock_settings.return_value.WEIGHTS_DIR = weights_dir

        with (
            patch("urllib.request.urlopen", side_effect=[http_429_err, mock_success_resp]) as mock_urlopen,
            patch("time.sleep") as mock_sleep,
        ):
            success = download_weights(assume_yes=True, max_retries=2)
            assert success is True
            assert mock_urlopen.call_count == 2
            mock_sleep.assert_called_once_with(1.0)


def test_permanent_http_404_aborts_immediately_without_retry(tmp_path: Path):
    """Permanent HTTP 404 Not Found aborts immediately on the first attempt without retrying."""
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()

    http_404_err = urllib.error.HTTPError(
        url="http://test.url", code=404, msg="Not Found", hdrs={}, fp=None
    )

    with patch("scripts.download_weights.get_settings") as mock_settings:
        mock_settings.return_value.DEFAULT_MODEL_NAME = "nonexistent_model.pt"
        mock_settings.return_value.WEIGHTS_DIR = weights_dir

        with (
            patch("urllib.request.urlopen", side_effect=http_404_err) as mock_urlopen,
            patch("time.sleep") as mock_sleep,
        ):
            success = download_weights(assume_yes=True, max_retries=3)
            assert success is False
            # Crucial: Must NOT retry 404
            assert mock_urlopen.call_count == 1
            mock_sleep.assert_not_called()
            assert not (weights_dir / "nonexistent_model.pt").exists()


def test_permanent_http_403_aborts_immediately_without_retry(tmp_path: Path):
    """Permanent HTTP 403 Forbidden aborts immediately on the first attempt without retrying."""
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()

    http_403_err = urllib.error.HTTPError(
        url="http://test.url", code=403, msg="Forbidden", hdrs={}, fp=None
    )

    with patch("scripts.download_weights.get_settings") as mock_settings:
        mock_settings.return_value.DEFAULT_MODEL_NAME = "restricted_model.pt"
        mock_settings.return_value.WEIGHTS_DIR = weights_dir

        with (
            patch("urllib.request.urlopen", side_effect=http_403_err) as mock_urlopen,
            patch("time.sleep") as mock_sleep,
        ):
            success = download_weights(assume_yes=True, max_retries=3)
            assert success is False
            assert mock_urlopen.call_count == 1
            mock_sleep.assert_not_called()


def test_forced_replacement_failure_preserves_existing_valid_file(tmp_path: Path):
    """When force=True and download fails, an existing valid model file must never be deleted."""
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()
    existing_valid_file = weights_dir / "yolo11n-seg.pt"
    original_bytes = b"ORIGINAL_VALID_WEIGHTS" + b"\x00" * 2_000_000
    existing_valid_file.write_bytes(original_bytes)

    timeout_err = TimeoutError("Connection dropped during forced replacement")

    with patch("scripts.download_weights.get_settings") as mock_settings:
        mock_settings.return_value.DEFAULT_MODEL_NAME = "yolo11n-seg.pt"
        mock_settings.return_value.WEIGHTS_DIR = weights_dir

        with (
            patch("urllib.request.urlopen", side_effect=timeout_err),
            patch("time.sleep"),
        ):
            success = download_weights(assume_yes=True, force=True, max_retries=2)
            assert success is False
            # Crucial requirement: Existing valid file MUST NOT be deleted
            assert existing_valid_file.is_file()
            assert existing_valid_file.read_bytes() == original_bytes
            assert not (weights_dir / "yolo11n-seg.pt.part").exists()


def test_persistent_failure_stops_at_retry_limit_and_cleans_up(tmp_path: Path):
    """Persistent network failures exhaust max_retries, clean up, and return False."""
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()

    timeout_err = TimeoutError("The read operation timed out")

    with patch("scripts.download_weights.get_settings") as mock_settings:
        mock_settings.return_value.DEFAULT_MODEL_NAME = "yolo11n-seg.pt"
        mock_settings.return_value.WEIGHTS_DIR = weights_dir

        with (
            patch("urllib.request.urlopen", side_effect=timeout_err) as mock_urlopen,
            patch("time.sleep") as mock_sleep,
        ):
            success = download_weights(assume_yes=True, max_retries=3, timeout_seconds=10.0)
            assert success is False
            # 1 initial + 3 retries = 4 attempts
            assert mock_urlopen.call_count == 4
            assert mock_sleep.call_count == 3
            # Ensure target file and .part file are NOT left on disk
            assert not (weights_dir / "yolo11n-seg.pt").exists()
            assert not (weights_dir / "yolo11n-seg.pt.part").exists()


def test_truncated_download_retries_and_rejects(tmp_path: Path):
    """Downloads smaller than MIN_EXPECTED_BYTES are retried as transient payload errors and rejected if persistent."""
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()

    # Server sends only 500 KB instead of expected ~6MB across all attempts
    truncated_data = b"Z" * 500_000
    mock_resp = MagicMock()
    mock_resp.headers.get.return_value = str(len(truncated_data))
    mock_resp.read.side_effect = [truncated_data, b"", truncated_data, b"", truncated_data, b""]
    mock_resp.__enter__.return_value = mock_resp

    with patch("scripts.download_weights.get_settings") as mock_settings:
        mock_settings.return_value.DEFAULT_MODEL_NAME = "yolo11n-seg.pt"
        mock_settings.return_value.WEIGHTS_DIR = weights_dir

        with (
            patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen,
            patch("time.sleep") as mock_sleep,
        ):
            success = download_weights(assume_yes=True, max_retries=2)
            assert success is False
            # Initial attempt + 2 retries = 3 attempts
            assert mock_urlopen.call_count == 3
            assert mock_sleep.call_count == 2
            assert not (weights_dir / "yolo11n-seg.pt").exists()
            assert not (weights_dir / "yolo11n-seg.pt.part").exists()
