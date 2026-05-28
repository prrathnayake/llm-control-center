from __future__ import annotations

from llm_control_center.providers.base import ProviderChatRequest, ProviderChatResponse
from llm_control_center.schemas import ModelCapabilities, Usage


class MockProvider:
    """Deterministic provider used for tests and local smoke checks."""

    name = "mock"
    capabilities = ModelCapabilities(chat=True, streaming=True, tools=False, vision=False)

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        content = f"[mock:{request.provider_model}] {last_user}".strip()
        prompt_tokens = sum(len(message.content.split()) for message in request.messages)
        completion_tokens = len(content.split())
        return ProviderChatResponse(
            content=content,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
