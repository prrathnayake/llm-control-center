from __future__ import annotations

import uuid

import structlog
from fastapi.concurrency import run_in_threadpool
from structlog.contextvars import bind_contextvars, unbind_contextvars

from llm_control_center.auth import ProjectPrincipal
from llm_control_center.errors import LLMControlCenterError, ProviderExecutionError
from llm_control_center.providers.base import ProviderChatRequest
from llm_control_center.providers.registry import ProviderRegistry
from llm_control_center.routing import ModelRouter
from llm_control_center.schemas import (
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    RequestMetadata,
    Usage,
    coerce_finish_reason,
)
from llm_control_center.services.usage import UsageService
from llm_control_center.telemetry import new_trace_id, now_epoch_seconds, timer

logger = structlog.stdlib.get_logger(__name__)


class ChatService:
    def __init__(
        self,
        *,
        router: ModelRouter,
        providers: ProviderRegistry,
        usage_service: UsageService,
    ) -> None:
        self.router = router
        self.providers = providers
        self.usage_service = usage_service

    async def _record_usage(self, **kwargs) -> None:
        await run_in_threadpool(self.usage_service.record, **kwargs)

    async def complete(
        self,
        *,
        principal: ProjectPrincipal,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        principal.require_scope("chat:write")
        trace_id = new_trace_id()
        metadata = request.metadata
        bind_contextvars(
            workflow=metadata.workflow,
            session_id=metadata.session_id,
            user_id=metadata.user_id,
        )
        try:
            return await self._complete(
                principal=principal,
                request=request,
                trace_id=trace_id,
                metadata=metadata,
            )
        finally:
            unbind_contextvars("workflow", "session_id", "user_id")

    async def _complete(
        self,
        *,
        principal: ProjectPrincipal,
        request: ChatCompletionRequest,
        trace_id: str,
        metadata: RequestMetadata,
    ) -> ChatCompletionResponse:
        route = self.router.resolve(request.model)
        provider = self.providers.get(route.provider)
        provider_request = ProviderChatRequest(
            provider_model=route.provider_model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
            provider_options=request.provider_options,
        )

        with timer() as timing:
            try:
                provider_response = await provider.chat(provider_request)
            except LLMControlCenterError as exc:
                logger.error(
                    "chat_completion_error",
                    model_alias=route.alias,
                    provider=route.provider,
                    latency_ms=timing.latency_ms,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                await self._record_usage(
                    trace_id=trace_id,
                    project_id=principal.project_id,
                    model_alias=route.alias,
                    provider=route.provider,
                    provider_model=route.provider_model,
                    status="error",
                    latency_ms=timing.latency_ms,
                    usage=Usage(),
                    error=str(exc),
                    metadata=metadata,
                )
                raise
            except Exception as exc:
                error = ProviderExecutionError(f"unexpected provider failure: {exc}")
                logger.error(
                    "chat_completion_error",
                    model_alias=route.alias,
                    provider=route.provider,
                    latency_ms=timing.latency_ms,
                    error_type=type(error).__name__,
                    error_message=str(error),
                    exc_info=True,
                )
                await self._record_usage(
                    trace_id=trace_id,
                    project_id=principal.project_id,
                    model_alias=route.alias,
                    provider=route.provider,
                    provider_model=route.provider_model,
                    status="error",
                    latency_ms=timing.latency_ms,
                    usage=Usage(),
                    error=str(error),
                    metadata=metadata,
                )
                raise error from exc

        logger.info(
            "chat_completion_success",
            model_alias=route.alias,
            provider=route.provider,
            latency_ms=timing.latency_ms,
            tokens=provider_response.usage.total_tokens,
        )

        await self._record_usage(
            trace_id=trace_id,
            project_id=principal.project_id,
            model_alias=route.alias,
            provider=route.provider,
            provider_model=route.provider_model,
            status="success",
            latency_ms=timing.latency_ms,
            usage=provider_response.usage,
            metadata=metadata,
        )

        return ChatCompletionResponse(
            id=f"chatcmpl_{uuid.uuid4().hex}",
            created=now_epoch_seconds(),
            model=route.alias,
            provider=route.provider,
            trace_id=trace_id,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=provider_response.content),
                    finish_reason=coerce_finish_reason(provider_response.finish_reason),
                )
            ],
            usage=provider_response.usage,
        )
