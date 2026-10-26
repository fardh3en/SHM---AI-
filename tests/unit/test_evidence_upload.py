"""
Unit tests for the evidence upload endpoint and end-to-end upload-to-inference handoff.

Verifies:
1. Valid image upload receives actual image bytes, persists safely, and returns
   /uploads/evidence/... path.
2. Content verification: saved file on server disk matches uploaded bytes byte-for-byte.
3. Uploading with asset_id automatically links the evidence in the AssetEvidence repository.
4. Uploading invalid extensions (e.g. .exe, .txt) returns HTTP 400.
5. Uploading empty (0-byte) files returns HTTP 400.
6. Path traversal attempts are sanitized and strictly confined to UPLOAD_DIR/evidence.
7. Full handoff: Uploaded image -> Inspection created with input_path ->
   Vision pipeline execution succeeds.
"""
import io
from unittest.mock import patch

from PIL import Image
from starlette.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import app
from backend.app.models.detection import DefectType
from vision.detectors.base import IDetector, RawDetection
from vision.pipeline.cv_pipeline import CVInferencePipeline

client = TestClient(app, raise_server_exceptions=False)


def _generate_test_image(format_str: str = "JPEG", size=(64, 64), color="blue") -> bytes:
    """Generate in-memory test image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format_str)
    return buf.getvalue()


class MockDetector(IDetector):
    """Test detector returning one defect without loading external model weights."""
    @property
    def model_name(self) -> str:
        return "mock-yolo.pt"

    @property
    def device(self) -> str:
        return "cpu"

    def predict(self, image, confidence_threshold=None):
        return [
            RawDetection(
                defect_type=DefectType.CRACK,
                confidence=0.92,
                bbox=[5.0, 5.0, 30.0, 50.0],
                mask=None,
            )
        ]


def test_upload_valid_jpeg():
    """Verify JPEG upload persists bytes to disk and returns 201."""
    jpeg_bytes = _generate_test_image("JPEG")
    files = {"file": ("crack_sample.jpeg", jpeg_bytes, "image/jpeg")}

    response = client.post("/api/v1/evidence/upload", files=files)
    assert response.status_code == 201, response.text

    data = response.json()
    assert data["file_path"].startswith("/uploads/evidence/")
    assert data["filename"].endswith(".jpeg")
    assert data["size_bytes"] == len(jpeg_bytes)
    assert data["content_type"] == "image/jpeg"

    # Verify byte-for-byte on disk
    settings = get_settings()
    disk_path = settings.UPLOAD_DIR / "evidence" / data["filename"]
    assert disk_path.is_file()
    assert disk_path.read_bytes() == jpeg_bytes


def test_upload_valid_png():
    """Verify PNG upload succeeds."""
    png_bytes = _generate_test_image("PNG")
    files = {"file": ("spall_view.png", png_bytes, "image/png")}

    response = client.post("/api/v1/evidence/upload", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["file_path"].startswith("/uploads/evidence/")
    assert data["filename"].endswith(".png")


def test_upload_with_asset_id():
    """Verify uploading with asset_id registers an AssetEvidence record."""
    # 1. Create asset via API
    asset_res = client.post(
        "/api/v1/assets/",
        json={"name": "Upload Pier Asset", "asset_type": "bridge"},
    )
    assert asset_res.status_code == 201
    asset_id = asset_res.json()["id"]

    # 2. Upload with asset_id
    jpeg_bytes = _generate_test_image("JPEG", color="red")
    files = {"file": ("pier_crack.jpg", jpeg_bytes, "image/jpeg")}
    data_form = {"asset_id": asset_id, "caption": "East Substructure Crack"}

    upload_res = client.post("/api/v1/evidence/upload", files=files, data=data_form)
    assert upload_res.status_code == 201
    upload_data = upload_res.json()
    assert upload_data["asset_id"] == asset_id
    assert upload_data["id"] is not None

    # 3. Verify asset's evidence list reflects this image
    list_res = client.get(f"/api/v1/assets/{asset_id}/evidence")
    assert list_res.status_code == 200
    evidence_list = list_res.json()
    assert any(e["file_path"] == upload_data["file_path"] for e in evidence_list)


def test_upload_invalid_extension():
    """Verify non-image files are rejected with HTTP 400."""
    files = {"file": ("malicious.exe", b"MZexecutabledata", "application/octet-stream")}
    response = client.post("/api/v1/evidence/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_upload_empty_file():
    """Verify empty 0-byte file is rejected with HTTP 400."""
    files = {"file": ("empty.jpg", b"", "image/jpeg")}
    response = client.post("/api/v1/evidence/upload", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


def test_upload_path_traversal_sanitization():
    """Verify path traversal characters are sanitized and kept inside UPLOAD_DIR/evidence."""
    jpeg_bytes = _generate_test_image("JPEG")
    files = {"file": ("../../etc/passwd.jpg", jpeg_bytes, "image/jpeg")}

    response = client.post("/api/v1/evidence/upload", files=files)
    assert response.status_code == 201
    data = response.json()

    # The resulting filename should NOT contain .. or slashes
    assert ".." not in data["filename"]
    assert "/" not in data["filename"]
    assert "\\" not in data["filename"]

    # File must be strictly inside UPLOAD_DIR/evidence
    settings = get_settings()
    dest = (settings.UPLOAD_DIR / "evidence" / data["filename"]).resolve()
    assert dest.is_relative_to((settings.UPLOAD_DIR / "evidence").resolve())
    assert dest.is_file()


def test_end_to_end_upload_to_inspection_inference():
    """
    Test full end-to-end handoff:
    1. Upload real image bytes -> /uploads/evidence/...
    2. Create inspection with input_path = uploaded file_path
    3. Trigger run inspection -> pipeline runs on the uploaded bytes
    4. Verify status is COMPLETED and detections are persisted.
    """
    # 1. Create Asset
    asset_res = client.post(
        "/api/v1/assets/",
        json={"name": "End-to-End Test Bridge", "asset_type": "bridge"},
    )
    assert asset_res.status_code == 201
    asset_id = asset_res.json()["id"]

    # 2. Upload image file
    test_bytes = _generate_test_image("JPEG", size=(128, 128), color="gray")
    files = {"file": ("crack_image_sg.jpeg", test_bytes, "image/jpeg")}
    upload_res = client.post(
        "/api/v1/evidence/upload",
        files=files,
        data={"asset_id": asset_id, "caption": "Field Crack"},
    )
    assert upload_res.status_code == 201
    file_path = upload_res.json()["file_path"]

    # 3. Create inspection record referencing the uploaded file
    insp_res = client.post(
        "/api/v1/inspections/",
        json={
            "asset_id": asset_id,
            "source": "image",
            "input_path": file_path,
            "notes": "Field photography inspection",
        },
    )
    assert insp_res.status_code == 201
    insp_id = insp_res.json()["id"]

    # 4. Run vision pipeline with mock pipeline
    pipeline = CVInferencePipeline(
        detector=MockDetector(),
        slice_height=640,
        slice_width=640,
        slice_overlap_ratio=0.2,
    )

    with patch("backend.app.dependencies.get_cv_pipeline", return_value=pipeline):
        run_res = client.post(f"/api/v1/inspections/{insp_id}/run")
        assert run_res.status_code == 200, run_res.text
        run_data = run_res.json()
        assert run_data["status"] == "completed"
        assert run_data["defect_count"] == 1
        assert run_data["health_score"] is not None

    # 5. Check detections endpoint
    det_res = client.get(f"/api/v1/inspections/{insp_id}/detections")
    assert det_res.status_code == 200
    dets = det_res.json()
    assert len(dets) == 1
    assert dets[0]["defect_type"] == "crack"
    assert dets[0]["source_image"] == file_path
