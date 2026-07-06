from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from fastapi.concurrency import run_in_threadpool

from llm_control_center.db import Store
from llm_control_center.schemas import RequestMetadata, Usage


class UsageService:
    def __init__(self, *, store: Store, queue_size: int = 1000) -> None:
        self.store = store
        self._queue: asyncio.Queue[dict[str, Any]] | None = None
        self._worker: asyncio.Task | None = None
        self._queue_size = queue_size

    async def start(self) -> None:
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._queue_size)
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run_worker())

    async def stop(self) -> None:
        await self.flush()
        if self._worker is not None:
            self._worker.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker
            self._worker = None

    async def flush(self) -> None:
        if self._queue is not None:
            await self._queue.join()

    async def _run_worker(self) -> None:
        assert self._queue is not None
        while True:
            item = await self._queue.get()
            try:
                await run_in_threadpool(self.record, **item)
            finally:
                self._queue.task_done()

    async def record_async(self, **kwargs) -> None:
        if self._queue is None:
            await run_in_threadpool(self.record, **kwargs)
            return
        await self._queue.put(kwargs)

    def record(
        self,
        *,
        trace_id: str,
        endpoint: str = "/v1/chat/completions",
        request_kind: str = "chat",
        project_id: str,
        model_alias: str,
        provider: str,
        provider_model: str,
        status: str,
        latency_ms: int,
        usage: Usage,
        error: str | None = None,
        metadata: RequestMetadata | None = None,
    ) -> dict:
        metadata = metadata or RequestMetadata()
        return self.store.insert_usage_log(
            trace_id=trace_id,
            endpoint=endpoint,
            request_kind=request_kind,
            project_id=project_id,
            model_alias=model_alias,
            provider=provider,
            provider_model=provider_model,
            status=status,
            latency_ms=latency_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            error=error,
            workflow=metadata.workflow,
            session_id=metadata.session_id,
            user_id=metadata.user_id,
            tags=metadata.tags,
        )
