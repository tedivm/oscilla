## 1. Dockerfile Rename and Stage Naming

- [x] 1.1 Run `git mv dockerfile.www Dockerfile` to rename the production Dockerfile; verify `git status` shows a rename (not a delete + create)
- [x] 1.2 Add `AS backend` to the Python runtime stage line in `Dockerfile` (change `FROM ghcr.io/multi-py/python-uvicorn:...` to `FROM ghcr.io/multi-py/python-uvicorn:... AS backend`)
- [x] 1.3 Remove the `COPY --from=frontend-build /app/frontend/build /app/frontend/build` line from the `backend` stage
- [x] 1.4 Append a new `FROM backend AS production` final stage to `Dockerfile` containing only `COPY --from=frontend-build /app/frontend/build /app/frontend/build`
- [ ] 1.5 Verify `docker build .` succeeds and the resulting image contains `/app/frontend/build/`
- [ ] 1.6 Verify `docker build --target backend .` succeeds and the resulting image does NOT contain `/app/frontend/build/`

## 2. Gateway Container

- [x] 2.1 Create `docker/gateway/Caddyfile` with path-based routing: `/api*`, `/static*`, `/health*`, `/ready*` → `reverse_proxy backend:8000`; all other paths → `reverse_proxy frontend:5173`
- [x] 2.2 Verify the Caddyfile syntax is valid by running `docker run --rm -v $(pwd)/docker/gateway/Caddyfile:/etc/caddy/Caddyfile caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile`

## 3. Frontend Dev Container

- [x] 3.1 Create `docker/frontend/Dockerfile` with `FROM node:22-alpine`; set `WORKDIR /app`; copy `frontend/package*.json ./`; run `npm ci`; expose port 5173; set `CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]`

## 4. compose.yaml Overhaul

- [x] 4.1 Replace the `www` service with a `gateway` service: image `caddy:2-alpine`, port `80:80`, volume `./docker/gateway/Caddyfile:/etc/caddy/Caddyfile`, depends_on `backend` and `frontend`
- [x] 4.2 Add a `backend` service: `build: { dockerfile: ./Dockerfile, target: backend }`, volumes for `./oscilla`, `./db`, `./content`, `./docker/www/prestart.sh`; environment `IS_DEV=true`, `RELOAD=true`, `DATABASE_URL`, `CACHE_REDIS_HOST`, `CACHE_REDIS_PORT`; depends_on `db` and `redis`
- [x] 4.3 Add a `frontend` service: `build: { context: ., dockerfile: ./docker/frontend/Dockerfile }`, volumes `./frontend:/app` and `frontend_node_modules:/app/node_modules`; environment `HMR_CLIENT_PORT=80`; depends_on `backend`
- [x] 4.4 Remove `profiles: [dev]` from the `mailhog` service so it starts with plain `docker compose up`
- [x] 4.5 Add a top-level `volumes:` block declaring `frontend_node_modules:`
- [x] 4.6 Remove the `content` volume mount from the old `www` service if it was not already there; confirm `content` is volume-mounted on `backend` so games load correctly

## 5. Vite Config HMR Patch

- [x] 5.1 In `frontend/vite.config.ts`, add `hmr: { clientPort: Number(process.env.HMR_CLIENT_PORT) || undefined }` inside the `server:` block, above the existing `proxy:` entry; add an inline comment explaining the Docker proxy port override pattern

## 6. GitHub Actions Workflow

- [x] 6.1 In `.github/workflows/docker.yaml`, remove the `strategy.matrix` block and the `image: [www]` entry
- [x] 6.2 Update the `Extract metadata` step: change `images:` from `${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}.${{ matrix.image }}` to `${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}`
- [x] 6.3 Update the `Build and push Docker image` step: change `file:` from `dockerfile.${{ matrix.image }}` to `Dockerfile`
- [x] 6.4 Remove the `name: Push Container Image to GHCR` job's `strategy:` section entirely; verify the workflow YAML is still valid

## 7. Documentation

- [x] 7.1 Update `docs/dev/docker.md`: replace all references to `dockerfile.www` with `Dockerfile`; replace the old single-service description with the new three-container topology diagram; add a section on the `node_modules` named volume caveat (rebuild required after `package.json` changes); update the MailHog section to reflect it now starts without `--profile dev`
- [x] 7.2 Update `docs/dev/README.md`: simplify the quick start to a single `docker compose up` flow (remove the two-option layout); list the correct URLs (port 80 only, plus 8025 for MailHog); remove the local uvicorn + `make frontend_dev` option as a required workflow (it can remain as an optional alternative)
- [x] 7.3 Update `AGENTS.md`: update the Docker command block to reflect `docker compose up` as the full dev stack; remove the `--profile dev` note

## 8. Docker Stack Smoke Test

