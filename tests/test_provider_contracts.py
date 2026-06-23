from __future__ import annotations

import asyncio

import httpx
import pytest

from llm_control_center.errors import ProviderExecutionError
from llm_control_center.providers.base import ProviderChatRequest
from llm_control_center.providers.ollama import OllamaProvider
from llm_control_center.providers.openai_compatible import OpenAICompatibleProvider
from llm_control_center.schemas import ChatMessage


def _request(messages=None, **kwargs):
    return ProviderChatRequest(
        provider_model="test-model",
        messages=messages or [ChatMessage(role="user", content="hello")],
        **kwargs,
    )


def _openai_provider(handler, *, api_key: str = "sk-test") -> OpenAICompatibleProvider:
    provider = OpenAICompatibleProvider(base_url="https://example.com", api_key=api_key)
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return provider


def _ollama_provider(handler) -> OllamaProvider:
    provider = OllamaProvider(base_url="http://localhost:11434")
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return provider


def _run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# OpenAI-compatible provider
# --------------------------------------------------------------------------- #


class TestOpenAICompatibleProvider:
    def test_happy_path_parses_response(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url == "https://example.com/v1/chat/completions"
            assert request.headers["Authorization"] == "Bearer sk-test"
            body = request.read()
            import json

            payload = json.loads(body)
            assert payload["model"] == "test-model"
            assert payload["stream"] is False
            assert payload["temperature"] == 0.7
            assert payload["messages"] == [{"role": "user", "content": "hello"}]
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "hi there"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 5,
                        "completion_tokens": 3,
                        "total_tokens": 8,
                    },
                },
            )

        provider = _openai_provider(handler)
        try:
            response = _run(provider.chat(_request(temperature=0.7)))
        finally:
            _run(provider._client.aclose())

        assert response.content == "hi there"
        assert response.finish_reason == "stop"
        assert response.usage.prompt_tokens == 5
        assert response.usage.completion_tokens == 3
        assert response.usage.total_tokens == 8

    def test_max_tokens_is_sent_when_provided(self):
        def handler(request: httpx.Request) -> httpx.Response:
            import json

            payload = json.loads(request.read())
            assert payload["max_tokens"] == 42
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
            )

        provider = _openai_provider(handler)
        try:
            response = _run(provider.chat(_request(max_tokens=42)))
        finally:
            _run(provider._client.aclose())

        assert response.content == "ok"

    def test_max_tokens_omitted_when_none(self):
        def handler(request: httpx.Request) -> httpx.Response:
            import json

            payload = json.loads(request.read())
            assert "max_tokens" not in payload
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                    "usage": {},
                },
            )

        provider = _openai_provider(handler)
        try:
            _run(provider.chat(_request()))
        finally:
            _run(provider._client.aclose())

    def test_provider_options_cannot_override_blocked_keys(self):
        def handler(request: httpx.Request) -> httpx.Response:
            import json

            payload = json.loads(request.read())
            assert payload["model"] == "test-model"
            assert payload["stream"] is False
            assert payload["messages"] == [{"role": "user", "content": "hello"}]
            assert payload["top_p"] == 0.9
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                    "usage": {},
                },
            )

        provider = _openai_provider(handler)
        try:
            _run(
                provider.chat(
                    _request(
                        provider_options={
                            "model": "hacked",
                            "messages": [],
                            "stream": True,
                            "top_p": 0.9,
                        }
                    )
                )
            )
        finally:
            _run(provider._client.aclose())

    def test_api_key_missing_raises_provider_execution_error(self):
        provider = OpenAICompatibleProvider(base_url="https://example.com", api_key="")
        with pytest.raises(ProviderExecutionError, match="API key"):
            _run(provider.chat(_request()))

    def test_http_error_raises_provider_execution_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="upstream broken")

        provider = _openai_provider(handler)
        try:
            with pytest.raises(ProviderExecutionError, match="failed"):
                _run(provider.chat(_request()))
        finally:
            _run(provider._client.aclose())

    def test_invalid_response_body_raises_provider_execution_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"unexpected": "shape"})

        provider = _openai_provider(handler)
        try:
            with pytest.raises(ProviderExecutionError, match="invalid response"):
                _run(provider.chat(_request()))
        finally:
            _run(provider._client.aclose())

    def test_finish_reason_defaults_to_stop_when_missing(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {},
                },
            )

        provider = _openai_provider(handler)
        try:
            response = _run(provider.chat(_request()))
        finally:
            _run(provider._client.aclose())

        assert response.finish_reason == "stop"


# --------------------------------------------------------------------------- #
# Ollama provider
# --------------------------------------------------------------------------- #


class TestOllamaProvider:
    def test_happy_path_parses_response(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url == "http://localhost:11434/api/chat"
            import json

            payload = json.loads(request.read())
            assert payload["model"] == "test-model"
            assert payload["stream"] is False
            assert payload["options"]["temperature"] == 0.7
            return httpx.Response(
                200,
                json={
                    "message": {"role": "assistant", "content": "ollama reply"},
                    "prompt_eval_count": 4,
                    "eval_count": 6,
                    "done": True,
                },
            )

        provider = _ollama_provider(handler)
        try:
            response = _run(provider.chat(_request(temperature=0.7)))
        finally:
            _run(provider._client.aclose())

        assert response.content == "ollama reply"
        assert response.finish_reason == "stop"
        assert response.usage.prompt_tokens == 4
        assert response.usage.completion_tokens == 6
        assert response.usage.total_tokens == 10

    def test_finish_reason_length_when_not_done(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "message": {"content": "partial"},
                    "done": False,
                },
            )

        provider = _ollama_provider(handler)
        try:
            response = _run(provider.chat(_request()))
        finally:
            _run(provider._client.aclose())

        assert response.finish_reason == "length"

    def test_max_tokens_maps_to_num_predict(self):
        def handler(request: httpx.Request) -> httpx.Response:
            import json

            payload = json.loads(request.read())
            assert payload["options"]["num_predict"] == 99
            return httpx.Response(200, json={"message": {"content": "ok"}, "done": True})

        provider = _ollama_provider(handler)
        try:
            _run(provider.chat(_request(max_tokens=99)))
        finally:
            _run(provider._client.aclose())

    def test_http_error_raises_provider_execution_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="ollama down")

        provider = _ollama_provider(handler)
        try:
            with pytest.raises(ProviderExecutionError, match="failed"):
                _run(provider.chat(_request()))
        finally:
            _run(provider._client.aclose())

    def test_missing_message_returns_empty_content(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"done": True})

        provider = _ollama_provider(handler)
        try:
            response = _run(provider.chat(_request()))
        finally:
            _run(provider._client.aclose())

        assert response.content == ""
        assert response.usage.total_tokens == 0