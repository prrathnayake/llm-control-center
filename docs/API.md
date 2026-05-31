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
        "streaming": true,
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

## Usage logs

```http
GET /admin/usage?project_id=<optional>
```

Use this endpoint to inspect project-level traffic, provider routing, latency, token estimates, and errors.

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
| Admin | `/admin/*` | 60 req/min | Per IP |
| Chat completions | `/v1/chat/completions` | 30 req/min | Per API key (per project) |
| Models / Health | `/v1/models`, `/health` | 120 req/min | Per IP |

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
