from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from llm_control_center.schemas import ChatMessage, ModelCapabilities, Usage


@dataclass(frozen=True)
class ProviderChatRequest:
    provider_model: str
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    provider_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderChatResponse:
    content: str
    usage: Usage
    finish_reason: str = "stop"
    raw: dict[str, Any] = field(default_factory=dict)


class ProviderAdapter(Protocol):
    name: str
    capabilities: ModelCapabilities

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        """Execute a chat completion call."""
