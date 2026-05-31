from __future__ import annotations

from typing import Any

import httpx
import structlog

from llm_control_center.errors import ProviderExecutionError
from llm_control_center.providers.base import ProviderChatRequest, ProviderChatResponse
from llm_control_center.schemas import ModelCapabilities, Usage

logger = structlog.stdlib.get_logger(__name__)


class OpenAICompatibleProvider:
    """Adapter for OpenAI-compatible `/v1/chat/completions` providers.

    Works with OpenAI, OpenRouter, Groq, Together, LM Studio, vLLM, and similar APIs.
    """

    name = "openai_compatible"
    capabilities = ModelCapabilities(chat=True, streaming=False, tools=True, vision=True)

    def __init__(self, *, base_url: str, api_key: str, timeout_seconds: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        if not self.api_key:
            raise ProviderExecutionError("OpenAI-compatible provider API key is not configured")

        payload: dict[str, Any] = {
            "model": request.provider_model,
            "messages": [message.model_dump(exclude_none=True) for message in request.messages],
            "temperature": request.temperature,
            "stream": False,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        blocked_keys = {"model", "messages", "stream"}
        for key, value in request.provider_options.items():
            if key not in blocked_keys:
                payload[key] = value

        try:
            client = self._get_client()
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(
                "provider_error",
                provider="openai_compatible",
                model=request.provider_model,
                error=str(exc),
            )
            raise ProviderExecutionError(f"OpenAI-compatible provider failed: {exc}") from exc

        data = response.json()
        try:
            choice = data["choices"][0]
            content = choice["message"].get("content", "")
            finish_reason = choice.get("finish_reason", "stop") or "stop"
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderExecutionError(
                "OpenAI-compatible provider returned invalid response"
            ) from exc

        usage_data = data.get("usage") or {}
        prompt_tokens = int(usage_data.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage_data.get("completion_tokens", 0) or 0)
        total = int(usage_data.get("total_tokens", 0) or 0)
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
        )
        logger.debug(
            "provider_call",
            provider="openai_compatible",
            model=request.provider_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
        )
        return ProviderChatResponse(
            content=content,
            usage=usage,
            finish_reason=finish_reason,
            raw=data,
        )
