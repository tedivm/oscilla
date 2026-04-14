## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: MailHog is isolated behind a dev Compose profile

**Reason**: The Compose profile gate was added to prevent MailHog from starting in production. Production deployments pull and run the published container image directly — they do not use `compose.yaml`. The profile gate serves no production-safety purpose and adds friction to the developer workflow.

**Migration**: Remove `profiles: [dev]` from the `mailhog` service. MailHog now starts with plain `docker compose up`. Developers no longer need `--profile dev`.
