from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from llm_control_center.app import create_app
from llm_control_center.config import Settings


@pytest.fixture()
def settings(tmp_path) -> Settings:
    return Settings(
        admin_token="test-admin",
        api_key_pepper="test-pepper",
        database_url=f"sqlite:///{tmp_path}/test.sqlite3",
        model_routes={
            "default-chat": {"provider": "mock", "provider_model": "mock-smart"},
            "broken-provider": {"provider": "missing", "provider_model": "x"},
        },
        default_model_alias="default-chat",
        openai_compatible_api_key="",
        rate_limit_admin=0,
        rate_limit_chat=0,
        rate_limit_models=0,
        max_request_size_mb=1,
        docs_protected=False,
        cors_origins=["http://testserver"],
    )


@pytest.fixture()
def client(settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "test-admin"}


@pytest.fixture()
def project_key(client: TestClient, admin_headers: dict[str, str]) -> str:
    project_response = client.post(
        "/admin/projects",
        headers=admin_headers,
        json={"name": "demo", "description": "Demo project"},
    )
    assert project_response.status_code == 200
    project_id = project_response.json()["id"]
    key_response = client.post(
        f"/admin/projects/{project_id}/api-keys",
        headers=admin_headers,
        json={"name": "dev", "scopes": ["chat:write", "models:read"]},
    )
    assert key_response.status_code == 200
    return key_response.json()["api_key"]


@pytest.fixture()
def project_headers(project_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {project_key}"}
