from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ChatRole = Literal["system", "user", "assistant", "tool"]
FinishReason = Literal["stop", "length", "tool_calls", "content_filter", "error"]


class ChatMessage(BaseModel):
    role: ChatRole
    content: str
    name: str | None = None


class RequestMetadata(BaseModel):
    project: str | None = None
    workflow: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    temperature: float | None = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    stream: bool = False
    provider_options: dict[str, Any] = Field(default_factory=dict)
    metadata: RequestMetadata = Field(default_factory=RequestMetadata)


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: FinishReason = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    provider: str
    trace_id: str
    choices: list[ChatChoice]
    usage: Usage


class ModelCapabilities(BaseModel):
    chat: bool = True
    streaming: bool = False
    tools: bool = False
    vision: bool = False


class PublicModel(BaseModel):
    id: str
    provider: str
    capabilities: ModelCapabilities


class ModelsResponse(BaseModel):
    data: list[PublicModel]


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: str


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=lambda: ["chat:write"])


class ApiKeyResponse(BaseModel):
    id: str
    project_id: str
    name: str
    prefix: str
    scopes: list[str]
    created_at: str


class CreateApiKeyResponse(BaseModel):
    api_key: str
    key: ApiKeyResponse


class UsageLogResponse(BaseModel):
    id: int
    trace_id: str
    project_id: str
    model_alias: str
    provider: str
    provider_model: str
    status: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    error: str | None
    created_at: str


class UsageLogsResponse(BaseModel):
    data: list[UsageLogResponse]
