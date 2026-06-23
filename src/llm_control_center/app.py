from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm_control_center.api.middleware import (
    DocsProtectionMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from llm_control_center.api.routes import admin, chat, health
from llm_control_center.config import Settings, get_settings, validate_settings
from llm_control_center.db import Store
from llm_control_center.logging_config import configure_logging
from llm_control_center.middleware import CorrelationIdMiddleware
from llm_control_center.providers.registry import build_provider_registry
from llm_control_center.routing import ModelRouter
from llm_control_center.services.api_keys import ApiKeyService
from llm_control_center.services.chat import ChatService
from llm_control_center.services.models import ModelsService
from llm_control_center.services.projects import ProjectService
from llm_control_center.services.usage import UsageService


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    validate_settings(runtime_settings)

    json_format = runtime_settings.env != "test"
    log_level = "DEBUG" if runtime_settings.env == "dev" else "INFO"
    configure_logging(level=log_level, json_format=json_format)

    store = Store(runtime_settings.database_url)
    store.initialize()
    router = ModelRouter(runtime_settings.model_routes, runtime_settings.default_model_alias)
    providers = build_provider_registry(runtime_settings)
    usage_service = UsageService(store=store)
    api_key_service = ApiKeyService(store=store, settings=runtime_settings)
    project_service = ProjectService(store=store)
    models_service = ModelsService(router=router, providers=providers)
    chat_service = ChatService(router=router, providers=providers, usage_service=usage_service)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            store.close()

    fastapi_app = FastAPI(
        title="LLM Control Center",
        version="0.1.0",
        description="Central gateway for cloud and local LLM provider calls.",
        lifespan=lifespan,
    )
    fastapi_app.state.settings = runtime_settings
    fastapi_app.state.store = store
    fastapi_app.state.router = router
    fastapi_app.state.providers = providers
    fastapi_app.state.usage_service = usage_service
    fastapi_app.state.api_key_service = api_key_service
    fastapi_app.state.project_service = project_service
    fastapi_app.state.models_service = models_service
    fastapi_app.state.chat_service = chat_service

    fastapi_app.include_router(health.router)
    fastapi_app.include_router(admin.router)
    fastapi_app.include_router(chat.router)

    # --- Middleware (last added = first executed) ---
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Admin-Token"],
        allow_credentials=True,
    )
    if runtime_settings.docs_protected:
        fastapi_app.add_middleware(
            DocsProtectionMiddleware, admin_token=runtime_settings.admin_token
        )
    fastapi_app.add_middleware(SecurityHeadersMiddleware)
    fastapi_app.add_middleware(CorrelationIdMiddleware)
    fastapi_app.add_middleware(
        RateLimitMiddleware,
        admin_limit=runtime_settings.rate_limit_admin,
        chat_limit=runtime_settings.rate_limit_chat,
        models_limit=runtime_settings.rate_limit_models,
        max_request_size_bytes=runtime_settings.max_request_size_mb * 1_048_576,
    )

    return fastapi_app


app = create_app()
