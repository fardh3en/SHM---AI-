"""Unit tests for PDF export endpoint and report generation in SHM-AI."""

from pathlib import Path
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.config import get_settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def settings():
    return get_settings()


def test_get_report_pdf_404_when_missing(client: TestClient) -> None:
    """Requesting a nonexistent report PDF should return 404."""
    response = client.get("/api/v1/reports/nonexistent_report_12345/pdf")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_report_pdf_serves_existing_pdf(client: TestClient, settings) -> None:
    """When a PDF exists in reports dir, /api/v1/reports/{filename}/pdf should serve it."""
    # Create sample PDF in reports dir
    reports_dir = Path(settings.REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)
    test_pdf = reports_dir / "test_sample_report_export.pdf"
    test_pdf.write_bytes(b"%PDF-1.4\n%test PDF content\n%%EOF")

    try:
        response = client.get("/api/v1/reports/test_sample_report_export/pdf")
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "test_sample_report_export.pdf" in response.headers.get("content-disposition", "")
    finally:
        if test_pdf.is_file():
            test_pdf.unlink()


def test_get_report_pdf_generates_dynamically_from_html(client: TestClient, settings) -> None:
    """When HTML exists but PDF does not yet exist, /pdf dynamically compiles it."""
    reports_dir = Path(settings.REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)
    test_html = reports_dir / "test_dynamic_report_export.html"
    test_html.write_text(
        "<!DOCTYPE html><html><head><title>Test Report</title></head>"
        "<body><h1>SHM-AI Engineering Report</h1><p>Structural health assessment.</p></body></html>",
        encoding="utf-8",
    )
    test_pdf = reports_dir / "test_dynamic_report_export.pdf"
    if test_pdf.is_file():
        test_pdf.unlink()

    try:
        response = client.get("/api/v1/reports/test_dynamic_report_export/pdf")
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")
        assert "attachment" in response.headers.get("content-disposition", "")
        # Verify the PDF file was saved to disk alongside the HTML
        assert test_pdf.is_file()
    finally:
        if test_html.is_file():
            test_html.unlink()
        if test_pdf.is_file():
            test_pdf.unlink()
