# Agent Working Rules

This repo is an LLM gateway. Keep it boring, typed, tested, and provider-agnostic.

## Source of truth

Read these before large changes:

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `docs/API.md`
4. `docs/TESTING.md`
5. `docs/adr/0001-llm-gateway.md`

## Hard rules

- Do not expose real provider API keys to client projects.
- Do not expose provider model names as a requirement for clients.
- Client-facing contracts must stay stable.
- Tests must not call paid APIs or external network services.
- Provider adapters must stay behind `ProviderAdapter`.
- Business logic belongs in services, not directly in FastAPI routes.
- Every new provider needs contract tests with fake HTTP transport or mock provider behavior.
- Every new route needs tests for auth failure and success path.
- Keep docs updated when public API shape changes.

## Preferred change flow

1. Update or add tests first.
2. Implement small service/provider changes.
3. Run `make test`.
4. Update docs and ADRs if the design changed.
5. Open PR only after CI passes.
