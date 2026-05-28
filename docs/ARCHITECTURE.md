# Architecture

## Goal

Build one central control center for LLM calls across many projects.

The gateway owns:

- project authentication
- provider credentials
- model alias routing
- provider request normalization
- response normalization
- usage logging
- error normalization
- future policy and budget controls

## Runtime flow

```text
Client project
  -> Authorization: Bearer project_api_key
  -> /v1/chat/completions
  -> auth dependency validates key
  -> ChatService validates requested model alias
  -> Router resolves alias to provider + provider model
  -> ProviderRegistry returns adapter
  -> Adapter calls provider
  -> UsageService records request/response metadata
  -> Normalized response returns to client
```

## Package layout

```text
src/llm_control_center/
  api/            FastAPI dependencies and routes
  providers/      Provider adapters and registry
  services/       Application services
  app.py          App factory
  auth.py         API key and admin auth helpers
  config.py       Environment settings
  db.py           SQLite persistence layer
  routing.py      Model alias routing
  schemas.py      Public and internal contracts
  telemetry.py    Trace IDs and usage metadata
```

## Design principles

### 1. Stable public API

Projects call the same endpoint no matter which model provider is used.

### 2. Provider names are internal

A project can request `cloud-chat`. The gateway decides that this means OpenAI, OpenRouter, Gemini, Anthropic, or another provider.

### 3. No paid APIs in tests

The `mock` provider exists so every route, CI pipeline, and local test can run without external cost.

### 4. Service layer first

FastAPI routes are thin. Routing, auth, logging, and provider execution live in dedicated modules.

### 5. Local and cloud parity

OpenAI-compatible APIs and Ollama are both adapters behind the same interface.

## Extension points

Add a provider by implementing:

```python
class MyProvider(ProviderAdapter):
    name = "my_provider"

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        ...
```

Then register it in `providers/registry.py`.

## Future production upgrades

- PostgreSQL instead of SQLite
- Redis rate limits
- Prometheus/OpenTelemetry metrics
- Langfuse-style trace export
- streaming provider passthrough
- budget governance
- provider health scoring
- fallback routing
- secret manager integration
