"""Test core backend endpoints."""
import json
import urllib.request

endpoints = [
    ("/", "Root"),
    ("/api/v1/system/health", "Health Probe"),
    ("/api/v1/system/info", "Platform Info"),
    ("/api/v1/docs", "Swagger UI"),
    ("/api/v1/openapi.json", "OpenAPI Schema"),
    ("/api/v1/assets", "Assets List"),
    ("/api/v1/inspections", "Inspections List"),
    ("/api/v1/reports", "Reports List"),
]

print("=== TESTING BACKEND API ENDPOINTS ===")
all_pass = True
for path, desc in endpoints:
    url = f"http://127.0.0.1:8000{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HealthCheck/1.0"})
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            ctype = resp.headers.get("content-type", "").split(";")[0]
            data = resp.read()
            print(f"[PASS] {status} | {desc:<16} | {path:<24} | {len(data)} bytes ({ctype})")
    except Exception as e:
        print(f"[FAIL] {desc:<16} | {path:<24} -> {e}")
        all_pass = False

if all_pass:
    print("\nALL ENDPOINTS RESPONDED WITH HTTP 200 OK!")
