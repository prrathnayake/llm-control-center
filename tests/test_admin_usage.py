from __future__ import annotations


def test_usage_list_filters_by_project_id(client, admin_headers):
    project1_response = client.post(
        "/admin/projects",
        headers=admin_headers,
        json={"name": "proj1", "description": "first"},
    )
    project1_id = project1_response.json()["id"]

    project2_response = client.post(
        "/admin/projects",
        headers=admin_headers,
        json={"name": "proj2", "description": "second"},
    )
    project2_id = project2_response.json()["id"]

    for project_id in [project1_id, project1_id, project2_id]:
        client.post(
            "/admin/projects",
            headers=admin_headers,
            json={"name": f"dummy-{project_id[:8]}", "description": "for key creation"},
        )

    key1_response = client.post(
        f"/admin/projects/{project1_id}/api-keys",
        headers=admin_headers,
        json={"name": "key1", "scopes": ["chat:write"]},
    )
    key1 = key1_response.json()["api_key"]

    key2_response = client.post(
        f"/admin/projects/{project2_id}/api-keys",
        headers=admin_headers,
        json={"name": "key2", "scopes": ["chat:write"]},
    )
    key2 = key2_response.json()["api_key"]

    client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key1}"},
        json={"model": "default-chat", "messages": [{"role": "user", "content": "a"}]},
    )
    client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key1}"},
        json={"model": "default-chat", "messages": [{"role": "user", "content": "b"}]},
    )
    client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key2}"},
        json={"model": "default-chat", "messages": [{"role": "user", "content": "c"}]},
    )

    all_logs = client.get("/admin/usage", headers=admin_headers).json()["data"]
    assert len(all_logs) == 3

    proj1_logs = client.get(
        f"/admin/usage?project_id={project1_id}", headers=admin_headers
    ).json()["data"]
    assert len(proj1_logs) == 2
    assert all(log["project_id"] == project1_id for log in proj1_logs)

    proj2_logs = client.get(
        f"/admin/usage?project_id={project2_id}", headers=admin_headers
    ).json()["data"]
    assert len(proj2_logs) == 1
    assert proj2_logs[0]["project_id"] == project2_id


def test_usage_list_limit(client, admin_headers):
    project_response = client.post(
        "/admin/projects",
        headers=admin_headers,
        json={"name": "limit-proj", "description": "test"},
    )
    project_id = project_response.json()["id"]
    key_response = client.post(
        f"/admin/projects/{project_id}/api-keys",
        headers=admin_headers,
        json={"name": "key", "scopes": ["chat:write"]},
    )
    key = key_response.json()["api_key"]

    for i in range(5):
        client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "default-chat",
                "messages": [{"role": "user", "content": f"msg {i}"}],
            },
        )

    response = client.get("/admin/usage?limit=2", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2
