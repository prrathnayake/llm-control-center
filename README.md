# LLM Control Center

Central LLM gateway for all of your LLM-powered projects.

Your projects call one internal server. This server authenticates project API keys, normalizes requests, routes to cloud or local providers, records usage, and returns one stable response shape.

```text
Your projects
  -> LLM Control Center API
    -> router + policy + logging
      -> provider adapters
        -> OpenAI-compatible APIs / Ollama / mock / future providers
```

## What is included

- FastAPI backend
- Project API key creation
- Stable `/v1/chat/completions` endpoint
- OpenAI-style `/v1/responses` endpoint for agent and structured-output requests
- Provider abstraction layer
- Mock provider for safe tests
- OpenAI-compatible provider adapter
- Ollama provider adapter
- SQLite persistence for projects, keys, and usage logs
- Production-ready Postgres storage path for concurrent activity tracking
- GitHub Actions CI pipeline
- Unit/API tests that do **not** call paid providers
- Dockerfile and Docker Compose
- Architecture and operations documentation

## Why this design

Client apps should not know provider secrets or real model names. They send a stable alias such as `default-chat`, `local-chat`, or `cloud-chat`. The gateway maps that alias to an internal provider and provider model.

This lets you swap providers without changing your other projects.

## Quick start

```bash
cp .env.example .env
python -m pip install -e .[dev]
make test
make dev
```

Create a project:

```bash
curl -X POST http://localhost:8080/admin/projects \
  -H "X-Admin-Token: change-me-admin-token" \
  -H "Content-Type: application/json" \
  -d '{"name":"social-agent","description":"Social media agent platform"}'
```

Create a project API key:

```bash
curl -X POST http://localhost:8080/admin/projects/<project_id>/api-keys \
  -H "X-Admin-Token: change-me-admin-token" \
  -H "Content-Type: application/json" \
  -d '{"name":"dev-key","scopes":["chat:write"]}'
```

Call the gateway:

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer <project_api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"default-chat",
    "messages":[{"role":"user","content":"Say hello from the gateway"}],
    "metadata":{"workflow":"smoke-test"}
  }'
```

Call the Responses endpoint:

```bash
curl -X POST http://localhost:8080/v1/responses \
  -H "Authorization: Bearer <project_api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"default-chat",
    "input":"Return a short JSON status for this workspace agent",
    "text":{"format":{"type":"json_schema","schema":{"type":"object"}}},
    "metadata":{"workflow":"agent-run","session_id":"sess_123"}
  }'
```

## Model routing

Routes are configured using `LLM_CC_MODEL_ROUTES`:

```json
{
  "default-chat": {"provider": "mock", "provider_model": "mock-smart"},
  "local-chat": {"provider": "ollama", "provider_model": "llama3.1"},
  "cloud-chat": {
    "provider": "openai_compatible",
    "provider_model": "gpt-4o-mini",
    "api": "responses"
  }
}
```

Your projects only use aliases. Real provider models stay inside this server.

## Test strategy

Tests use the mock provider and isolated temporary SQLite databases. CI runs:

1. dependency install
2. Ruff lint
3. unit/API tests with coverage gate
4. package import smoke test

No test calls OpenAI, OpenRouter, Anthropic, Gemini, Ollama, or any paid API.

## Main endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/admin/projects` | Create project |
| `POST` | `/admin/projects/{project_id}/api-keys` | Create project API key |
| `GET` | `/admin/usage` | View usage logs |
| `GET` | `/v1/models` | List exposed model aliases |
| `POST` | `/v1/chat/completions` | Normalized chat completion |
| `POST` | `/v1/responses` | Normalized agent/structured-output response |

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/API.md`](docs/API.md)
- [`docs/TESTING.md`](docs/TESTING.md)
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/adr/0001-llm-gateway.md`](docs/adr/0001-llm-gateway.md)

## Repository rules

See [`AGENTS.md`](AGENTS.md) for maintainability rules for future coding agents.
