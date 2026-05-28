from __future__ import annotations

from llm_control_center.auth import ProjectPrincipal
from llm_control_center.errors import AuthorizationError


def test_admin_token_required(client):
    response = client.post("/admin/projects", json={"name": "x"})
    assert response.status_code == 401


def test_project_bearer_token_required(client):
    response = client.get("/v1/models")
    assert response.status_code == 401


def test_project_principal_scope_check():
    principal = ProjectPrincipal(project_id="p", api_key_id="k", scopes={"models:read"})
    try:
        principal.require_scope("chat:write")
    except AuthorizationError as exc:
        assert "missing scope" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected AuthorizationError")
