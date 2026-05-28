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