- [ ] 8.1 Run `docker compose build` and confirm all three custom images build successfully (`backend`, `frontend`, `gateway` uses a pre-built image)
- [ ] 8.2 Run `docker compose up -d` and confirm all six services reach running state
- [ ] 8.3 Open `http://localhost` in a browser and confirm it redirects to `/app` and the SvelteKit app loads
- [ ] 8.4 Open `http://localhost:8025` and confirm the MailHog web UI is accessible
- [ ] 8.5 Edit any `.svelte` file (e.g. add a visible string to `frontend/src/routes/+page.svelte`) and confirm the browser hot-reloads within ~1-2 seconds
- [ ] 8.6 Edit `oscilla/www.py` (e.g. add a `logger.info` call) and confirm uvicorn reloads and the API responds correctly
- [ ] 8.7 Run `docker compose down -v` and confirm the `frontend_node_modules` volume is removed

## 9. API Route Prefix Migration

- [x] 9.1 In `oscilla/www.py`, update the `FastAPI()` instantiation to add `docs_url="/api/docs"`, `redoc_url="/api/redoc"`, and `openapi_url="/api/openapi.json"` keyword arguments
- [x] 9.2 In `oscilla/www.py`, update `app.include_router(auth_router, ...)` to use `prefix="/api/auth"`
- [x] 9.3 In `oscilla/www.py`, update `app.include_router(games_router, ...)` to use `prefix="/api/games"`
- [x] 9.4 In `oscilla/www.py`, update `app.include_router(characters_router, ...)` to use `prefix="/api/characters"`
- [x] 9.5 In `oscilla/www.py`, update `app.include_router(play_router, ...)` to add `prefix="/api"` (the router's internal paths already start with `/characters/{id}/play/...`)
- [x] 9.6 In `oscilla/www.py`, update `app.include_router(overworld_router, ...)` to add `prefix="/api"` (the router's internal paths already start with `/characters/{id}/overworld`)
- [x] 9.7 In `oscilla/www.py`, add a `GET /api` route that returns `RedirectResponse("/api/docs")` with `include_in_schema=False`; add the `RedirectResponse` import from `fastapi.responses`
- [x] 9.8 In `frontend/src/lib/api/auth.ts`, prefix all `apiFetch` path arguments with `/api` (e.g. `/auth/login` → `/api/auth/login`)
- [x] 9.9 In `frontend/src/lib/api/games.ts`, prefix all `apiFetch` path arguments with `/api`
- [x] 9.10 In `frontend/src/lib/api/characters.ts`, prefix all `apiFetch` path arguments with `/api`
- [x] 9.11 In `frontend/src/lib/api/play.ts`, prefix all `apiFetch` path arguments with `/api`
- [x] 9.12 In `frontend/src/lib/stores/auth.ts`, prefix all `apiFetch` path arguments with `/api`
- [x] 9.13 In `frontend/src/lib/api/client.ts`, update the token refresh guard from `path === "/auth/refresh"` to `path === "/api/auth/refresh"`
- [x] 9.14 In `frontend/vite.config.ts`, replace the four-entry proxy (`/auth`, `/games`, `/characters`, `/overworld`) with two entries: `/api` → `http://localhost:8000` and `/static` → `http://localhost:8000`
- [x] 9.15 In all files under `tests/routers/`, replace all bare path prefixes with `/api`-prefixed equivalents (e.g. `"/auth/login"` → `"/api/auth/login"`, `"/games"` → `"/api/games"`, etc.); run `make pytest` to confirm zero test failures after the update

## 10. API Route Documentation

- [x] 10.1 Create `docs/dev/api.md`: document the `/api` prefix convention, list all routers with their base paths, note that `/health` and `/ready` are at root, explain `GET /api` → `/api/docs` redirect, and describe how to call the API from frontend code
- [x] 10.2 Update `docs/dev/README.md`: add `api.md` to the table of contents in the dev docs index
- [x] 10.3 Update `docs/dev/docker.md`: remove any note about updating Caddyfile when adding new API routes (not needed with `/api*` catch-all); add a note about the `/api/docs` Swagger URL
- [x] 10.4 Update `AGENTS.md`: note that all API routes live under `/api`, `/health`+`/ready` are at root, `GET /api` redirects to `/api/docs`

## 11. Hosting Documentation

- [x] 11.1 Create `docs/hosting/README.md`: brief intro for operators/self-hosters, table of contents linking to `deployment.md` and any future hosting guides, note distinguishing this section from developer docs
- [x] 11.2 Create `docs/hosting/deployment.md`: cover pulling the published image from `ghcr.io/tedivm/oscilla`, all required environment variables (database URL, Redis host/port, secret key, etc.), an example `docker run` command and an example `docker-compose.yml` snippet for a production deployment with PostgreSQL and Redis, the health probe endpoints (`/health` and `/ready`) and how to wire them into a load balancer or orchestrator, upgrade procedure (pull new tag + restart), and a note that the image is a multistage production build with no dev tooling included

## 12. Final Verification

- [ ] 12.1 Run `make chores` and confirm exit 0
- [ ] 12.2 Run `make pytest` and confirm all tests pass (validates API route migration in Python tests)
- [ ] 12.3 Run `make frontend_test` and confirm frontend unit tests pass
- [ ] 12.4 Run `make frontend_e2e` and confirm Playwright E2E passes (validates frontend `apiFetch` paths)
- [ ] 12.5 Run `docker compose build` and `docker compose up -d`; open `http://localhost/api/docs` and confirm Swagger UI loads; confirm `GET http://localhost/api` redirects to `/api/docs`; confirm `GET http://localhost/health` returns 200
