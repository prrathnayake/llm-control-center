from __future__ import annotations


def test_chat_completion_uses_mock_provider(client, project_headers, admin_headers):
    response = client.post(
        "/v1/chat/completions",
        headers=project_headers,
        json={
            "model": "default-chat",
            "messages": [{"role": "user", "content": "Hello gateway"}],
            "metadata": {"workflow": "unit-test"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "default-chat"
    assert body["provider"] == "mock"
    assert body["choices"][0]["message"]["content"] == "[mock:mock-smart] Hello gateway"
    assert body["usage"]["total_tokens"] > 0
    assert body["trace_id"].startswith("tr_")

    usage_response = client.get("/admin/usage", headers=admin_headers)
    assert usage_response.status_code == 200
    logs = usage_response.json()["data"]
    assert len(logs) == 1
    assert logs[0]["status"] == "success"
    assert logs[0]["provider"] == "mock"


def test_streaming_is_explicitly_not_implemented(client, project_headers):
    response = client.post(
        "/v1/chat/completions",
        headers=project_headers,
        json={
            "model": "default-chat",
            "stream": True,
            "messages": [{"role": "user", "content": "stream please"}],
        },
    )
    assert response.status_code == 501


def test_request_metadata_is_recorded_in_usage_logs(client, project_headers, admin_headers):
    response = client.post(
        "/v1/chat/completions",
        headers=project_headers,
        json={
            "model": "default-chat",
            "messages": [{"role": "user", "content": "tagged request"}],
            "metadata": {
                "workflow": "nightly-batch",
                "session_id": "sess_abc",
                "user_id": "user_42",
                "tags": ["eval", "smoke"],
            },
        },
    )
    assert response.status_code == 200

    logs = client.get("/admin/usage", headers=admin_headers).json()["data"]
    log = logs[0]
    assert log["workflow"] == "nightly-batch"
    assert log["session_id"] == "sess_abc"
    assert log["user_id"] == "user_42"
    assert log["tags"] == ["eval", "smoke"]


def test_request_metadata_defaults_when_omitted(client, project_headers, admin_headers):
    response = client.post(
        "/v1/chat/completions",
        headers=project_headers,
        json={
            "model": "default-chat",
            "messages": [{"role": "user", "content": "no metadata"}],
        },
    )
    assert response.status_code == 200

    logs = client.get("/admin/usage", headers=admin_headers).json()["data"]
    log = logs[0]
    assert log["workflow"] is None
    assert log["session_id"] is None
    assert log["user_id"] is None
    assert log["tags"] == []
