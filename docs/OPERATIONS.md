# Operations

## Environment variables

See `.env.example`.

Required for local development:

```bash
LLM_CC_ADMIN_TOKEN=change-me-admin-token
LLM_CC_API_KEY_PEPPER=change-me-long-random-pepper
LLM_CC_DATABASE_URL=sqlite:///./data/control_center.sqlite3
```

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
4. Revoke/delete old keys in a future admin endpoint.

The current MVP supports creation and validation. Revocation is planned.

## Production checklist

- Replace SQLite with PostgreSQL.
- Store provider API keys in a secret manager.
- Set a long random `LLM_CC_API_KEY_PEPPER`.
- Use HTTPS only.
- Add reverse proxy rate limits.
- Add per-project budgets.
- Add provider health checks.
- Add structured log export.

## Observability plan

Current MVP records usage rows in SQLite.

Next version should export:

- Prometheus metrics
- OpenTelemetry traces
- request/response redaction pipeline
- provider latency dashboard
- per-project cost dashboard
