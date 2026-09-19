# Operations

## Environment variables

See `.env.example`.

Required for local development:

```bash
LLM_CC_ADMIN_TOKEN=change-me-admin-token
LLM_CC_API_KEY_PEPPER=change-me-long-random-pepper
LLM_CC_DATABASE_URL=sqlite:///./data/control_center.sqlite3
LLM_CC_USAGE_SPOOL_PATH=./data/usage_spool.sqlite3
```

For concurrent workspace agents, use Postgres:

```bash
LLM_CC_DATABASE_URL=postgresql+psycopg2://llm_cc:changeme@localhost:5432/llm_control_center
```

The gateway indexes activity logs by project, trace, creation time, status,
workflow, and session. `trace_id` is an idempotency key. The independent usage
spool survives gateway restarts and retains exhausted entries as `dead_letter`
rows for operator inspection and replay.

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

## Docker Hub publishing

The repository includes `.github/workflows/docker-publish.yml`.

The workflow runs on:

- pull requests to `main`
- pushes to `main`
- version tags like `v0.1.0`
- manual `workflow_dispatch`

The Docker image is only built and pushed after the full test job passes.
Pull requests build the image but do not push it.
Pushes to `main` and version tags publish to Docker Hub.

Add these GitHub Actions repository secrets:

```text
DOCKERHUB_USERNAME=<your-dockerhub-username>
DOCKERHUB_TOKEN=<dockerhub-access-token>
```

Published tags include:

```text
latest              # only on main
main                # branch tag
v0.1.0              # git version tag
sha-<commit-sha>    # immutable commit tag
```

Expected image name:

```text
<DOCKERHUB_USERNAME>/llm-control-center
```

Create a Docker Hub access token from Docker Hub account settings and use that token instead of your Docker Hub password.

## Rotate project API keys

1. Create a new key for the project.
2. Update the client project secret.
3. Restart or reload the client project.
4. Revoke the old key:

```bash
curl -X DELETE http://localhost:8080/admin/projects/<project_id>/api-keys/<key_id> \
  -H "X-Admin-Token: change-me-admin-token"
```

The MVP supports creation, validation, listing, and hard revocation (`DELETE /admin/projects/{project_id}/api-keys/{key_id}`). Revocation is a hard delete; past usage logs are retained.

## Production checklist

- Use PostgreSQL for concurrent agent activity.
- Put the usage spool on durable, monitored storage.
- Store provider API keys in a secret manager.
- Set a long random `LLM_CC_API_KEY_PEPPER`.
- Use HTTPS only.
- Keep `LLM_CC_TRUST_PROXY_HEADERS=false` unless a trusted edge strips incoming forwarding headers.
- Add an edge rate limiter for volumetric protection; authenticated gateway buckets are shared in SQL.
- Add per-project budgets.
- Tune provider bulkhead/circuit settings against production latency and capacity.
- Add structured log export.

## Observability plan

Current MVP records usage/activity rows in the configured SQL database and
flushes queued activity before admin usage reads.

Next version should export:

- Prometheus metrics
- OpenTelemetry traces
- request/response redaction pipeline
- provider latency dashboard
- per-project cost dashboard
