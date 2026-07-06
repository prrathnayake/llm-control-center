from __future__ import annotations

from typing import Any

import httpx
import structlog

from llm_control_center.errors import ProviderExecutionError
from llm_control_center.providers.base import (
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderResponseRequest,
    ProviderResponseResponse,
    response_input_to_messages,
    response_output_from_text,
)
from llm_control_center.schemas import ModelCapabilities, Usage

logger = structlog.stdlib.get_logger(__name__)


class OllamaProvider:
    """Adapter for local Ollama `/api/chat`."""

    name = "ollama"
    capabilities = ModelCapabilities(
        chat=True,
        responses=True,
        streaming=False,
        tools=False,
        vision=False,
    )

    def __init__(self, *, base_url: str, timeout_seconds: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        blocked_keys = {"model", "messages", "stream"}
        payload: dict[str, Any] = {
            "model": request.provider_model,
            "messages": [message.model_dump(exclude_none=True) for message in request.messages],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                **{k: v for k, v in request.provider_options.items() if k not in blocked_keys},
            },
        }
        if request.max_tokens is not None:
            payload["options"]["num_predict"] = request.max_tokens

        try:
            client = self._get_client()
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(
                "provider_error",
                provider="ollama",
                model=request.provider_model,
                error=str(exc),
            )
            raise ProviderExecutionError(f"Ollama provider failed: {exc}") from exc

        data = response.json()
        message = data.get("message") or {}
        content = message.get("content", "")
        prompt_tokens = int(data.get("prompt_eval_count", 0) or 0)
        completion_tokens = int(data.get("eval_count", 0) or 0)
        total = prompt_tokens + completion_tokens
        logger.debug(
            "provider_call",
            provider="ollama",
            model=request.provider_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
        )
        return ProviderChatResponse(
            content=content,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total,
            ),
            finish_reason="stop" if data.get("done", True) else "length",
            raw=data,
        )

    async def respond(self, request: ProviderResponseRequest) -> ProviderResponseResponse:
        chat_response = await self.chat(
            ProviderChatRequest(
                provider_model=request.provider_model,
                messages=response_input_to_messages(request.input, request.instructions),
                temperature=request.temperature,
                max_tokens=request.max_output_tokens,
                provider_options=request.provider_options,
            )
        )
        return ProviderResponseResponse(
            output_text=chat_response.content,
            output=response_output_from_text(chat_response.content),
            usage=chat_response.usage,
            raw=chat_response.raw,
        )
