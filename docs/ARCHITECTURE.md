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
  api/            FastAPI dependencies, routes, and middleware
    deps.py       Auth dependencies (admin token, project principal)
    middleware.py Security headers, docs protection, rate limiting
    routes/       health, admin, and chat (/v1) route modules
  providers/      Provider adapters and registry
  services/       Application services (api_keys, chat, models, projects, usage)
  app.py          App factory
  auth.py         API key and admin auth primitives
  cli.py          `llmcc` console client (admin API + models + health)
  config.py       Environment settings
  db.py           SQLAlchemy Core persistence (SQLite/PostgreSQL)
  errors.py       Exception hierarchy
  logging_config.py  structlog setup
  middleware.py   Correlation ID middleware
  routing.py      Model alias routing
  schemas.py      Public and internal contracts
  telemetry.py    Trace IDs and timing helpers
```

## Design principles

### 1. Stable public API

Projects call the same endpoint no matter which model provider is used.

### 2. Provider routing is internal

A project can request `cloud-chat`. The gateway decides that this means OpenAI, OpenRouter, Gemini, Anthropic, or another provider. Clients never need to know the provider to make a request and never send provider model names. The gateway may surface the resolved provider name in responses (`GET /v1/models`, `ChatCompletionResponse.provider`, `/admin/usage`) as informational observability metadata; the routing decision itself stays centralized.

### 3. No paid APIs in tests

The `mock` provider exists so every route, CI pipeline, and local test can run without external cost.

### 4. Service layer first

FastAPI routes are thin. Routing, auth, logging, provider execution, project/usage admin, and model listing live in dedicated service modules (`services/`). Routes only translate domain errors to HTTP status codes.

### 5. Local and cloud parity

OpenAI-compatible APIs and Ollama are both adapters behind the same interface.

## Extension points

Add a provider by implementing the `ProviderAdapter` Protocol in `providers/base.py`:

```python
class MyProvider(ProviderAdapter):
    name = "my_provider"

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        ...
```

Then register an instance for it in `build_provider_registry(settings)` in `providers/registry.py`. (The registry is built in code rather than via entry-point plugins; add a call there and a contract test under `tests/test_provider_contracts.py` with a fake HTTP transport.)

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
