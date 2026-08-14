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
- activity filtering for agent workflows and sessions
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

`POST /v1/responses` follows the same flow through `ResponseService`. It accepts
agent-style input, structured-output configuration, tool declarations, reasoning
options, and metadata, then routes through `ProviderAdapter.respond()`.

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

Routes may declare an internal `api` mode such as `chat_completions` or
`responses`. This is a gateway/provider concern only; clients continue to send
the alias.

### 3. No paid APIs in tests

The `mock` provider exists so every route, CI pipeline, and local test can run without external cost.

### 4. Service layer first

FastAPI routes are thin. Routing, auth, logging, provider execution, project/usage admin, and model listing live in dedicated service modules (`services/`). Routes only translate domain errors to HTTP status codes.

### 5. Local and cloud parity

OpenAI-compatible APIs and Ollama are both adapters behind the same interface.

### 6. Activity logging off the request path

Usage/activity records are enqueued through `UsageService` and written by a
bounded async worker. Admin usage reads flush the queue first, so monitoring sees
recent records without forcing provider calls to wait on every database write.
Every queued record is first persisted to a local SQLite spool. Successful
database writes acknowledge and remove the receipt; pending receipts replay on
restart, transient failures retry with bounded backoff, and exhausted records
remain as explicit dead letters. Usage `trace_id` is unique and replay-safe.

### 7. Bounded provider execution

Every provider is wrapped by a concurrency bulkhead and circuit breaker. The
bulkhead bounds active calls and queue wait time. Repeated upstream failures open
the circuit for a configured cooldown, preventing an unhealthy provider from
consuming all gateway capacity. Provider-owned HTTP clients close during the
application lifespan shutdown.

### 8. Authentication-aware ingress controls

Chat rate-limit buckets use the authenticated API-key ID, never raw credential
text. Invalid or rotating credentials share a client-IP pre-authentication
bucket. Forwarding headers are ignored unless `LLM_CC_TRUST_PROXY_HEADERS=true`.
Buckets are atomically consumed in the configured SQL store, so replica count
does not multiply allowances or erase them on gateway restart.
The middleware validates declared length and actual body bytes, and public
schemas cap collection sizes, metadata, token requests, and free text.

## Extension points

Add a provider by implementing the `ProviderAdapter` Protocol in `providers/base.py`:

```python
class MyProvider(ProviderAdapter):
    name = "my_provider"

    async def chat(self, request: ProviderChatRequest) -> ProviderChatResponse:
        ...
```

Then register an instance for it in `build_provider_registry(settings)` in `providers/registry.py`. (The registry is built in code rather than via entry-point plugins; add a call there and a contract test under `tests/test_provider_contracts.py` with a fake HTTP transport.)

Providers should implement both:

- `chat(request: ProviderChatRequest)` for `/v1/chat/completions`
- `respond(request: ProviderResponseRequest)` for `/v1/responses`

Providers without a native Responses API can convert response input into chat
messages and return a normalized response output.

## Future production upgrades

- PostgreSQL as the production database for concurrent agent activity
- Redis rate-limit storage if deployments require sliding windows instead of SQL fixed windows
- Prometheus/OpenTelemetry metrics
- Langfuse-style trace export
- streaming provider passthrough
- budget governance
- weighted provider health scoring and automatic alias fallback
- fallback routing
- secret manager integration
