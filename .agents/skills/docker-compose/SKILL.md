---
name: docker-compose
description: "Work with the Oscilla Docker Compose development environment. Use when: starting or stopping services, inspecting logs, opening a shell in a container, resetting the database, or understanding the service topology."
---

# Docker Compose Development Environment

> **context7**: If the `mcp_context7` tool is available, resolve and load the full Docker Compose documentation before modifying `compose.yaml` or using advanced CLI options:
> ```
> mcp_context7_resolve-library-id: "docker compose"
> mcp_context7_get-library-docs: /docker/compose
> ```

The Oscilla development environment runs entirely through Docker Compose. All services are defined in `compose.yaml`.

---

## Services

| Service    | Role                                         |
| ---------- | -------------------------------------------- |
| `gateway`  | Caddy reverse proxy — routes traffic to backend/frontend |
| `backend`  | FastAPI application server                   |
| `frontend` | Vite / SvelteKit dev server                  |
| `db`       | PostgreSQL database                          |
| `redis`    | Redis cache / task queue                     |
| `mailhog`  | Local SMTP sink for catching outbound emails |

---

## Essential Commands

### Start / Stop

```bash
# Start all services in the background
docker compose up -d

# Stop all services (preserves volumes — data is retained)
docker compose down

# Stop all services AND remove volumes (full reset — destroys all data)
docker compose down -v

# Restart all services without destroying containers or volumes
docker compose restart

# Restart a single service
docker compose restart backend
```

### Logs

```bash
# View recent logs from all services
docker compose logs

# Follow (tail) logs from all services in real-time
docker compose logs -f

# Follow logs from a specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f db
```

### Status and Inspection

```bash
# List running services and their status
docker compose ps

# Open a bash shell inside a running service
docker compose exec backend bash
docker compose exec db bash
docker compose exec frontend sh
```

---

## Common Workflows

### Start a fresh development environment

```bash
docker compose up -d
docker compose logs -f   # watch until all services are healthy
```

### Full reset (wipe all data and restart)

```bash
docker compose down -v
docker compose up -d
```

### Debug a service startup failure

```bash
docker compose logs backend --tail=50
# or follow real-time:
docker compose logs -f backend
```

### Run a one-off command inside a service

```bash
docker compose exec backend bash
# then run commands inside the container
```

### Apply database migrations inside the container

```bash
docker compose exec backend uv run alembic upgrade head
```

---

## Notes

- The gateway service (`Caddy`) handles TLS termination and routing. Its config lives in `docker/gateway/Caddyfile`.
- Frontend container config lives in `docker/frontend/Dockerfile`.
- All Docker-specific files (Dockerfiles, gateway config) live in the `docker/` folder.
- The developer `.env` file is loaded automatically by Compose — make sure it's populated before starting.

---

## Further Reading

- [docs/dev/docker.md](../../docs/dev/docker.md) — Full Docker developer guide covering service topology, volume management, hot-reload behavior, and multi-service debugging.
- [docs/hosting/deployment.md](../../docs/hosting/deployment.md) — Production deployment guide (separate from the dev Compose stack).
- [Docker Compose Docs](https://docs.docker.com/compose/)
