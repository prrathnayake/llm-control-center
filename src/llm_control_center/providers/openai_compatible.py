from __future__ import annotations

from typing import Any

import httpx

from llm_control_center.errors import ProviderExecutionError
from llm_control_center.providers.base import ProviderChatRequest, ProviderChatResponse
from llm_control_center.schemas import ModelCapabilities, Usage


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

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        if not self.api_key:
            raise ProviderExecutionError("OpenAI-compatible provider API key is not configured")

        payload: dict[str, Any] = {
            "model": request.provider_model,
            "messages": [message.model_dump(exclude_none=True) for message in request.messages],
            "temperature": request.temperature,
            "stream": False,
            **request.provider_options,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
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
        usage = Usage(
            prompt_tokens=int(usage_data.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage_data.get("completion_tokens", 0) or 0),
            total_tokens=int(usage_data.get("total_tokens", 0) or 0),
        )
        return ProviderChatResponse(
            content=content,
            usage=usage,
            finish_reason=finish_reason,
            raw=data,
        )
