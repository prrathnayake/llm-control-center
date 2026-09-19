from __future__ import annotations

import tempfile
from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient

from llm_control_center.app import create_app
from llm_control_center.config import Settings


def _make_limited_app(
    *,
    admin_limit: int = 5,
    chat_limit: int = 3,
    models_limit: int = 4,
    max_request_size_mb: int = 1,
    trust_proxy_headers: bool = False,
) -> tuple[Settings, TestClient]:
    """Create an app with tight rate limits for testing."""
    tmp_dir = tempfile.mkdtemp()
    settings = Settings(
        admin_token="test-admin",
        api_key_pepper="test-pepper",
        database_url=f"sqlite:///{tmp_dir}/test.sqlite3",
        model_routes={"default-chat": {"provider": "mock", "provider_model": "mock-smart"}},
        default_model_alias="default-chat",
        openai_compatible_api_key="",
        rate_limit_admin=admin_limit,
        rate_limit_chat=chat_limit,
        rate_limit_models=models_limit,
        max_request_size_mb=max_request_size_mb,
        trust_proxy_headers=trust_proxy_headers,
    )
    app = create_app(settings)
    return settings, TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def limited_client_factory() -> Generator[Callable[..., tuple[Settings, TestClient]], None, None]:
    clients: list[TestClient] = []

    def factory(**kwargs) -> tuple[Settings, TestClient]:
        settings, client = _make_limited_app(**kwargs)
        client.__enter__()
        clients.append(client)
        return settings, client

    try:
        yield factory
    finally:
        for client in reversed(clients):
            client.__exit__(None, None, None)


def _create_project_and_key(client: TestClient, admin_headers: dict) -> str:
    resp = client.post(
        "/admin/projects",
        headers=admin_headers,
        json={"name": "rl-test", "description": "Rate limit test project"},
    )
    assert resp.status_code == 200
    project_id = resp.json()["id"]
    key_resp = client.post(
        f"/admin/projects/{project_id}/api-keys",
        headers=admin_headers,
        json={"name": "rl-key", "scopes": ["chat:write", "models:read"]},
    )
    assert key_resp.status_code == 200
    return key_resp.json()["api_key"]


