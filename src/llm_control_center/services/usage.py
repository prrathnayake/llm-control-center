from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool

from llm_control_center.db import Store
from llm_control_center.schemas import RequestMetadata, Usage

logger = structlog.stdlib.get_logger(__name__)


class UsageService:
    def __init__(
        self,
        *,
        store: Store,
        queue_size: int = 1000,
        spool_path: str | Path | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.store = store
        self._queue: asyncio.Queue[dict[str, Any]] | None = None
        self._worker: asyncio.Task | None = None
        self._queue_size = queue_size
        self._spool_path = Path(spool_path) if spool_path else None
        self._max_attempts = max_attempts

    async def start(self) -> None:
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._queue_size)
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run_worker())
        if self._spool_path is not None:
            pending = await run_in_threadpool(self._load_spooled)
            for item in pending:
                await self._queue.put(item)

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
            spool_id = item.pop("_spool_id", None)
            attempts = int(item.pop("_attempts", 0) or 0)
            try:
                while attempts < self._max_attempts:
                    try:
                        await run_in_threadpool(self.record, **item)
                    except Exception as exc:
                        attempts += 1
                        logger.exception(
                            "usage_record_failed",
                            trace_id=item.get("trace_id"),
                            project_id=item.get("project_id"),
                            attempt=attempts,
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                        if spool_id is not None:
                            await run_in_threadpool(
                                self._mark_spool_attempt,
                                spool_id,
                                attempts,
                                str(exc),
                            )
                        if attempts >= self._max_attempts:
                            break
                        await asyncio.sleep(min(0.05 * (2 ** (attempts - 1)), 0.5))
                    else:
                        if spool_id is not None:
                            await run_in_threadpool(self._delete_spooled, spool_id)
                        break
            finally:
                self._queue.task_done()

    async def record_async(self, **kwargs) -> None:
        if self._queue is None:
            await run_in_threadpool(self.record, **kwargs)
            return
        item = dict(kwargs)
        if self._spool_path is not None:
            spool_id = uuid.uuid4().hex
            await run_in_threadpool(self._persist_spooled, spool_id, item)
            item["_spool_id"] = spool_id
            item["_attempts"] = 0
        await self._queue.put(item)

    @contextmanager
    def _connect_spool(self) -> Iterator[sqlite3.Connection]:
        assert self._spool_path is not None
        self._spool_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._spool_path, timeout=10)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS usage_spool ("
            "id TEXT PRIMARY KEY,payload TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,"
            "last_error TEXT,status TEXT NOT NULL DEFAULT 'pending')"
        )
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _persist_spooled(self, spool_id: str, item: dict[str, Any]) -> None:
        payload = dict(item)
        usage = payload.get("usage")
        metadata = payload.get("metadata")
        if isinstance(usage, Usage):
            payload["usage"] = usage.model_dump()
        if isinstance(metadata, RequestMetadata):
            payload["metadata"] = metadata.model_dump()
        with self._connect_spool() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO usage_spool(id,payload) VALUES(?,?)",
                (spool_id, json.dumps(payload, ensure_ascii=True, default=str)),
            )

    def _load_spooled(self) -> list[dict[str, Any]]:
        with self._connect_spool() as connection:
            rows = connection.execute(
                "SELECT id,payload,attempts FROM usage_spool WHERE status='pending' ORDER BY rowid"
            ).fetchall()
        items: list[dict[str, Any]] = []
        for spool_id, raw_payload, attempts in rows:
            payload = json.loads(raw_payload)
            payload["usage"] = Usage.model_validate(payload.get("usage") or {})
            payload["metadata"] = RequestMetadata.model_validate(
                payload.get("metadata") or {}
            )
            payload["_spool_id"] = spool_id
            payload["_attempts"] = attempts
            items.append(payload)
        return items

    def _mark_spool_attempt(self, spool_id: str, attempts: int, error: str) -> None:
        status = "dead_letter" if attempts >= self._max_attempts else "pending"
        with self._connect_spool() as connection:
            connection.execute(
                "UPDATE usage_spool SET attempts=?,last_error=?,status=? WHERE id=?",
                (attempts, error[:1000], status, spool_id),
            )

    def _delete_spooled(self, spool_id: str) -> None:
        with self._connect_spool() as connection:
            connection.execute("DELETE FROM usage_spool WHERE id=?", (spool_id,))

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
        if isinstance(usage, dict):
            usage = Usage.model_validate(usage)
        if isinstance(metadata, dict):
            metadata = RequestMetadata.model_validate(metadata)
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
