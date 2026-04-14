# Developer Documentation

Welcome to the developer documentation! This directory contains comprehensive guides for working with this project's features, tools, and workflows.

## Getting Started

New to this project? Start here:

1. **[Makefile](./makefile.md)** - Essential commands for development, testing, and building
2. **[Dependencies](./dependencies.md)** - Managing project dependencies, virtual environments, and package installation
3. **[Settings](./settings.md)** - Environment configuration and settings management
4. **[Docker](./docker.md)** - Containerization, deployment, and local development with Docker

## Quick Start (Frontend + Backend)

1. Clone the repository and move into the project root.
2. Copy environment defaults:

   ```bash
   cp .env.example .env
   ```

3. Start everything:

   ```bash
   docker compose up --build
   ```

4. Open the app and verify:
   - App: <http://localhost/app>
   - API docs (Swagger): <http://localhost/api/docs>
   - Health check: <http://localhost/health>
   - MailHog (email testing): <http://localhost:8025>

This starts a Caddy gateway, a Python backend, and a Vite frontend dev server with hot module replacement (HMR). Changes to frontend source files reload instantly in the browser. See [Docker](./docker.md) for architecture details.

### Stop Everything

```bash
docker compose down
```

### Running Without Docker

If you prefer to run the backend locally (e.g. for debugging):

1. Start only the infrastructure services:

   ```bash
   docker compose up -d db redis mailhog
   ```

2. In Terminal 1, start the backend:

   ```bash
   uv run uvicorn oscilla.www:app --reload --host 127.0.0.1 --port 8000
   ```

3. In Terminal 2, start the Vite dev server:

   ```bash
   make frontend_dev
   ```

   The Vite server proxies `/api` and `/static` to the backend at `http://localhost:8000`.

- Frontend: <http://localhost:5173/app>
- API docs: <http://localhost:8000/api/docs>
- MailHog: <http://localhost:8025>

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
