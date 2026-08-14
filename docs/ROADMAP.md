# Roadmap

## Phase 1: Gateway MVP

- [x] FastAPI server
- [x] project API keys
- [x] model alias routing
- [x] mock provider
- [x] OpenAI-compatible provider
- [x] Ollama provider
- [x] SQLite usage logs
- [x] CI/CD pipeline
- [x] documentation

## Phase 2: Production controls

- [x] PostgreSQL persistence
- [x] API key revocation
- [x] per-project rate limits
- [ ] per-project monthly budget limits
- [ ] fallback routing
- [x] provider circuit breaker and concurrency bulkhead
- [x] public provider-error redaction

## Phase 3: Advanced LLM platform

- [ ] embeddings endpoint
- [ ] image generation endpoint
- [ ] tool-call normalization
- [ ] streaming passthrough for cloud providers
- [ ] prompt registry
- [ ] trace replay
- [ ] eval harness
- [ ] admin dashboard

## Phase 4: Agent infrastructure

- [ ] workflow traces
- [ ] memory service integration
- [ ] MCP/tool registry integration
- [ ] policy engine
- [ ] sandboxed tool execution logs
