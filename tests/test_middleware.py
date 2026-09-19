from __future__ import annotations

from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_control_center.config import Settings


def _make_app(settings: Settings) -> FastAPI:
    from llm_control_center.app import create_app

    return create_app(settings)


class TestCORSHeaders:
    def test_cors_headers_present(self, client: TestClient) -> None:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://testserver",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://testserver"
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_preflight_returns_allowed_methods(self, client: TestClient) -> None:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://testserver",
                "Access-Control-Request-Method": "POST",
            },
        )
        allow_methods = response.headers.get("access-control-allow-methods", "")
        assert "GET" in allow_methods
        assert "POST" in allow_methods
        assert "DELETE" in allow_methods

    def test_cors_preflight_returns_allowed_headers(self, client: TestClient) -> None:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://testserver",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        allow_headers = response.headers.get("access-control-allow-headers", "")
        assert "authorization" in allow_headers.lower()
        assert "content-type" in allow_headers.lower()
        assert "x-admin-token" in allow_headers.lower()


class TestSecurityHeaders:
    def test_nosniff_header(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_frame_deny_header(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_xss_protection_header(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers["X-XSS-Protection"] == "1; mode=block"


class TestRequestID:
    def test_request_id_returned_in_response(self, client: TestClient) -> None:
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0

    def test_custom_request_id_preserved(self, client: TestClient) -> None:
        custom_id = "my-custom-id-12345"
        response = client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id


class TestDocsProtection:
    @contextmanager
    def _make_protected_client(self, tmp_path) -> TestClient:
        settings = Settings(
            admin_token="secret-token",
            api_key_pepper="test-pepper",
            database_url=f"sqlite:///{tmp_path}/test.sqlite3",
            model_routes={"default-chat": {"provider": "mock", "provider_model": "mock-smart"}},
            default_model_alias="default-chat",
            openai_compatible_api_key="",
            rate_limit_admin=0,
            rate_limit_chat=0,
            rate_limit_models=0,
            max_request_size_mb=1,
            docs_protected=True,
            cors_origins=["http://testserver"],
        )
        app = _make_app(settings)
        with TestClient(app) as client:
            yield client

    def test_docs_returns_403_without_token(self, tmp_path) -> None:
        with self._make_protected_client(tmp_path) as client:
            response = client.get("/docs")
        assert response.status_code == 403
        assert response.json()["detail"] == "Forbidden"

    def test_docs_returns_403_with_wrong_token(self, tmp_path) -> None:
        with self._make_protected_client(tmp_path) as client:
            response = client.get("/docs", headers={"X-Admin-Token": "wrong-token"})
        assert response.status_code == 403

    def test_docs_returns_200_with_correct_token(self, tmp_path) -> None:
        with self._make_protected_client(tmp_path) as client:
            response = client.get("/docs", headers={"X-Admin-Token": "secret-token"})
        assert response.status_code == 200

    def test_redoc_returns_403_without_token(self, tmp_path) -> None:
        with self._make_protected_client(tmp_path) as client:
            response = client.get("/redoc")
        assert response.status_code == 403

    def test_redoc_returns_200_with_correct_token(self, tmp_path) -> None:
        with self._make_protected_client(tmp_path) as client:
            response = client.get("/redoc", headers={"X-Admin-Token": "secret-token"})
        assert response.status_code == 200

    def test_openapi_json_returns_403_without_token(self, tmp_path) -> None:
        with self._make_protected_client(tmp_path) as client:
            response = client.get("/openapi.json")
        assert response.status_code == 403

    def test_openapi_json_returns_200_with_correct_token(self, tmp_path) -> None:
        with self._make_protected_client(tmp_path) as client:
            response = client.get("/openapi.json", headers={"X-Admin-Token": "secret-token"})
        assert response.status_code == 200

    def test_health_endpoint_not_protected(self, tmp_path) -> None:
        with self._make_protected_client(tmp_path) as client:
            response = client.get("/health")
        assert response.status_code == 200
