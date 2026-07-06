from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_INSECURE_DEFAULTS = frozenset(
    {
        "change-me-admin-token",
        "change-me-long-random-pepper",
    }
)


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="LLM_CC_", env_file=".env", extra="ignore")

    env: str = "dev"
    admin_token: str = "change-me-admin-token"
    api_key_pepper: str = "change-me-long-random-pepper"
    database_url: str = "sqlite:///./data/control_center.sqlite3"
    model_routes: dict[str, dict[str, str]] = Field(
        default_factory=lambda: {
            "default-chat": {"provider": "mock", "provider_model": "mock-smart"},
            "local-chat": {"provider": "ollama", "provider_model": "llama3.1"},
            "cloud-chat": {"provider": "openai_compatible", "provider_model": "gpt-4o-mini"},
        }
    )
    default_model_alias: str = "default-chat"
    openai_compatible_base_url: str = "https://api.openai.com"
    openai_compatible_api_key: str = ""
    openai_compatible_responses_api: bool = False
    ollama_base_url: str = "http://localhost:11434"
    request_timeout_seconds: float = 60.0

    rate_limit_admin: int = 60
    rate_limit_chat: int = 30
    rate_limit_models: int = 120
    max_request_size_mb: int = 1
    cors_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:8080"])
    docs_protected: bool = True

    @field_validator("model_routes", mode="before")
    @classmethod
    def parse_model_routes(cls, value: Any) -> dict[str, dict[str, str]]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("LLM_CC_MODEL_ROUTES must be valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError("LLM_CC_MODEL_ROUTES must be a JSON object")
            return parsed
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


def validate_settings(settings: Settings) -> None:
    """Validate cross-field constraints that Pydantic alone cannot express well."""

    if settings.default_model_alias not in settings.model_routes:
        raise ValidationError.from_exception_data(
            title="Settings",
            line_errors=[
                {
                    "type": "value_error",
                    "loc": ("default_model_alias",),
                    "msg": "default model alias must exist in model_routes",
                    "input": settings.default_model_alias,
                    "ctx": {"error": ValueError("missing default model route")},
                }
            ],
        )

    if settings.admin_token in _INSECURE_DEFAULTS:
        logger.warning(
            "LLM_CC_ADMIN_TOKEN is using an insecure default value. "
            "Set a strong, unique token before deploying to production."
        )
    if settings.api_key_pepper in _INSECURE_DEFAULTS:
        logger.warning(
            "LLM_CC_API_KEY_PEPPER is using an insecure default value. "
            "Set a strong, unique pepper before deploying to production."
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    validate_settings(settings)
    return settings
