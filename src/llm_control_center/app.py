from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from llm_control_center.api.routes import admin, chat, health
from llm_control_center.config import Settings, get_settings, validate_settings
from llm_control_center.db import SQLiteStore
from llm_control_center.providers.registry import build_provider_registry
from llm_control_center.routing import ModelRouter
from llm_control_center.services.api_keys import ApiKeyService
from llm_control_center.services.chat import ChatService
from llm_control_center.services.usage import UsageService


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    validate_settings(runtime_settings)

    store = SQLiteStore(runtime_settings.database_url)
    store.initialize()
    router = ModelRouter(runtime_settings.model_routes, runtime_settings.default_model_alias)
    providers = build_provider_registry(runtime_settings)
    usage_service = UsageService(store=store)
    api_key_service = ApiKeyService(store=store, settings=runtime_settings)
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
    fastapi_app.state.chat_service = chat_service

    fastapi_app.include_router(health.router)
    fastapi_app.include_router(admin.router)
    fastapi_app.include_router(chat.router)
    return fastapi_app


app = create_app()
