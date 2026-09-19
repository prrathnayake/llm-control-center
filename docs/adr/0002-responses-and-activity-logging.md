# ADR 0002: Responses endpoint and activity logging

## Status

Accepted

## Context

Workspace agents need one central LLM middleware surface that can route to local
or cloud providers, support structured outputs, and record activity across many
parallel agent runs. The existing chat completions endpoint remains useful, but
new agent workloads need a response-oriented contract closer to OpenAI's
Responses API.

## Decision

Add `POST /v1/responses` as the preferred endpoint for agent and structured
output requests.

The gateway will:

- keep client requests provider-agnostic through model aliases
- route aliases to internal provider/model/API mode
- forward structured-output configuration for compatible providers
- keep `/v1/chat/completions` backward compatible
- record chat and responses traffic as activity rows
- write activity records through a bounded async queue
- use Postgres as the production storage target for concurrent workspace agents

## Consequences

Positive:

- client applications use one gateway for agent LLM requests
- provider credentials and model names stay centralized
- structured-output requests can be tracked consistently
- admin usage filters can inspect workflow, session, user, endpoint, and status

Trade-offs:

- providers now need a `respond()` contract in addition to `chat()`
- SQLite remains suitable for local development, but production concurrency
  should use Postgres
- streaming and local tool execution remain separate follow-up decisions
