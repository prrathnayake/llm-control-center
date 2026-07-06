from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from llm_control_center.app import create_app
from llm_control_center.config import Settings


def test_responses_requires_project_auth(client):
    response = client.post(
        "/v1/responses",
        json={"model": "default-chat", "input": "hello"},
    )

    assert response.status_code == 401


def test_responses_requires_write_scope(settings, admin_headers):
    app = create_app(settings)
    with TestClient(app) as scoped_client:
        project = scoped_client.post(
            "/admin/projects",
            headers=admin_headers,
            json={"name": "read-only", "description": ""},
        ).json()
        key = scoped_client.post(
            f"/admin/projects/{project['id']}/api-keys",
            headers=admin_headers,
            json={"name": "reader", "scopes": ["models:read"]},
        ).json()["api_key"]

        response = scoped_client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "default-chat", "input": "hello"},
        )

    assert response.status_code == 403


def test_responses_endpoint_uses_mock_provider(client, project_headers, admin_headers):
    response = client.post(
        "/v1/responses",
        headers=project_headers,
        json={
            "model": "default-chat",
            "input": "Hello gateway",
            "metadata": {"workflow": "responses-unit", "session_id": "sess_1"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "response"
    assert body["status"] == "completed"
    assert body["model"] == "default-chat"
    assert body["provider"] == "mock"
    assert body["trace_id"].startswith("tr_")
    assert body["output_text"] == "[mock] Hello gateway"
    assert body["output"][0]["content"][0]["text"] == "[mock] Hello gateway"
    assert body["usage"]["total_tokens"] > 0
    assert body["metadata"]["workflow"] == "responses-unit"
    assert "mock-smart" not in response.text

    usage = client.get("/admin/usage?endpoint=/v1/responses", headers=admin_headers).json()
    assert len(usage["data"]) == 1
    assert usage["data"][0]["endpoint"] == "/v1/responses"
    assert usage["data"][0]["request_kind"] == "responses"
    assert usage["data"][0]["workflow"] == "responses-unit"


def test_responses_unknown_model_returns_404(client, project_headers):
    response = client.post(
        "/v1/responses",
        headers=project_headers,
        json={"model": "missing", "input": "hello"},
    )

    assert response.status_code == 404


def test_responses_provider_failure_is_logged(client, project_headers, admin_headers):
    response = client.post(
        "/v1/responses",
        headers=project_headers,
        json={"model": "broken-provider", "input": "hello"},
    )

    assert response.status_code == 500
    logs = client.get("/admin/usage?status=error", headers=admin_headers).json()["data"]
    assert len(logs) == 1
    assert logs[0]["endpoint"] == "/v1/responses"
    assert logs[0]["request_kind"] == "responses"
    assert logs[0]["status"] == "error"


def test_usage_filters_include_activity_fields(client, project_headers, admin_headers):
    client.post(
        "/v1/responses",
        headers=project_headers,
        json={
            "model": "default-chat",
            "input": "first",
            "metadata": {
                "workflow": "nightly",
                "session_id": "sess_filter",
                "user_id": "user_filter",
            },
        },
    )
    client.post(
        "/v1/chat/completions",
        headers=project_headers,
        json={
            "model": "default-chat",
            "messages": [{"role": "user", "content": "second"}],
            "metadata": {"workflow": "other"},
        },
    )

    filtered = client.get(
        "/admin/usage"
        "?endpoint=/v1/responses"
        "&status=success"
        "&workflow=nightly"
        "&session_id=sess_filter"
        "&user_id=user_filter",
        headers=admin_headers,
    ).json()["data"]

    assert len(filtered) == 1
    assert filtered[0]["request_kind"] == "responses"
    assert filtered[0]["workflow"] == "nightly"


def test_parallel_responses_record_all_activity(settings, admin_headers):
    app = create_app(settings)
    with TestClient(app) as parallel_client:
        project = parallel_client.post(
            "/admin/projects",
            headers=admin_headers,
            json={"name": "parallel", "description": ""},
        ).json()
        key = parallel_client.post(
            f"/admin/projects/{project['id']}/api-keys",
            headers=admin_headers,
            json={"name": "writer", "scopes": ["chat:write"]},
        ).json()["api_key"]
        headers = {"Authorization": f"Bearer {key}"}

        def call_response(i: int) -> str:
            response = parallel_client.post(
                "/v1/responses",
                headers=headers,
                json={"model": "default-chat", "input": f"message {i}"},
            )
            assert response.status_code == 200
            return response.json()["trace_id"]

        with ThreadPoolExecutor(max_workers=8) as executor:
            trace_ids = list(executor.map(call_response, range(12)))

        logs = parallel_client.get(
            f"/admin/usage?project_id={project['id']}&endpoint=/v1/responses&limit=20",
            headers=admin_headers,
        ).json()["data"]

    assert len(trace_ids) == 12
    assert len(set(trace_ids)) == 12
    assert len(logs) == 12
    assert {log["trace_id"] for log in logs} == set(trace_ids)


def test_responses_rate_limit_is_project_key_scoped(tmp_path, admin_headers):
    settings = Settings(
        admin_token="test-admin",
        api_key_pepper="test-pepper",
        database_url=f"sqlite:///{tmp_path}/rate.sqlite3",
        model_routes={
            "default-chat": {"provider": "mock", "provider_model": "mock-smart"},
        },
        default_model_alias="default-chat",
        rate_limit_admin=0,
        rate_limit_chat=1,
        rate_limit_models=0,
        docs_protected=False,
    )
    app = create_app(settings)
    with TestClient(app) as rate_client:
        project = rate_client.post(
            "/admin/projects",
            headers=admin_headers,
            json={"name": "rate", "description": ""},
        ).json()
        key = rate_client.post(
            f"/admin/projects/{project['id']}/api-keys",
            headers=admin_headers,
            json={"name": "writer", "scopes": ["chat:write"]},
        ).json()["api_key"]
        headers = {"Authorization": f"Bearer {key}"}

        first = rate_client.post(
            "/v1/responses",
            headers=headers,
            json={"model": "default-chat", "input": "one"},
        )
        second = rate_client.post(
            "/v1/responses",
            headers=headers,
            json={"model": "default-chat", "input": "two"},
        )

    assert first.status_code == 200
    assert second.status_code == 429
