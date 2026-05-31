from __future__ import annotations

import uuid

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
    Usage,
    coerce_finish_reason,
)
from llm_control_center.services.usage import UsageService
from llm_control_center.telemetry import new_trace_id, now_epoch_seconds, timer


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

    async def complete(
        self,
        *,
        principal: ProjectPrincipal,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        principal.require_scope("chat:write")
        trace_id = new_trace_id()
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
                self.usage_service.record(
                    trace_id=trace_id,
                    project_id=principal.project_id,
                    model_alias=route.alias,
                    provider=route.provider,
                    provider_model=route.provider_model,
                    status="error",
                    latency_ms=timing.latency_ms,
                    usage=Usage(),
                    error=str(exc),
                )
                raise
            except Exception as exc:
                error = ProviderExecutionError(f"unexpected provider failure: {exc}")
                self.usage_service.record(
                    trace_id=trace_id,
                    project_id=principal.project_id,
                    model_alias=route.alias,
                    provider=route.provider,
                    provider_model=route.provider_model,
                    status="error",
                    latency_ms=timing.latency_ms,
                    usage=Usage(),
                    error=str(error),
                )
                raise error from exc

        self.usage_service.record(
            trace_id=trace_id,
            project_id=principal.project_id,
            model_alias=route.alias,
            provider=route.provider,
            provider_model=route.provider_model,
            status="success",
            latency_ms=timing.latency_ms,
            usage=provider_response.usage,
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
