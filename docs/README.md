# Oscilla Documentation

Welcome to the Oscilla documentation. Guides are organized by audience into three sections below.

For a comprehensive architecture reference covering how all layers fit together, see the [System Overview](system-overview.md).

---

## [Hosting](hosting/README.md)

For operators deploying Oscilla in production.

| Document                                  | Description                                                                                  |
| ----------------------------------------- | -------------------------------------------------------------------------------------------- |
| [Deployment Guide](hosting/deployment.md) | Container image, environment variables, database migrations, and reverse-proxy configuration |

---

## [Developer Documentation](dev/README.md)

For contributors and engineers working on the Oscilla engine and platform.

| Section                   | Documents                                                                                                                                                                                           |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Getting Started**       | [Docker](dev/docker.md) · [Makefile](dev/makefile.md) · [Dependencies](dev/dependencies.md) · [Settings](dev/settings.md)                                                                           |
| **Core Features**         | [API](dev/api.md) · [Authentication](dev/authentication.md) · [Database](dev/database.md) · [Cache](dev/cache.md) · [CLI](dev/cli.md) · [Templates](dev/templates.md) · [Frontend](dev/frontend.md) |
| **Game Engine**           | [Game Engine](dev/game-engine.md) · [TUI Interface](dev/tui.md) · [Load Warnings](dev/load-warnings.md)                                                                                             |
| **Development Practices** | [Testing](dev/testing.md) · [Documentation](dev/documentation.md) · [GitHub Actions](dev/github.md) · [PyPI Publishing](dev/pypi.md) · [Design Philosophy](dev/design-philosophy.md)                |

---

## [Content Author Documentation](authors/README.md)

For game designers and writers building games with Oscilla's YAML manifest system.

| Section                     | Documents                                                                                                                                                                                                                                                                                                                                                                                                                |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **New Authors: Start Here** | [Getting Started](authors/getting-started.md) · [Game Configuration](authors/game-configuration.md)                                                                                                                                                                                                                                                                                                                      |
| **The Authoring Model**     | [Conditions](authors/conditions.md) · [Effects](authors/effects.md) · [Templates](authors/templates.md) · [Cooldowns](authors/cooldowns.md)                                                                                                                                                                                                                                                                              |
| **Building Your Game**      | [World Building](authors/world-building.md) · [Adventures](authors/adventures.md) · [Items](authors/items.md) · [Enemies](authors/enemies.md) · [Skills & Buffs](authors/skills.md) · [Archetypes](authors/archetypes.md) · [Loot Tables](authors/loot-tables.md) · [Quests](authors/quests.md) · [Recipes](authors/recipes.md) · [Passive Effects](authors/passive-effects.md) · [In-Game Time](authors/ingame-time.md) |
| **Author CLI Tooling**      | [CLI Reference](authors/cli.md)                                                                                                                                                                                                                                                                                                                                                                                          |
| **Cookbook**                | [Reputation System](authors/cookbook/reputation-system.md) · [Locked Doors](authors/cookbook/locked-doors.md) · [Day-Night Narrative](authors/cookbook/day-night-narrative.md) · [In-Game Time Patterns](authors/cookbook/ingame-time-patterns.md)                                                                                                                                                                       |