class TestRateLimitHeaders:
    def test_rate_limit_headers_on_health(self, limited_client_factory):
        settings, client = limited_client_factory()
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == "4"

    def test_rate_limit_headers_on_admin(self, limited_client_factory):
        settings, client = limited_client_factory(admin_limit=10)
        admin_headers = {"X-Admin-Token": "test-admin"}
        resp = client.get("/admin/usage", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "10"

    def test_rate_limit_headers_decrement(self, limited_client_factory):
        settings, client = limited_client_factory(models_limit=3)
        headers = {"X-Admin-Token": "test-admin"}
        # Create project/key for model access
        api_key = _create_project_and_key(client, headers)
        model_headers = {"Authorization": f"Bearer {api_key}"}

        resp1 = client.get("/v1/models", headers=model_headers)
        assert resp1.headers["X-RateLimit-Remaining"] == "2"

        resp2 = client.get("/v1/models", headers=model_headers)
        assert resp2.headers["X-RateLimit-Remaining"] == "1"


class TestRateLimitExceeded:
    def test_admin_rate_limit_exceeded(self, limited_client_factory):
        settings, client = limited_client_factory(admin_limit=3)
        admin_headers = {"X-Admin-Token": "test-admin"}

        for _ in range(3):
            resp = client.get("/admin/usage", headers=admin_headers)
            assert resp.status_code == 200

        resp = client.get("/admin/usage", headers=admin_headers)
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Rate limit exceeded. Try again later."
        assert "Retry-After" in resp.headers
        assert "X-RateLimit-Limit" in resp.headers

    def test_chat_rate_limit_exceeded(self, limited_client_factory):
        settings, client = limited_client_factory(chat_limit=2)
        admin_headers = {"X-Admin-Token": "test-admin"}
        api_key = _create_project_and_key(client, admin_headers)
        chat_headers = {"Authorization": f"Bearer {api_key}"}

        for _ in range(2):
            resp = client.post(
                "/v1/chat/completions",
                headers=chat_headers,
                json={
                    "model": "default-chat",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
            assert resp.status_code == 200

        resp = client.post(
            "/v1/chat/completions",
            headers=chat_headers,
            json={
                "model": "default-chat",
                "messages": [{"role": "user", "content": "Hi again"}],
            },
        )
        assert resp.status_code == 429

    def test_models_rate_limit_exceeded(self, limited_client_factory):
        settings, client = limited_client_factory(models_limit=2)
        admin_headers = {"X-Admin-Token": "test-admin"}
        api_key = _create_project_and_key(client, admin_headers)
        model_headers = {"Authorization": f"Bearer {api_key}"}

        for _ in range(2):
            resp = client.get("/v1/models", headers=model_headers)
            assert resp.status_code == 200

        resp = client.get("/v1/models", headers=model_headers)
        assert resp.status_code == 429


class TestForwardedForRateLimit:
    def test_admin_rate_limit_uses_forwarded_for(self, limited_client_factory):
        settings, client = limited_client_factory(
            admin_limit=2, trust_proxy_headers=True
        )
        forwarded_headers = {"X-Admin-Token": "test-admin", "X-Forwarded-For": "203.0.113.9"}

        for _ in range(2):
            resp = client.get("/admin/usage", headers=forwarded_headers)
            assert resp.status_code == 200

        resp = client.get("/admin/usage", headers=forwarded_headers)
        assert resp.status_code == 429

    def test_models_and_health_share_bucket(self, limited_client_factory):
        settings, client = limited_client_factory(
            models_limit=2, trust_proxy_headers=True
        )
        forwarded_headers = {"X-Forwarded-For": "198.51.100.7"}
        # Two requests from different paths draw from the shared models bucket
        # (use /health twice since it's unauthenticated; both still share the models bucket)
        assert client.get("/health", headers=forwarded_headers).status_code == 200
        assert client.get("/health", headers=forwarded_headers).status_code == 200
        # Third request is rejected
        assert client.get("/health", headers=forwarded_headers).status_code == 429
        # A different forwarded-IP gets its own bucket
        other_headers = {"X-Forwarded-For": "198.51.100.42"}
        assert client.get("/health", headers=other_headers).status_code == 200

    def test_untrusted_forwarded_for_cannot_rotate_rate_bucket(
        self, limited_client_factory
    ):
        settings, client = limited_client_factory(models_limit=1)

        assert client.get(
            "/health", headers={"X-Forwarded-For": "198.51.100.1"}
        ).status_code == 200
        assert client.get(
            "/health", headers={"X-Forwarded-For": "198.51.100.2"}
        ).status_code == 429


class TestPerProjectChatRateLimit:
    def test_different_keys_get_separate_limits(self, limited_client_factory):
        settings, client = limited_client_factory(chat_limit=2)
        admin_headers = {"X-Admin-Token": "test-admin"}

        # Create two projects with separate keys
        resp1 = client.post(
            "/admin/projects",
            headers=admin_headers,
            json={"name": "proj-a", "description": "A"},
        )
        key_a_resp = client.post(
            f"/admin/projects/{resp1.json()['id']}/api-keys",
            headers=admin_headers,
            json={"name": "key-a", "scopes": ["chat:write"]},
        )
        api_key_a = key_a_resp.json()["api_key"]

        resp2 = client.post(
            "/admin/projects",
            headers=admin_headers,
            json={"name": "proj-b", "description": "B"},
        )
        key_b_resp = client.post(
            f"/admin/projects/{resp2.json()['id']}/api-keys",
            headers=admin_headers,
            json={"name": "key-b", "scopes": ["chat:write"]},
        )
        api_key_b = key_b_resp.json()["api_key"]

        headers_a = {"Authorization": f"Bearer {api_key_a}"}
        headers_b = {"Authorization": f"Bearer {api_key_b}"}

        # Use up key-a's limit
        for _ in range(2):
            resp = client.post(
                "/v1/chat/completions",
                headers=headers_a,
                json={
                    "model": "default-chat",
                    "messages": [{"role": "user", "content": "from A"}],
                },
            )
            assert resp.status_code == 200

        # key-a should be rate limited
        resp = client.post(
            "/v1/chat/completions",
            headers=headers_a,
            json={
                "model": "default-chat",
                "messages": [{"role": "user", "content": "A again"}],
            },
        )
        assert resp.status_code == 429

        # key-b should still work
        resp = client.post(
            "/v1/chat/completions",
            headers=headers_b,
            json={
                "model": "default-chat",
                "messages": [{"role": "user", "content": "from B"}],
            },
        )
        assert resp.status_code == 200

    def test_rotating_invalid_tokens_share_pre_auth_bucket(
        self, limited_client_factory
    ):
        settings, client = limited_client_factory(chat_limit=1)

        first = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer invalid-token-a"},
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        second = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer invalid-token-b"},
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

        assert first.status_code == 401
        assert second.status_code == 429


class TestRequestSizeLimit:
    def test_oversize_request_rejected(self, limited_client_factory):
        settings, client = limited_client_factory(max_request_size_mb=0)
        admin_headers = {"X-Admin-Token": "test-admin"}
        resp = client.post(
            "/admin/projects",
            headers=admin_headers,
            json={"name": "test", "description": "x"},
        )
        # With max_request_size_mb=0, Content-Length > 0 triggers rejection
        # (body always has some content)
        assert resp.status_code == 413

    def test_normal_request_accepted(self, limited_client_factory):
        settings, client = limited_client_factory(max_request_size_mb=1)
        admin_headers = {"X-Admin-Token": "test-admin"}
        resp = client.post(
            "/admin/projects",
            headers=admin_headers,
            json={"name": "test", "description": "small"},
        )
        assert resp.status_code == 200

    def test_malformed_content_length_is_rejected(self, limited_client_factory):
        settings, client = limited_client_factory(max_request_size_mb=1)

        resp = client.get("/health", headers={"Content-Length": "not-a-number"})

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid Content-Length header"

    def test_schema_rejects_unbounded_message_collection(self, limited_client_factory):
        settings, client = limited_client_factory(chat_limit=10)
        api_key = _create_project_and_key(
            client, {"X-Admin-Token": "test-admin"}
        )

        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "messages": [
                    {"role": "user", "content": str(index)}
                    for index in range(201)
                ]
            },
        )

        assert response.status_code == 422


class TestDisabledInTestMode:
    def test_zero_limit_disables_rate_limiting(self, limited_client_factory):
        """Rate limiting is disabled when limit=0 (test mode)."""
        settings, client = limited_client_factory(admin_limit=0)
        admin_headers = {"X-Admin-Token": "test-admin"}

        # Should not get rate limited even with many requests
        for _ in range(50):
            resp = client.get("/admin/usage", headers=admin_headers)
            assert resp.status_code == 200
