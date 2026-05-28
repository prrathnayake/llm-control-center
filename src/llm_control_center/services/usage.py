from __future__ import annotations

from llm_control_center.db import SQLiteStore
from llm_control_center.schemas import Usage


class UsageService:
    def __init__(self, *, store: SQLiteStore) -> None:
        self.store = store

    def record(
        self,
        *,
        trace_id: str,
        project_id: str,
        model_alias: str,
        provider: str,
        provider_model: str,
        status: str,
        latency_ms: int,
        usage: Usage,
        error: str | None = None,
    ) -> dict:
        return self.store.insert_usage_log(
            trace_id=trace_id,
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
        )
