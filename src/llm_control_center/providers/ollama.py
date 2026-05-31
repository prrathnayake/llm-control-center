from __future__ import annotations

from typing import Any

import httpx

from llm_control_center.errors import ProviderExecutionError
from llm_control_center.providers.base import ProviderChatRequest, ProviderChatResponse
from llm_control_center.schemas import ModelCapabilities, Usage


class OllamaProvider:
    """Adapter for local Ollama `/api/chat`."""

    name = "ollama"
    capabilities = ModelCapabilities(chat=True, streaming=False, tools=False, vision=False)

    def __init__(self, *, base_url: str, timeout_seconds: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        payload: dict[str, Any] = {
            "model": request.provider_model,
            "messages": [message.model_dump(exclude_none=True) for message in request.messages],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                **request.provider_options,
            },
        }
        if request.max_tokens is not None:
            payload["options"]["num_predict"] = request.max_tokens

        try:
            client = self._get_client()
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderExecutionError(f"Ollama provider failed: {exc}") from exc

        data = response.json()
        message = data.get("message") or {}
        content = message.get("content", "")
        prompt_tokens = int(data.get("prompt_eval_count", 0) or 0)
        completion_tokens = int(data.get("eval_count", 0) or 0)
        return ProviderChatResponse(
            content=content,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            finish_reason="stop" if data.get("done", True) else "length",
            raw=data,
        )
