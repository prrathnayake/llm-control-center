from __future__ import annotations

import pytest

from llm_control_center.errors import UnknownModelError
from llm_control_center.routing import ModelRouter


def test_router_resolves_default_alias():
    router = ModelRouter(
        routes={"default-chat": {"provider": "mock", "provider_model": "mock-smart"}},
        default_alias="default-chat",
    )
    route = router.resolve(None)
    assert route.alias == "default-chat"
    assert route.provider == "mock"


def test_router_rejects_unknown_alias():
    router = ModelRouter(
        routes={"default-chat": {"provider": "mock", "provider_model": "mock-smart"}},
        default_alias="default-chat",
    )
    with pytest.raises(UnknownModelError, match="unknown model alias"):
        router.resolve("missing")


def test_unknown_model_returns_404(client, project_headers):
    response = client.post(
        "/v1/chat/completions",
        headers=project_headers,
        json={"model": "missing", "messages": [{"role": "user", "content": "x"}]},
    )
    assert response.status_code == 404


def test_missing_provider_route_returns_500(client, project_headers):
    response = client.post(
        "/v1/chat/completions",
        headers=project_headers,
        json={"model": "broken-provider", "messages": [{"role": "user", "content": "x"}]},
    )
    assert response.status_code == 500
