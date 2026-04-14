# Hosting Documentation

This directory contains guides for deploying and operating Oscilla in production.

## Contents

- **[Deployment Guide](./deployment.md)** — Deploy the pre-built container image, configure environment variables, connect to a database and Redis, and run database migrations.

## Before You Begin

Oscilla is distributed as a container image published to the GitHub Container Registry (GHCR):

```
ghcr.io/tedivm/oscilla:latest
```

The image bundles the Python backend (FastAPI + Uvicorn) and compiled frontend assets.
All configuration is supplied via environment variables — no config files are required.

## Quick Reference

| Concern         | Details                             |
| --------------- | ----------------------------------- |
| Image           | `ghcr.io/tedivm/oscilla:latest`     |
| Exposed port    | `8000`                              |
| Health probe    | `GET /health`                       |
| Readiness probe | `GET /ready`                        |
| API docs        | `GET /api/docs` (Swagger UI)        |
| Migrations      | `docker run ... oscilla db upgrade` |
