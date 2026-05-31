from __future__ import annotations

from llm_control_center.app import create_app
from llm_control_center.config import Settings


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_state_has_all_services(settings):
    app = create_app(settings)
    assert hasattr(app.state, "settings")
    assert hasattr(app.state, "store")
    assert hasattr(app.state, "router")
    assert hasattr(app.state, "providers")
    assert hasattr(app.state, "usage_service")
    assert hasattr(app.state, "api_key_service")
    assert hasattr(app.state, "chat_service")
    assert isinstance(app.state.settings, Settings)
