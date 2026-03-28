# oscilla



## Installation

```bash
pip install oscilla
```

## Playing Locally

Oscilla requires a content package — a directory of YAML manifests that define the game world. By default it looks for a `content/` directory in the project root. You can point it at any content package via the `CONTENT_PATH` environment variable.

```bash
# Validate your content package (check for errors before playing)
uv run oscilla validate

# Start an interactive game session
uv run oscilla game

# Use a custom content directory
CONTENT_PATH=/path/to/my-content uv run oscilla game
```

## CLI

```bash
uv run oscilla --help
```

## Developer Documentation

Comprehensive developer documentation is available in [`docs/dev/`](./docs/dev/) covering testing, configuration, deployment, and all project features.

### Quick Start for Developers

```bash
# Install development environment
make install

# Start services with Docker
docker compose up -d

# Run tests
make tests

# Auto-fix formatting
make chores
```

See the [developer documentation](./docs/dev/README.md) for complete guides and reference.
