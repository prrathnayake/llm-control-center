# API Reference

## Admin auth

Admin routes require:

```http
X-Admin-Token: <LLM_CC_ADMIN_TOKEN>
```

## Project auth

Project routes require:

```http
Authorization: Bearer <project_api_key>
```

## Create project

```http
POST /admin/projects
```

Request:

```json
{
  "name": "social-agent",
  "description": "Social media agent platform"
}
```

Response:

```json
{
  "id": "...",
  "name": "social-agent",
  "description": "Social media agent platform",
  "created_at": "..."
}
```

## Create API key

```http
POST /admin/projects/{project_id}/api-keys
```

Request:

```json
{
  "name": "dev-key",
  "scopes": ["chat:write"]
}
```

Response includes the raw key once:

```json
{
  "api_key": "llmcc_...",
  "key": {
    "id": "...",
    "project_id": "...",
    "name": "dev-key",
    "prefix": "llmcc_abc123",
    "scopes": ["chat:write"],
    "created_at": "..."
  }
}
```

## List projects

```http
GET /admin/projects
```

Returns a list of projects (newest first by id).

## Get project

```http
GET /admin/projects/{project_id}
```

Response:

```json
{
  "id": "...",
  "name": "social-agent",
  "description": "Social media agent platform",
  "created_at": "..."
}
```

Returns `404` if the project does not exist.

## List project API keys

```http
GET /admin/projects/{project_id}/api-keys
```

Returns the project's API keys. `key_hash` is never included.

## Revoke API key

```http
DELETE /admin/projects/{project_id}/api-keys/{key_id}
```

Hard-deletes the API key. Returns `204 No Content` on success, `404` if the key does not exist under that project. Keys cannot be recovered after revocation.

## List models

```http
GET /v1/models
```

Response:

```json
{
  "data": [
    {
      "id": "default-chat",
      "provider": "mock",
      "capabilities": {
        "chat": true,
        "streaming": false,
        "tools": false,
        "vision": false
      }
    }
  ]
}
```

## Chat completions

```http
POST /v1/chat/completions
```

Request:

```json
{
  "model": "default-chat",
  "messages": [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello"}
  ],
  "temperature": 0.2,
  "max_tokens": 1000,
  "metadata": {
    "workflow": "demo",
    "session_id": "abc"
  }
}
```

Response:

```json
{
  "id": "chatcmpl_...",
  "object": "chat.completion",
  "created": 1760000000,
  "model": "default-chat",
  "provider": "mock",
  "trace_id": "tr_...",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "..."},
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 4,
    "completion_tokens": 8,
    "total_tokens": 12
  }
}
```

## Responses

```http
POST /v1/responses
```

Use this endpoint for agent-style requests, structured outputs, and provider-neutral
middleware calls. Project API keys need `responses:write`; keys with `chat:write`
are accepted during migration.

Request:

```json
{
  "model": "default-chat",
  "input": "Classify this agent event",
  "instructions": "Return only JSON.",
  "temperature": 0.2,
  "max_output_tokens": 1000,
  "text": {
    "format": {
      "type": "json_schema",
      "schema": {"type": "object"},
      "strict": true
    }
  },
  "reasoning": {"effort": "low"},
  "tools": [],
  "tool_choice": "auto",
  "parallel_tool_calls": true,
  "metadata": {
    "workflow": "agent-run",
    "session_id": "sess_123",
    "user_id": "workspace-user"
  },
  "provider_options": {
    "top_p": 0.9
  }
}
```

Response:

```json
{
  "id": "resp_...",
  "object": "response",
  "status": "completed",
  "created_at": 1760000000,
  "model": "default-chat",
  "provider": "mock",
  "trace_id": "tr_...",
  "output": [
    {
      "type": "message",
      "role": "assistant",
      "status": "completed",
      "content": [
        {"type": "output_text", "text": "{\"ok\":true}", "annotations": []}
      ]
    }
  ],
  "output_text": "{\"ok\":true}",
  "usage": {
    "prompt_tokens": 4,
    "completion_tokens": 8,
    "total_tokens": 12
  },
  "metadata": {
    "workflow": "agent-run",
    "session_id": "sess_123"
  }
}
```

Clients never send provider model names. `model` is always a gateway alias.

## Usage logs

```http
GET /admin/usage?project_id=<optional>
```

Use this endpoint to inspect project-level traffic, provider routing, latency, token estimates, and errors.

Additional filters:

| Query parameter | Description |
|---|---|
| `endpoint` | Filter by `/v1/chat/completions` or `/v1/responses` |
| `status` | Filter by `success` or `error` |
| `workflow` | Filter by metadata workflow |
| `session_id` | Filter by metadata session ID |
| `user_id` | Filter by metadata user ID |
| `created_after` | ISO timestamp lower bound |
| `created_before` | ISO timestamp upper bound |

## Rate limiting

All endpoints are subject to sliding-window rate limits. When a limit is exceeded, the API returns `429 Too Many Requests` with a `Retry-After` header.

### Rate limit headers

Every response includes:

| Header | Description |
|---|---|
| `X-RateLimit-Limit` | Maximum requests allowed in the window |
| `X-RateLimit-Remaining` | Requests remaining in the current window |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |

### Limits by endpoint group

| Group | Endpoints | Default limit | Scope |
|---|---|---|---|
| Admin | `/admin/*` | 60 req/min | Per client IP |
| LLM requests | `/v1/chat/completions`, `/v1/responses` | 30 req/min | Per API key (per project) |
| Models / Health | `/v1/models`, `/health` | 120 req/min (shared pool) | Per client IP |

The Models and Health endpoints share one bucket per client IP (so `GET /v1/models` and `GET /health` draw from the same 120 req/min allowance). The client IP is resolved from the leftmost `X-Forwarded-For` header value when present (e.g. behind a reverse proxy), falling back to the direct connection IP.

### Configuration

Rate limits are configurable via environment variables (prefix `LLM_CC_`):

| Variable | Default | Description |
|---|---|---|
| `LLM_CC_RATE_LIMIT_ADMIN` | `60` | Admin endpoints: requests per minute |
| `LLM_CC_RATE_LIMIT_CHAT` | `30` | Chat completions: requests per minute per project |
| `LLM_CC_RATE_LIMIT_MODELS` | `120` | Models and health: requests per minute |
| `LLM_CC_MAX_REQUEST_SIZE_MB` | `1` | Maximum request body size in MB |

Set any rate limit to `0` to disable rate limiting for that group.

### Request size limit

Requests exceeding `LLM_CC_MAX_REQUEST_SIZE_MB` (default 1 MB) are rejected with `413 Payload Too Large`.
