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
