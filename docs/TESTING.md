# Testing Strategy

## Goals

- Prove API auth works.
- Prove project API keys are hashed and validated.
- Prove chat requests route through the provider abstraction.
- Prove usage is logged for success and failure scenarios.
- Prove CI never calls paid APIs.

## Test categories

```text
tests/test_auth.py            admin and project auth
tests/test_api_keys.py        key creation and one-time raw key behavior
tests/test_chat_mock.py       chat endpoint through mock provider
tests/test_routing.py         alias routing and unknown model handling
tests/test_provider_mapping.py provider response normalization
tests/test_ci_contract.py     CI and repo contract checks
```

## Local commands

```bash
make install
make test
make lint
```

## CI/CD pipeline

GitHub Actions runs on every push and pull request:

1. install Python dependencies
2. run Ruff lint
3. run pytest with coverage threshold
4. import package smoke test

## Important rule

Tests must never require these environment variables:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY`
- `LLM_CC_OPENAI_COMPATIBLE_API_KEY`

Provider adapters that call real APIs must be tested with fake transports, mock providers, or contract tests.
