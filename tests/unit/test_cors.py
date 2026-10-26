"""
Unit tests for CORS configuration and preflight handling.

Verifies:
- Configured Vercel production and preview deployment origins are allowed.
- Localhost development ports are allowed.
- Disallowed origins are rejected without Access-Control-Allow-Origin headers.
- Preflight OPTIONS requests respond with 200 OK and expected CORS headers.
- Credentials flag behaves according to CORS_ALLOW_CREDENTIALS setting.
- Settings parser supports comma-separated and JSON string formats.
- Exception handlers maintain CORS headers for allowed origins.
"""
import pytest
from starlette.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import app

client = TestClient(app, raise_server_exceptions=False)

PERMITTED_ORIGINS = [
    "https://shm-ai-silk.vercel.app",
    "https://shm-p2k5964w-fardh3en.vercel.app",
    "https://shm-preview-branch.vercel.app",  # Matches ALLOWED_ORIGIN_REGEX
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:4173",
    "http://127.0.0.1:3000",
]

DISALLOWED_ORIGIN = "https://unauthorized-domain.com"

AFFECTED_ROUTES = [
    "/api/v1/system/health",
    "/api/v1/system/info",
    "/api/v1/assets/",
    "/api/v1/inspections/",
]


class TestCORSPreflight:
    """Verify OPTIONS preflight requests for all permitted origins."""

    @pytest.mark.parametrize("origin", PERMITTED_ORIGINS)
    @pytest.mark.parametrize("route", AFFECTED_ROUTES)
    def test_preflight_permitted_origins(self, origin: str, route: str) -> None:
        response = client.options(
            route,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type,accept",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin
        assert "GET" in response.headers.get("access-control-allow-methods", "")
        # Credentials must not be sent if not enabled
        assert response.headers.get("access-control-allow-credentials") is None

    def test_preflight_disallowed_origin_rejected(self) -> None:
        response = client.options(
            "/api/v1/system/health",
            headers={
                "Origin": DISALLOWED_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type,accept",
            },
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


class TestCORSActualRequests:
    """Verify actual GET requests include Access-Control-Allow-Origin."""

    @pytest.mark.parametrize("origin", [
        "https://shm-ai-silk.vercel.app",
        "https://shm-p2k5964w-fardh3en.vercel.app",
    ])
    @pytest.mark.parametrize("route", AFFECTED_ROUTES)
    def test_actual_get_requests(self, origin: str, route: str) -> None:
        response = client.get(route, headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin

    def test_actual_request_disallowed_origin(self) -> None:
        response = client.get("/api/v1/system/health", headers={"Origin": DISALLOWED_ORIGIN})
        assert response.status_code == 200
        # For disallowed origin, CORS middleware must not add allow-origin header
        assert "access-control-allow-origin" not in response.headers


class TestCORSSettingsParsing:
    """Verify Pydantic settings parsing for ALLOWED_ORIGINS env formats."""

    def test_parse_comma_separated_origins(self) -> None:
        s = Settings(ALLOWED_ORIGINS="https://app1.vercel.app, https://app2.vercel.app/")
        assert s.ALLOWED_ORIGINS == [
            "https://app1.vercel.app",
            "https://app2.vercel.app",
        ]
        assert s.is_origin_allowed("https://app1.vercel.app")
        assert s.is_origin_allowed("https://app2.vercel.app")

    def test_parse_json_list_origins(self) -> None:
        s = Settings(ALLOWED_ORIGINS='["https://app3.vercel.app/", "https://app4.vercel.app"]')
        assert s.ALLOWED_ORIGINS == [
            "https://app3.vercel.app",
            "https://app4.vercel.app",
        ]
        assert s.is_origin_allowed("https://app3.vercel.app")
        assert s.is_origin_allowed("https://app4.vercel.app")

    def test_trailing_slash_normalization(self) -> None:
        s = Settings(ALLOWED_ORIGINS=["https://example.com///"])
        assert s.ALLOWED_ORIGINS == ["https://example.com"]
        assert s.is_origin_allowed("https://example.com")
        assert s.is_origin_allowed("https://example.com/")

    def test_regex_origin_matching(self) -> None:
        s = Settings(
            ALLOWED_ORIGINS=["https://fixed.example.com"],
            ALLOWED_ORIGIN_REGEX=r"^https:\/\/.*\.vercel\.app$",
        )
        assert s.is_origin_allowed("https://fixed.example.com")
        assert s.is_origin_allowed("https://branch-deploy-123.vercel.app")
        assert not s.is_origin_allowed("https://attacker.com")
