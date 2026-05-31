from __future__ import annotations

import logging

from llm_control_center.config import Settings, validate_settings


def test_create_duplicate_project_returns_409(client, admin_headers):
    client.post(
        "/admin/projects",
        headers=admin_headers,
        json={"name": "unique-project", "description": "first"},
    )
    response = client.post(
        "/admin/projects",
        headers=admin_headers,
        json={"name": "unique-project", "description": "second"},
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_list_models_requires_models_read_scope(client, admin_headers):
    project_response = client.post(
        "/admin/projects",
        headers=admin_headers,
        json={"name": "read-test", "description": "test"},
    )
    project_id = project_response.json()["id"]
    key_response = client.post(
        f"/admin/projects/{project_id}/api-keys",
        headers=admin_headers,
        json={"name": "write-only", "scopes": ["chat:write"]},
    )
    raw_key = key_response.json()["api_key"]
    response = client.get(
        "/v1/models",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 403


def test_list_models_succeeds_with_models_read_scope(client, project_headers):
    response = client.get("/v1/models", headers=project_headers)
    assert response.status_code == 200
    models = response.json()["data"]
    assert len(models) > 0


def test_validate_settings_warns_on_default_admin_token(caplog):
    settings = Settings(
        admin_token="change-me-admin-token",
        api_key_pepper="unique-pepper-value",
    )
    with caplog.at_level(logging.WARNING):
        validate_settings(settings)
    assert "LLM_CC_ADMIN_TOKEN" in caplog.text


def test_validate_settings_warns_on_default_pepper(caplog):
    settings = Settings(
        admin_token="unique-admin-value",
        api_key_pepper="change-me-long-random-pepper",
    )
    with caplog.at_level(logging.WARNING):
        validate_settings(settings)
    assert "LLM_CC_API_KEY_PEPPER" in caplog.text


def test_validate_settings_no_warning_on_secure_values(caplog):
    settings = Settings(
        admin_token="super-secret-admin-token-12345",
        api_key_pepper="super-secret-pepper-67890",
    )
    with caplog.at_level(logging.WARNING):
        validate_settings(settings)
    assert "insecure" not in caplog.text
