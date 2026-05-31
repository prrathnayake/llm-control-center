from __future__ import annotations

import pytest

from llm_control_center.auth import ProjectPrincipal
from llm_control_center.errors import AuthorizationError


def test_admin_token_required(client):
    response = client.post("/admin/projects", json={"name": "x"})
    assert response.status_code == 401


def test_admin_token_rejects_wrong_token(client):
    response = client.post(
        "/admin/projects",
        headers={"X-Admin-Token": "wrong-token"},
        json={"name": "x"},
    )
    assert response.status_code == 401


def test_project_bearer_token_required(client):
    response = client.get("/v1/models")
    assert response.status_code == 401


def test_project_bearer_token_rejects_invalid(client):
    response = client.get("/v1/models", headers={"Authorization": "Bearer invalid-key"})
    assert response.status_code == 401


def test_project_principal_scope_check():
    principal = ProjectPrincipal(project_id="p", api_key_id="k", scopes={"models:read"})
    with pytest.raises(AuthorizationError, match="missing scope"):
        principal.require_scope("chat:write")


def test_project_principal_scope_passes():
    principal = ProjectPrincipal(project_id="p", api_key_id="k", scopes={"chat:write"})
    principal.require_scope("chat:write")
