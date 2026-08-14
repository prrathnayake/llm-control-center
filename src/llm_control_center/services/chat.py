from __future__ import annotations

import asyncio
import uuid

import structlog
from structlog.contextvars import bind_contextvars, unbind_contextvars

from llm_control_center.auth import ProjectPrincipal
from llm_control_center.errors import (
    AuthorizationError,
    LLMControlCenterError,
    ProviderExecutionError,
)
from llm_control_center.providers.base import ProviderChatRequest, ProviderResponseRequest
from llm_control_center.providers.registry import ProviderRegistry
from llm_control_center.routing import ModelRouter
from llm_control_center.schemas import (
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    RequestMetadata,
    ResponseOutputContent,
    ResponseOutputMessage,
    ResponseRequest,
    ResponseResult,
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
        await self.usage_service.record_async(**kwargs)

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
            except asyncio.CancelledError:
                await self._record_usage(
                    trace_id=trace_id,
                    endpoint="/v1/chat/completions",
                    request_kind="chat",
                    project_id=principal.project_id,
                    model_alias=route.alias,
                    provider=route.provider,
                    provider_model=route.provider_model,
                    status="cancelled",
                    latency_ms=timing.latency_ms,
                    usage=Usage(),
                    error="request cancelled",
                    metadata=metadata,
                )
                raise
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
                    endpoint="/v1/chat/completions",
                    request_kind="chat",
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
                error = ProviderExecutionError("unexpected provider failure")
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
                    endpoint="/v1/chat/completions",
                    request_kind="chat",
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
            endpoint="/v1/chat/completions",
            request_kind="chat",
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


class ResponseService:
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
        await self.usage_service.record_async(**kwargs)

    async def respond(
        self,
        *,
        principal: ProjectPrincipal,
        request: ResponseRequest,
    ) -> ResponseResult:
        if "responses:write" not in principal.scopes and "chat:write" not in principal.scopes:
            raise AuthorizationError("missing scope: responses:write")
        trace_id = new_trace_id()
        metadata = request.metadata
        bind_contextvars(
            workflow=metadata.workflow,
            session_id=metadata.session_id,
            user_id=metadata.user_id,
        )
        try:
            return await self._respond(
                principal=principal,
                request=request,
                trace_id=trace_id,
                metadata=metadata,
            )
        finally:
            unbind_contextvars("workflow", "session_id", "user_id")

    async def _respond(
        self,
        *,
        principal: ProjectPrincipal,
        request: ResponseRequest,
        trace_id: str,
        metadata: RequestMetadata,
    ) -> ResponseResult:
        route = self.router.resolve(request.model)
        provider_request = ProviderResponseRequest(
            provider_model=route.provider_model,
            input=request.input,
            instructions=request.instructions,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
            text=request.text,
            reasoning=request.reasoning,
            tools=request.tools,
            tool_choice=request.tool_choice,
            parallel_tool_calls=request.parallel_tool_calls,
            metadata=metadata.model_dump(exclude_none=True),
            provider_options=request.provider_options,
        )

        with timer() as timing:
            try:
                provider = self.providers.get(route.provider)
                provider_response = await provider.respond(provider_request)
            except asyncio.CancelledError:
                await self._record_usage(
                    trace_id=trace_id,
                    endpoint="/v1/responses",
                    request_kind="responses",
                    project_id=principal.project_id,
                    model_alias=route.alias,
                    provider=route.provider,
                    provider_model=route.provider_model,
                    status="cancelled",
                    latency_ms=timing.latency_ms,
                    usage=Usage(),
                    error="request cancelled",
                    metadata=metadata,
                )
                raise
            except LLMControlCenterError as exc:
                logger.error(
                    "response_error",
                    model_alias=route.alias,
                    provider=route.provider,
                    latency_ms=timing.latency_ms,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                await self._record_usage(
                    trace_id=trace_id,
                    endpoint="/v1/responses",
                    request_kind="responses",
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
                error = ProviderExecutionError("unexpected provider failure")
                logger.error(
                    "response_error",
                    model_alias=route.alias,
                    provider=route.provider,
                    latency_ms=timing.latency_ms,
                    error_type=type(error).__name__,
                    error_message=str(error),
                    exc_info=True,
                )
                await self._record_usage(
                    trace_id=trace_id,
                    endpoint="/v1/responses",
                    request_kind="responses",
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
            "response_success",
            model_alias=route.alias,
            provider=route.provider,
            latency_ms=timing.latency_ms,
            tokens=provider_response.usage.total_tokens,
        )

        await self._record_usage(
            trace_id=trace_id,
            endpoint="/v1/responses",
            request_kind="responses",
            project_id=principal.project_id,
            model_alias=route.alias,
            provider=route.provider,
            provider_model=route.provider_model,
            status="success",
            latency_ms=timing.latency_ms,
            usage=provider_response.usage,
            metadata=metadata,
        )

        output_text = provider_response.output_text
        output = provider_response.output or [
            ResponseOutputMessage(content=[ResponseOutputContent(text=output_text)]).model_dump()
        ]
        return ResponseResult(
            id=provider_response.id or f"resp_{uuid.uuid4().hex}",
            status=provider_response.status,  # type: ignore[arg-type]
            created_at=now_epoch_seconds(),
            model=route.alias,
            provider=route.provider,
            trace_id=trace_id,
            output=output,
            output_text=output_text,
            usage=provider_response.usage,
            metadata=metadata.model_dump(exclude_none=True),
        )
