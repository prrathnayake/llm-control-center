from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from llm_control_center.errors import ProviderExecutionError
from llm_control_center.providers.base import (
    ProviderAdapter,
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderResponseRequest,
    ProviderResponseResponse,
)


class ResilientProviderAdapter:
    """Bound provider concurrency and fail fast while an upstream is unhealthy."""

    def __init__(
        self,
        delegate: ProviderAdapter,
        *,
        max_concurrency: int,
        queue_timeout_seconds: float,
        failure_threshold: int,
        cooldown_seconds: float,
    ) -> None:
        self._delegate = delegate
        self.name = delegate.name
        self.capabilities = delegate.capabilities
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._queue_timeout_seconds = queue_timeout_seconds
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._consecutive_failures = 0
        self._circuit_opened_at = 0.0
        self._state_lock = asyncio.Lock()

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        return await self._execute(lambda: self._delegate.chat(request))

    async def respond(self, request: ProviderResponseRequest) -> ProviderResponseResponse:
        return await self._execute(lambda: self._delegate.respond(request))

    async def _execute(self, operation: Callable[[], Awaitable[Any]]) -> Any:
        await self._require_closed_circuit()
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(), timeout=self._queue_timeout_seconds
            )
        except TimeoutError as exc:
            raise ProviderExecutionError("provider concurrency limit reached") from exc
        try:
            result = await operation()
        except asyncio.CancelledError:
            raise
        except Exception:
            async with self._state_lock:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._failure_threshold:
                    self._circuit_opened_at = time.monotonic()
            raise
        else:
            async with self._state_lock:
                self._consecutive_failures = 0
                self._circuit_opened_at = 0.0
            return result
        finally:
            self._semaphore.release()

    async def _require_closed_circuit(self) -> None:
        async with self._state_lock:
            if not self._circuit_opened_at:
                return
            elapsed = time.monotonic() - self._circuit_opened_at
            if elapsed >= self._cooldown_seconds:
                self._circuit_opened_at = 0.0
                self._consecutive_failures = 0
                return
            raise ProviderExecutionError("provider circuit is open")

    async def aclose(self) -> None:
        close = getattr(self._delegate, "aclose", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result
