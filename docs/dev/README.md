# Developer Documentation

Welcome to the developer documentation! This directory contains comprehensive guides for working with this project's features, tools, and workflows.

## Getting Started

New to this project? Start here:

1. **[Makefile](./makefile.md)** - Essential commands for development, testing, and building
2. **[Dependencies](./dependencies.md)** - Managing project dependencies, virtual environments, and package installation
3. **[Settings](./settings.md)** - Environment configuration and settings management
4. **[Docker](./docker.md)** - Containerization, deployment, and local development with Docker

## Quick Start (Frontend + Backend)

There are two valid full-stack workflows. Use the one that matches what you are changing.

### Option A: Full Docker Stack (backend container + built frontend)

Best when you want everything containerized exactly as Compose defines it.

1. Clone the repository and move into the project root.
2. Copy environment defaults:

   ```bash
   cp .env.example .env
   ```

3. Start all services, including MailHog (dev profile):

   ```bash
   docker compose --profile dev up -d --build
   ```

4. Open the app and verify health:

- Frontend (served by backend container): <http://127.0.0.1/app>
- API docs (backend container): <http://127.0.0.1/docs>
- Health check: <http://127.0.0.1/health>
- MailHog: <http://127.0.0.1:8025>

### Option B: Frontend Hot Reload (Vite) + Live backend API

Best when actively developing the Svelte app with instant reload.

1. Install dependencies:

   ```bash
   make install
   ```

2. Start dependency services:

   ```bash
   docker compose --profile dev up -d db redis mailhog
   ```

3. In Terminal 1, start backend API on port 8000:

   ```bash
   uv run uvicorn oscilla.www:app --reload --host 127.0.0.1 --port 8000
   ```

4. In Terminal 2, start the frontend dev server:

   ```bash
   make frontend_dev
   ```

5. Open these URLs:

- Frontend dev app: <http://127.0.0.1:5173/app>
- Backend API docs: <http://127.0.0.1:8000/docs>
- Backend health check: <http://127.0.0.1:8000/health>
- MailHog: <http://127.0.0.1:8025>

The Vite server proxies `/auth`, `/games`, `/characters`, and `/overworld` to `http://localhost:8000`.

### Stop Everything

- Stop local frontend/backend processes with Ctrl+C in their terminals.
- Stop containers:

  ```bash
  docker compose down
  ```

## Core Features

### [Design Philosophy](./design-philosophy.md)

The recurring ideas that guide engine and feature design: author-defined vocabulary, composable effects, the condition evaluator as a universal gate, and the separation of content from engine.

### [Database](./database.md)

SQLAlchemy ORM integration, models, migrations with Alembic, and database patterns.

### [Caching](./cache.md)

Redis-backed caching with aiocache for performance optimization.

### [REST API](./api.md)

FastAPI web framework, endpoints, middleware, and API development.

### [Authentication](./authentication.md)

JWT access tokens, refresh token rotation, email verification, password reset, and the `get_current_user` dependency.

### [CLI](./cli.md)

Command-line interface built with Typer for management and automation tasks.

### [Templates](./templates.md)

Jinja2 templating for HTML rendering and template-based content generation.

### [Frontend](./frontend.md)

The SvelteKit SPA architecture, API client conventions, route patterns, component structure, and frontend test workflows.

## Game Engine

### [Game Engine](./game-engine.md)

Engine internals, architecture, and extend points for the text-based adventure system.

### [CLI Interface](./tui.md)

Command-line interface layer, TUI implementation, and game loop structure.

### [Load Warnings](./load-warnings.md)

The `LoadWarning` dataclass, diagnostic policy (warning vs. error), the `suggestion` field contract, and a guide for adding new warning conditions.

## Interface Layers

The oscilla project is designed with clear separation between interface layers:

- **Game Engine** - Core game logic and content processing (above)
- **CLI Interface** - Terminal user interface and commands (above)
- **REST API** - Web service endpoints
- **Frontend** - Web browser interface

## Development Practices

### [Testing](./testing.md)

Comprehensive testing guide covering pytest, fixtures, async testing, mocking, and code coverage.

### [Documentation](./documentation.md)

Standards and best practices for writing and maintaining project documentation.

### [GitHub Actions](./github.md)

CI/CD workflows for testing, linting, building, and deployment automation.

### [PyPI](./pypi.md)

Publishing packages to the Python Package Index.

## Project-Specific Documentation

As your project grows, add documentation for:

- **Architecture** - System design, component interactions, and architectural decisions
- **API Reference** - Detailed API endpoints, request/response formats, and authentication
- **Deployment** - Production deployment procedures, monitoring, and operations
- **Troubleshooting** - Common issues, debugging techniques, and solutions
- **Contributing** - Guidelines for contributors and development workflows

## Documentation Standards

All documentation in this project follows the standards outlined in [documentation.md](./documentation.md). When adding new documentation:

- Use real, working code examples from this project
- Include practical usage patterns
- Test all code examples before publishing
- Keep documentation updated as code changes
- Follow the established structure and style

## Quick Reference

- **Setup**: Run `make install` to set up your development environment
- **Testing**: Run `make tests` for full test suite, see [testing.md](./testing.md) for details
- **Formatting**: Run `make chores` before committing to fix formatting issues
- **Configuration**: See [settings.md](./settings.md) for environment variables and settings
- **Local Development**: Use `docker compose up` for local services, see [docker.md](./docker.md)
- **All Make Commands**: See [makefile.md](./makefile.md) for complete reference

---

_This documentation is maintained by the development team. If you find issues or have suggestions, please contribute improvements!_
