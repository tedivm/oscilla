# Oscilla

Oscilla is a platform for building and hosting text-based adventure games. Games are defined entirely as YAML content manifests — regions, locations, adventures, items, enemies, quests, and more — with no code required to create a new game.

The engine ships two interfaces over the same core:

- **Web application** — a SvelteKit frontend backed by a FastAPI REST + SSE API, with user accounts, persistent characters, and a browser-based play experience.
- **TUI** — a Textual full-screen terminal application that runs entirely locally against a local SQLite database, with no server required.

For a full architectural overview, see [docs/system-overview.md](./docs/system-overview.md).

---

## Playing via the Web

The easiest way to run the web stack is with Docker Compose:

```bash
git clone https://github.com/tedivm/oscilla.git
cd oscilla
docker compose up -d
```

The application is then available at `http://localhost`. A default developer account is seeded automatically:

- **Email:** `dev@example.com`
- **Password:** `devpassword`

For production deployment — environment variables, PostgreSQL, Redis, TLS, and migration procedure — see the [Deployment Guide](./docs/hosting/deployment.md).

---

## Playing Locally via the TUI

The TUI runs entirely from the command line with no server or account required. It uses a local SQLite database for character persistence.

**Install from PyPI:**

```bash
pip install oscilla
# or, with uv:
uv tool install oscilla
```

**Install from source:**

```bash
git clone https://github.com/tedivm/oscilla.git
cd oscilla
make install
```

Oscilla requires a game library — a directory of game packages, each containing YAML manifests. By default it looks for a `content/` directory in the working directory. Point it elsewhere with `GAMES_PATH`.

```bash
# Validate content before playing
oscilla validate

# Launch the TUI (choose from available games)
oscilla game

# Jump directly into a specific game
oscilla game --game my-game

# Use a custom game library directory
GAMES_PATH=/path/to/games oscilla game
```

The `game` command resolves your identity from `USER@hostname` and stores save data in a platform-appropriate data directory. Run `oscilla data-path` to see where that is on your system.

For the full CLI reference, see [docs/dev/cli.md](./docs/dev/cli.md).

---

## Game Library Layout

A game library is a directory of game packages. Each package is a subdirectory containing a `game.yaml`.

```
content/                   # GAMES_PATH root
  my-game/                 # one game package
    game.yaml
    character_config.yaml
    regions/
      starting-region.yaml
    adventures/
      intro.yaml
```

Multiple game packages can coexist in the same library. Oscilla loads all of them at startup.

---

## Writing Game Content

Games are defined entirely in YAML. No code is required to create a new adventure, enemy, item, quest, or region. The content system supports:

- A hierarchical world of regions and locations with unlock conditions
- Multi-step adventures with narrative text, choices, combat, stat checks, and skill menus
- Items, equipment slots, crafting recipes, and loot tables
- A skill and buff system for both players and enemies
- Multi-stage quests with milestone-driven progression
- Archetypes for persistent character states (class, faction, condition)
- An opt-in in-game calendar with cycles, eras, and time-based conditions
- Jinja2 templates for dynamic narrative text and numeric formulas

**Getting started with content authoring:** [docs/authors/getting-started.md](./docs/authors/getting-started.md)

**Full authoring reference:** [docs/authors/README.md](./docs/authors/README.md)

**Author CLI tools** (validate, test, scaffold, graph, trace): [docs/authors/cli.md](./docs/authors/cli.md)

```bash
# Validate all content
oscilla validate

# List all loaded manifests of a given kind
oscilla content list Adventure --game my-game

# Run the engine against a specific adventure and print results
oscilla content test my-adventure --game my-game

# Scaffold a new manifest
oscilla content create Adventure --game my-game
```

---

## Contributing

```bash
git clone https://github.com/tedivm/oscilla.git
cd oscilla
make install          # install dependencies and set up .venv
cp .env.example .env  # configure local settings
docker compose up -d  # start database, Redis, and other services
make tests            # run the full test and lint suite
make chores           # auto-fix formatting
```

**Architecture and codebase reference:** [docs/system-overview.md](./docs/system-overview.md)

**Developer documentation index:** [docs/dev/README.md](./docs/dev/README.md)

**All documentation:** [docs/README.md](./docs/README.md)
