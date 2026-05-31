from __future__ import annotations

from llm_control_center.providers.base import ProviderChatRequest
from llm_control_center.providers.mock import MockProvider
from llm_control_center.schemas import ChatMessage, coerce_finish_reason


def test_coerce_finish_reason_valid():
    assert coerce_finish_reason("stop") == "stop"
    assert coerce_finish_reason("length") == "length"
    assert coerce_finish_reason("tool_calls") == "tool_calls"
    assert coerce_finish_reason("content_filter") == "content_filter"
    assert coerce_finish_reason("error") == "error"


def test_coerce_finish_reason_unknown_defaults_to_stop():
    assert coerce_finish_reason("unknown_reason") == "stop"
    assert coerce_finish_reason("") == "stop"
    assert coerce_finish_reason("null") == "stop"


def test_provider_options_cannot_override_model():
    request = ProviderChatRequest(
        provider_model="gpt-4",
        messages=[ChatMessage(role="user", content="hello")],
        provider_options={
            "model": "hacked-model",
            "messages": [],
            "stream": True,
            "temperature": 0.5,
        },
    )
    payload = {
        "model": request.provider_model,
        "messages": [m.model_dump(exclude_none=True) for m in request.messages],
        "temperature": request.temperature,
        "stream": False,
    }
    blocked_keys = {"model", "messages", "stream"}
    for key, value in request.provider_options.items():
        if key not in blocked_keys:
            payload[key] = value
    assert payload["model"] == "gpt-4"
    assert payload["messages"] != []
    assert payload["stream"] is False
    assert payload["temperature"] == 0.5


def test_provider_options_can_add_extra_fields():
    request = ProviderChatRequest(
        provider_model="gpt-4",
        messages=[ChatMessage(role="user", content="hello")],
        provider_options={"top_p": 0.9, "frequency_penalty": 0.5},
    )
    payload = {
        "model": request.provider_model,
        "messages": [m.model_dump(exclude_none=True) for m in request.messages],
        "temperature": request.temperature,
        "stream": False,
    }
    blocked_keys = {"model", "messages", "stream"}
    for key, value in request.provider_options.items():
        if key not in blocked_keys:
            payload[key] = value
    assert payload["top_p"] == 0.9
    assert payload["frequency_penalty"] == 0.5
    assert payload["model"] == "gpt-4"


def test_mock_provider_does_not_claim_streaming():
    provider = MockProvider()
    assert provider.capabilities.streaming is False
