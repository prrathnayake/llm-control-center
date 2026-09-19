from __future__ import annotations

import asyncio

import pytest

from llm_control_center.errors import ProviderExecutionError
from llm_control_center.providers.base import ProviderChatRequest, ProviderChatResponse
from llm_control_center.providers.resilient import ResilientProviderAdapter
from llm_control_center.schemas import ChatMessage, ModelCapabilities, Usage


class _Provider:
    name = "test"
    capabilities = ModelCapabilities()

    def __init__(self) -> None:
        self.calls = 0
        self.release = asyncio.Event()

    async def chat(self, _request):
        self.calls += 1
        await self.release.wait()
        return ProviderChatResponse(content="ok", usage=Usage())

    async def respond(self, _request):
        raise ProviderExecutionError("failed")


def _request() -> ProviderChatRequest:
    return ProviderChatRequest(
        provider_model="model", messages=[ChatMessage(role="user", content="hi")]
    )


def test_provider_bulkhead_rejects_excess_waiter() -> None:
    async def exercise() -> None:
        provider = _Provider()
        wrapped = ResilientProviderAdapter(
            provider,
            max_concurrency=1,
            queue_timeout_seconds=0.05,
            failure_threshold=2,
            cooldown_seconds=10,
        )
        first = asyncio.create_task(wrapped.chat(_request()))
        await asyncio.sleep(0)
        with pytest.raises(ProviderExecutionError, match="concurrency"):
            await wrapped.chat(_request())
        provider.release.set()
        assert (await first).content == "ok"

    asyncio.run(exercise())


def test_provider_circuit_opens_after_threshold() -> None:
    async def exercise() -> None:
        provider = _Provider()
        wrapped = ResilientProviderAdapter(
            provider,
            max_concurrency=1,
            queue_timeout_seconds=1,
            failure_threshold=2,
            cooldown_seconds=10,
        )
        request = object()
        for _ in range(2):
            with pytest.raises(ProviderExecutionError, match="failed"):
                await wrapped.respond(request)  # type: ignore[arg-type]
        with pytest.raises(ProviderExecutionError, match="circuit"):
            await wrapped.respond(request)  # type: ignore[arg-type]

    asyncio.run(exercise())
