from __future__ import annotations


def test_create_project_and_api_key(client, admin_headers):
    project_response = client.post(
        "/admin/projects",
        headers=admin_headers,
        json={"name": "agent", "description": "Agent app"},
    )
    assert project_response.status_code == 200
    project = project_response.json()
    assert project["id"].startswith("prj_")

    key_response = client.post(
        f"/admin/projects/{project['id']}/api-keys",
        headers=admin_headers,
        json={"name": "local-dev", "scopes": ["chat:write"]},
    )
    assert key_response.status_code == 200
    body = key_response.json()
    assert body["api_key"].startswith("llmcc_")
    assert body["key"]["prefix"] == body["api_key"][:16]
    assert "key_hash" not in body["key"]


def test_invalid_project_key_is_rejected(client):
    response = client.get("/v1/models", headers={"Authorization": "Bearer bad-key"})
    assert response.status_code == 401
