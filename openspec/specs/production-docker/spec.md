# Production Docker

## Purpose

Specifies the Docker hardening changes applied to `dockerfile.www` and `compose.yaml`. Goals are: run as a non-root user to reduce the attack surface of a container escape, install only production dependencies to minimize image size and supply-chain risk, support configurable worker counts for production throughput, and isolate the MailHog mail catcher behind a development-only Compose profile so it is never started in production.

---

## Requirements

### Requirement: Application container runs as non-root user

`dockerfile.www` SHALL create a system user and group with UID/GID `999` named `oscilla` and switch to that user before the `CMD` instruction. All files in the working directory SHALL be `chown`-ed to `oscilla:oscilla` before the user switch.

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

`dockerfile.www` SHALL invoke `uv sync` with the `--no-dev` flag so development dependencies (pytest, ruff, mypy, etc.) are not present in the production image. This reduces image size and removes tools that could be misused in a compromised container.

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

The `CMD` in `dockerfile.www` SHALL read the `UVICORN_WORKERS` environment variable and default to `1` if it is not set. This allows operators to tune concurrency by setting the variable in their deployment environment without rebuilding the image.

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

### Requirement: MailHog is isolated behind a dev Compose profile

`compose.yaml` SHALL add `profiles: ["dev"]` to the `mailhog` service definition. Services without a profile are started by default; services with a profile are only started when the profile is explicitly activated.

Developers run `docker compose --profile dev up` to include MailHog. The production deployment omits the `--profile` flag and MailHog is never started.

`compose.yaml` SHALL include a comment on the `mailhog` service explaining its profile restriction.

#### Scenario: mailhog not started without dev profile

- **GIVEN** `compose.yaml` with MailHog in the `dev` profile
- **WHEN** `docker compose up` is run without `--profile dev`
- **THEN** the `mailhog` service is not started

#### Scenario: mailhog started with dev profile

- **GIVEN** `compose.yaml` with MailHog in the `dev` profile
- **WHEN** `docker compose --profile dev up` is run
- **THEN** the `mailhog` service starts and is reachable

---

### Requirement: .env.example documents new environment variables

`.env.example` SHALL be updated to include documentation stubs for:

- `UVICORN_WORKERS` — with the default value `1` and a comment explaining it controls worker count
- `CORS_ORIGINS` — with the default value `'["http://localhost:5173"]'` and a comment noting that production deployments must set this to the deployed frontend URL

These additions ensure new operators are aware of the production-relevant variables when setting up their `.env` from the example file.
