from __future__ import annotations

from unittest.mock import AsyncMock, patch

from llm_control_center.errors import ProviderExecutionError


class TestChatCompletionErrorPaths:
    def test_authorization_error_returns_403(self, client, admin_headers):
        project_response = client.post(
            "/admin/projects",
            headers=admin_headers,
            json={"name": "no-chat", "description": "test"},
        )
        project_id = project_response.json()["id"]
        key_response = client.post(
            f"/admin/projects/{project_id}/api-keys",
            headers=admin_headers,
            json={"name": "read-only", "scopes": ["models:read"]},
        )
        raw_key = key_response.json()["api_key"]
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={
                "model": "default-chat",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert response.status_code == 403
        assert "missing scope" in response.json()["detail"]

    def test_provider_not_found_returns_500(self, client, project_headers):
        response = client.post(
            "/v1/chat/completions",
            headers=project_headers,
            json={
                "model": "broken-provider",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert response.status_code == 500
        assert "provider is not registered" in response.json()["detail"]

    def test_provider_execution_error_returns_502(self, client, project_headers):
        with patch(
            "llm_control_center.services.chat.ChatService.complete",
            new_callable=AsyncMock,
            side_effect=ProviderExecutionError("provider is down"),
        ):
            response = client.post(
                "/v1/chat/completions",
                headers=project_headers,
                json={
                    "model": "default-chat",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
        assert response.status_code == 502
        assert "provider is down" in response.json()["detail"]

    def test_unknown_model_returns_404(self, client, project_headers):
        response = client.post(
            "/v1/chat/completions",
            headers=project_headers,
            json={
                "model": "nonexistent-model",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert response.status_code == 404
        assert "unknown model alias" in response.json()["detail"]

    def test_streaming_returns_501(self, client, project_headers):
        response = client.post(
            "/v1/chat/completions",
            headers=project_headers,
            json={
                "model": "default-chat",
                "stream": True,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert response.status_code == 501
        assert "streaming" in response.json()["detail"].lower()


class TestChatCompletionSuccessWithUsage:
    def test_chat_records_usage_on_success(self, client, project_headers, admin_headers):
        response = client.post(
            "/v1/chat/completions",
            headers=project_headers,
            json={
                "model": "default-chat",
                "messages": [{"role": "user", "content": "test usage"}],
            },
        )
        assert response.status_code == 200
        trace_id = response.json()["trace_id"]

        usage_response = client.get("/admin/usage", headers=admin_headers)
        assert usage_response.status_code == 200
        logs = usage_response.json()["data"]
        assert len(logs) == 1
        assert logs[0]["trace_id"] == trace_id
        assert logs[0]["status"] == "success"
        assert logs[0]["prompt_tokens"] > 0
