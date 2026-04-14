# Production Docker

## Purpose

Specifies the Docker hardening changes applied to `Dockerfile` and `compose.yaml`. Goals are: run as a non-root user to reduce the attack surface of a container escape, install only production dependencies to minimize image size and supply-chain risk, support configurable worker counts for production throughput, and use a multi-stage build that separates the backend-only image from the production image that includes the frontend build artifact.

---

## Requirements

### Requirement: Dockerfile is named `Dockerfile` (not `dockerfile.www`)

The production Dockerfile SHALL be named `Dockerfile` (standard Docker naming convention). The legacy name `dockerfile.www` SHALL be removed via `git mv`.

All references in `compose.yaml`, `.github/workflows/docker.yaml`, and documentation SHALL be updated to reference `Dockerfile`.

#### Scenario: Standard docker build command works

- **GIVEN** the repository with `Dockerfile` at the root
- **WHEN** `docker build .` is run (no `-f` flag)
- **THEN** the production image is built successfully using the default `Dockerfile` name

---

### Requirement: Dockerfile declares named build stages

`Dockerfile` SHALL declare three named stages:

1. `FROM node:22-alpine AS frontend-build` — builds the SvelteKit static assets
2. `FROM ghcr.io/multi-py/python-uvicorn:... AS backend` — Python runtime without the frontend artifact; used by `docker compose` dev stack via `target: backend`
3. `FROM backend AS production` — extends `backend` with `COPY --from=frontend-build`; this is the default (last) stage built by `docker build .`

The `backend` stage SHALL include all Python dependencies, application code, non-root user setup, and the `CMD`. The `production` stage SHALL only add the frontend build artifact.

#### Scenario: Default build produces production image with frontend

- **GIVEN** `Dockerfile` with three named stages
- **WHEN** `docker build .` is run (targets the default final stage `production`)
- **THEN** the image contains `frontend/build/` with the compiled SvelteKit assets
- **AND** `GET /app` in a running container serves the SPA

#### Scenario: `target: backend` image omits frontend build

- **GIVEN** `Dockerfile` with three named stages
- **WHEN** `docker build --target backend .` is run
- **THEN** the image does NOT contain `frontend/build/`
- **AND** the image starts and serves the API correctly

---

### Requirement: Published container image is tagged without `.www` suffix

The GitHub Actions `docker.yaml` workflow SHALL publish the image to `ghcr.io/tedivm/oscilla` (no `.www` suffix). The strategy matrix (which previously allowed multiple images) SHALL be removed; the workflow SHALL have a single build step.

#### Scenario: Workflow publishes to correct image name

- **GIVEN** a push to the `main` branch or a version tag
- **WHEN** the `Publish Docker Images` workflow runs
- **THEN** the image is pushed to `ghcr.io/tedivm/oscilla` with the appropriate tags
- **AND** no image is pushed to `ghcr.io/tedivm/oscilla.www`

---

### Requirement: Application container runs as non-root user

`Dockerfile` SHALL create a system user and group with UID/GID `999` named `oscilla` and switch to that user before the `CMD` instruction. All files in the working directory SHALL be `chown`-ed to `oscilla:oscilla` before the user switch.

```dockerfile
RUN groupadd --gid 999 oscilla && \
    useradd --uid 999 --gid oscilla --no-create-home --shell /bin/false oscilla
...
RUN chown -R oscilla:oscilla /app
USER oscilla
```

#### Scenario: running container uses non-root user

- **GIVEN** the production Dockerfile
- **WHEN** `docker inspect` or `docker exec whoami` is run against a container built from it
- **THEN** the process user is `oscilla` (UID 999), not `root`

---

### Requirement: Only production dependencies are installed in the image

`Dockerfile` SHALL invoke `uv sync` with the `--no-dev` flag so development dependencies (pytest, ruff, mypy, etc.) are not present in the production image. This reduces image size and removes tools that could be misused in a compromised container.

```dockerfile
RUN uv sync --no-dev --frozen
```

The `--frozen` flag ensures the lock file is respected and no unexpected version upgrades occur at build time.

#### Scenario: dev dependencies absent from production image

- **GIVEN** a container built with the production Dockerfile
- **WHEN** `python -c "import pytest"` is run inside the container
- **THEN** the command fails with `ModuleNotFoundError`

---

### Requirement: Uvicorn worker count is configurable via environment variable

The `CMD` in `Dockerfile` SHALL read the `UVICORN_WORKERS` environment variable and default to `1` if it is not set. This allows operators to tune concurrency by setting the variable in their deployment environment without rebuilding the image.

```dockerfile
CMD ["sh", "-c", "uvicorn oscilla.www:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}"]
```

The `prestart.sh` script (if present) SHALL be called before the uvicorn command if it exists, to allow Alembic migrations to run on startup.

#### Scenario: default worker count is 1

- **GIVEN** a container started without `UVICORN_WORKERS` set
- **WHEN** the process list is inspected
- **THEN** exactly 1 uvicorn worker process is running

#### Scenario: worker count scales with UVICORN_WORKERS

- **GIVEN** a container started with `UVICORN_WORKERS=4`
- **THEN** 4 uvicorn worker processes are running

---

### Requirement: .env.example documents new environment variables

`.env.example` SHALL be updated to include documentation stubs for:

- `UVICORN_WORKERS` — with the default value `1` and a comment explaining it controls worker count
- `CORS_ORIGINS` — with the default value `'["http://localhost:5173"]'` and a comment noting that production deployments must set this to the deployed frontend URL

These additions ensure new operators are aware of the production-relevant variables when setting up their `.env` from the example file.
