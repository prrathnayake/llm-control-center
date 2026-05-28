# ADR 0001: Provider-agnostic LLM gateway

## Status

Accepted

## Context

Multiple projects need LLM access. Direct provider integration in every project creates duplicated code, leaked provider credentials, inconsistent logs, and hard provider migration.

## Decision

Build a central LLM gateway with:

- one stable client API
- project API keys
- internal provider adapters
- model aliases instead of exposed provider model names
- usage logging
- mock provider for CI

## Consequences

Positive:

- projects can change providers without code changes
- provider credentials stay centralized
- observability becomes consistent
- tests avoid paid APIs

Trade-offs:

- gateway is now critical infrastructure
- bad routing config can affect many projects
- high availability matters later

## Follow-up decisions

- choose PostgreSQL migration strategy
- define redaction policy
- define model fallback policy
- define cost accounting model
