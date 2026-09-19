from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_control_center.config import Settings, validate_settings


class TestModelRoutesParsing:
    def test_parse_model_routes_from_json_string(self, monkeypatch):
        routes = '{"route-a": {"provider": "mock", "provider_model": "m1"}}'
        monkeypatch.setenv("LLM_CC_MODEL_ROUTES", routes)
        monkeypatch.setenv("LLM_CC_DEFAULT_MODEL_ALIAS", "route-a")
        settings = Settings()
        assert "route-a" in settings.model_routes

    def test_parse_model_routes_rejects_invalid_json(self, monkeypatch):
        from pydantic_settings.exceptions import SettingsError

        monkeypatch.setenv("LLM_CC_MODEL_ROUTES", "not json {{{")
        with pytest.raises(SettingsError):
            Settings()

    def test_parse_model_routes_rejects_non_dict_json(self, monkeypatch):
        monkeypatch.setenv("LLM_CC_MODEL_ROUTES", '["not", "a", "dict"]')
        with pytest.raises(ValidationError):
            Settings()

    def test_parse_model_routes_from_dict(self):
        routes = {"my-route": {"provider": "mock", "provider_model": "m1"}}
        settings = Settings(model_routes=routes, default_model_alias="my-route")
        assert settings.model_routes == routes


class TestValidateSettings:
    def test_raises_on_missing_default_alias(self):
        settings = Settings(
            model_routes={"a": {"provider": "mock", "provider_model": "m"}},
            default_model_alias="nonexistent",
            admin_token="secure-token",
            api_key_pepper="secure-pepper",
        )
        with pytest.raises(ValidationError, match="missing default model route"):
            validate_settings(settings)

    def test_passes_with_valid_config(self):
        settings = Settings(
            model_routes={"my-route": {"provider": "mock", "provider_model": "m"}},
            default_model_alias="my-route",
            admin_token="secure-token",
            api_key_pepper="secure-pepper",
        )
        validate_settings(settings)

    def test_production_rejects_insecure_default_secrets(self):
        with pytest.raises(ValueError, match="production requires"):
            validate_settings(Settings(env="production"))
