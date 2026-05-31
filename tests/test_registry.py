from __future__ import annotations

import pytest

from llm_control_center.providers.mock import MockProvider
from llm_control_center.providers.ollama import OllamaProvider
from llm_control_center.providers.openai_compatible import OpenAICompatibleProvider
from llm_control_center.providers.registry import ProviderRegistry


class TestProviderRegistry:
    def test_names_returns_sorted_list(self):
        registry = ProviderRegistry(
            providers=[
                OpenAICompatibleProvider(base_url="https://example.com", api_key="test"),
                MockProvider(),
                OllamaProvider(base_url="http://localhost:11434"),
            ]
        )
        names = registry.names()
        assert names == ["mock", "ollama", "openai_compatible"]

    def test_get_returns_provider(self):
        registry = ProviderRegistry(providers=[MockProvider()])
        provider = registry.get("mock")
        assert provider.name == "mock"

    def test_get_raises_for_unknown_provider(self):
        registry = ProviderRegistry(providers=[MockProvider()])
        with pytest.raises(Exception, match="provider is not registered"):
            registry.get("nonexistent")
