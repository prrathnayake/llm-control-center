from __future__ import annotations

import structlog

from llm_control_center.providers.base import (
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderResponseRequest,
    ProviderResponseResponse,
    response_input_to_messages,
    response_output_from_text,
)
from llm_control_center.schemas import ModelCapabilities, Usage

logger = structlog.stdlib.get_logger(__name__)


class MockProvider:
    """Deterministic provider used for tests and local smoke checks."""

    name = "mock"
    capabilities = ModelCapabilities(
        chat=True,
        responses=True,
        streaming=False,
        structured_outputs=True,
        tools=False,
        vision=False,
    )

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        content = f"[mock:{request.provider_model}] {last_user}".strip()
        prompt_tokens = sum(len(message.content.split()) for message in request.messages)
        completion_tokens = len(content.split())
        total = prompt_tokens + completion_tokens
        logger.debug(
            "provider_call",
            provider="mock",
            model=request.provider_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
        )
        return ProviderChatResponse(
            content=content,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total,
            ),
        )

    async def respond(self, request: ProviderResponseRequest) -> ProviderResponseResponse:
        messages = response_input_to_messages(request.input, request.instructions)
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        content = f"[mock] {last_user}".strip()
        prompt_tokens = sum(len(message.content.split()) for message in messages)
        completion_tokens = len(content.split())
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        return ProviderResponseResponse(
            output_text=content,
            output=response_output_from_text(content),
            usage=usage,
        )
