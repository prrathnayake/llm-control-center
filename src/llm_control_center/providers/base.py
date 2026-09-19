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


@dataclass(frozen=True)
class ProviderResponseRequest:
    provider_model: str
    input: str | list[dict[str, Any]]
    instructions: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    text: dict[str, Any] = field(default_factory=dict)
    reasoning: dict[str, Any] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    tool_choice: str | dict[str, Any] | None = None
    parallel_tool_calls: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    provider_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponseResponse:
    output_text: str
    usage: Usage
    id: str | None = None
    status: str = "completed"
    output: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def response_input_to_messages(
    input_value: str | list[dict[str, Any]],
    instructions: str | None = None,
) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    if instructions:
        messages.append(ChatMessage(role="system", content=instructions))
    if isinstance(input_value, str):
        messages.append(ChatMessage(role="user", content=input_value))
        return messages
    for item in input_value:
        role = item.get("role", "user")
        content = item.get("content", "")
        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") in {"input_text", "text"}
            ]
            content = "\n".join(part for part in text_parts if part)
        if role in {"system", "user", "assistant", "tool"} and isinstance(content, str):
            messages.append(ChatMessage(role=role, content=content))
    return messages


def response_output_from_text(text: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }
    ]


class ProviderAdapter(Protocol):
    name: str
    capabilities: ModelCapabilities

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        """Execute a chat completion call."""

    async def respond(self, request: ProviderResponseRequest) -> ProviderResponseResponse:
        """Execute a Responses-style call."""
