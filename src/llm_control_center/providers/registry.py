from __future__ import annotations

from llm_control_center.config import Settings
from llm_control_center.errors import ProviderNotFoundError
from llm_control_center.providers.base import ProviderAdapter
from llm_control_center.providers.mock import MockProvider
from llm_control_center.providers.ollama import OllamaProvider
from llm_control_center.providers.openai_compatible import OpenAICompatibleProvider


class ProviderRegistry:
    def __init__(self, providers: list[ProviderAdapter]) -> None:
        self._providers = {provider.name: provider for provider in providers}

    def get(self, name: str) -> ProviderAdapter:
        provider = self._providers.get(name)
        if provider is None:
            raise ProviderNotFoundError(f"provider is not registered: {name}")
        return provider

    def names(self) -> list[str]:
        return sorted(self._providers)


def build_provider_registry(settings: Settings) -> ProviderRegistry:
    return ProviderRegistry(
        providers=[
            MockProvider(),
            OpenAICompatibleProvider(
                base_url=settings.openai_compatible_base_url,
                api_key=settings.openai_compatible_api_key,
                timeout_seconds=settings.request_timeout_seconds,
            ),
            OllamaProvider(
                base_url=settings.ollama_base_url,
                timeout_seconds=settings.request_timeout_seconds,
            ),
        ]
    )
