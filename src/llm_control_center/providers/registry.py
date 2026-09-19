from __future__ import annotations

import inspect

from llm_control_center.config import Settings
from llm_control_center.errors import ProviderNotFoundError
from llm_control_center.providers.base import ProviderAdapter
from llm_control_center.providers.mock import MockProvider
from llm_control_center.providers.ollama import OllamaProvider
from llm_control_center.providers.openai_compatible import OpenAICompatibleProvider
from llm_control_center.providers.resilient import ResilientProviderAdapter


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

    async def aclose(self) -> None:
        """Close provider-owned clients during application shutdown."""
        for provider in self._providers.values():
            close = getattr(provider, "aclose", None)
            if not callable(close):
                continue
            result = close()
            if inspect.isawaitable(result):
                await result


def build_provider_registry(settings: Settings) -> ProviderRegistry:
    providers: list[ProviderAdapter] = [
        MockProvider(),
        OpenAICompatibleProvider(
            base_url=settings.openai_compatible_base_url,
            api_key=settings.openai_compatible_api_key,
            timeout_seconds=settings.request_timeout_seconds,
            responses_api=settings.openai_compatible_responses_api,
        ),
        OllamaProvider(
            base_url=settings.ollama_base_url,
            timeout_seconds=settings.request_timeout_seconds,
        ),
    ]
    return ProviderRegistry(
        providers=[
            ResilientProviderAdapter(
                provider,
                max_concurrency=settings.provider_max_concurrency,
                queue_timeout_seconds=settings.provider_queue_timeout_seconds,
                failure_threshold=settings.provider_failure_threshold,
                cooldown_seconds=settings.provider_circuit_cooldown_seconds,
            )
            for provider in providers
        ]
    )
