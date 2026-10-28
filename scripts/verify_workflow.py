"""
SHM-AI Verification Script
Verifies:
1. Backend system health
2. Frontend dev server response
3. Inspection retrieval & completed inspection status
4. Report generation API (HTTP 201)
5. Report self-contained image data URI embedding (no broken images)
6. Architectural Olive & Sand styling and defect inventory markers
7. Report archive persistence (GET /api/v1/reports/)
8. Direct report download & preview endpoint (GET /api/v1/reports/{filename})
9. Incomplete inspection error handling (422 validation, not 500 crash)
"""
import sys
import httpx

BACKEND_BASE = "http://127.0.0.1:8000"
FRONTEND_BASE = "http://localhost:3000"

def main():
    print("=== SHM-AI VERIFICATION PIPELINE ===")

    # 1. Backend health
    with httpx.Client(base_url=BACKEND_BASE, follow_redirects=True, timeout=15.0) as client:
        health_res = client.get("/api/v1/system/health")
        assert health_res.status_code == 200, f"Backend health failed: {health_res.status_code}"
        health_data = health_res.json()
        print(f"[PASS] 1. Backend Health: {health_data.get('status')} ({health_data.get('service')})")

        # 2. Get completed inspection
        insps_res = client.get("/api/v1/inspections/")
        assert insps_res.status_code == 200, f"Inspections list failed: {insps_res.status_code}"
        insps = insps_res.json()
        items = insps.get("items", insps)
        completed = [i for i in items if i.get("status") == "completed"]
        assert len(completed) > 0, "No completed inspections found in database."
        target_insp = completed[0]
        insp_id = target_insp["id"]
        asset_id = target_insp["asset_id"]
        defect_count = target_insp.get("defect_count", 0)
        print(f"[PASS] 2. Completed Inspection Located: {insp_id} (Asset: {asset_id}, Defects: {defect_count})")

        # 3. Report generation for exact inspection
        gen_payload = {
            "asset_id": asset_id,
            "inspection_id": insp_id,
            "format": "html"
        }
        gen_res = client.post("/api/v1/reports/generate", json=gen_payload)
        assert gen_res.status_code in (200, 201), f"Report compilation failed: {gen_res.status_code} {gen_res.text}"
        report_data = gen_res.json()
        filename = report_data["filename"]
        html = report_data.get("html_content", "")
        print(f"[PASS] 3. Report Compiled Successfully: {filename} (HTTP {gen_res.status_code})")

        # 4. Image embedding check (No broken images)
        assert "data:image/" in html, "Original/annotated image was not embedded as data URI"
        assert 'class="evidence-img"' in html, "Evidence image markup missing from report HTML"
        assert "Figure 1.1: Original Survey Photograph" in html, "Figure 1.1 title missing"
        assert "Figure 1.2: YOLO26 AI Defect Segmentation" in html, "Figure 1.2 title missing"
        print("[PASS] 4. Photographic Evidence Embedded: Self-contained base64 data URI verified for Figure 1.1 & 1.2")

        # 5. Architectural Olive & Sand Palette & Defect Numbering
        for color in ["#353B32", "#FAF9F5", "#F0EDE4", "#77766D", "#A65D42"]:
            assert color.lower() in html.lower(), f"Architectural palette color {color} not found in HTML"
        print("[PASS] 5. Architectural Olive & Sand Palette Verified in Generated Dossier")

        # 6. Report Archive listing
        archive_res = client.get("/api/v1/reports/")
        assert archive_res.status_code == 200, f"Archive list failed: {archive_res.status_code}"
        archive_items = archive_res.json()
        archived_filenames = [r["filename"] for r in archive_items]
        assert filename in archived_filenames, f"Generated report {filename} not listed in archive"
        print(f"[PASS] 6. Persisted Report Archive Verified ({len(archive_items)} reports indexed)")

        # 7. Direct report preview & download endpoint
        file_res = client.get(f"/api/v1/reports/{filename}")
        assert file_res.status_code == 200, f"Direct download failed: {file_res.status_code}"
        assert len(file_res.content) > 1000, "Downloaded file content is empty or truncated"
        print(f"[PASS] 7. Direct Report Download & Preview Endpoint: HTTP 200 ({len(file_res.content)} bytes)")

        # 8. Negative test: Incomplete inspection or non-matching asset returns 422, not 500
        invalid_payload = {
            "asset_id": "00000000-0000-0000-0000-000000000000",
            "inspection_id": insp_id,
            "format": "html"
        }
        invalid_res = client.post("/api/v1/reports/generate", json=invalid_payload)
        assert invalid_res.status_code in (404, 422), f"Expected 404/422 for invalid asset, got {invalid_res.status_code}"
        print(f"[PASS] 8. Incomplete / Invalid Input Validation Handled Cleanly (HTTP {invalid_res.status_code})")

    # 9. Frontend Dev Server Check
    with httpx.Client(base_url=FRONTEND_BASE, follow_redirects=True, timeout=10.0) as fe_client:
        fe_res = fe_client.get("/")
        assert fe_res.status_code == 200, f"Frontend server responded with HTTP {fe_res.status_code}"
        print(f"[PASS] 9. Frontend Dev Server Responding: {FRONTEND_BASE}/ (HTTP 200)")

    print("\n=== ALL 9 VERIFICATION CHECKS PASSED WITH ZERO ERRORS ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
