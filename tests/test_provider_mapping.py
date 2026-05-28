from __future__ import annotations

import asyncio

from llm_control_center.providers.mock import MockProvider
from llm_control_center.providers.ollama import OllamaProvider
from llm_control_center.providers.openai_compatible import OpenAICompatibleProvider
from llm_control_center.schemas import ModelCapabilities


def test_mock_provider_counts_tokens():
    provider = MockProvider()
    from llm_control_center.providers.base import ProviderChatRequest
    from llm_control_center.schemas import ChatMessage

    response = asyncio.run(
        provider.chat(
            ProviderChatRequest(
                provider_model="mock-model",
                messages=[ChatMessage(role="user", content="hello world")],
            )
        )
    )
    assert response.content == "[mock:mock-model] hello world"
    assert response.usage.prompt_tokens == 2
    assert response.usage.total_tokens >= response.usage.completion_tokens


def test_provider_capability_contracts():
    providers = [
        MockProvider(),
        OpenAICompatibleProvider(base_url="https://example.com", api_key="test"),
        OllamaProvider(base_url="http://localhost:11434"),
    ]
    for provider in providers:
        assert provider.name
        assert isinstance(provider.capabilities, ModelCapabilities)
        assert provider.capabilities.chat is True
