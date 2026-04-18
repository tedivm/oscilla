# Agent Instructions

You must always follow the best practices outlined in this document. If there is a valid reason why you cannot follow one of these practices, you must inform the user and document the reasons.

At the start of any session you MUST review the the [system overview](./docs/system-overview.md). This is vital to give you the appropriate system context to take any action.

You must also review code related to your request to understand preferred style: for example, you must review other tests before writing a new test suite, or review existing routers before creating a new one. This is to ensure you match the style, structure, and feel of the existing codebase.

## Important Commands

### Development Environment Setup

```bash
make install # Install dependencies and set up virtual environment
make sync # Sync dependencies with uv.lock
make pre-commit # Install pre-commit hooks
```

### File Operations

```bash
git mv old_path new_path # ALWAYS use git mv for moving or renaming files, never use mv or file manipulation tools
```

**CRITICAL**: When moving or renaming files in a git repository, you MUST use `git mv` instead of regular `mv` or file manipulation tools. This ensures git properly tracks the file history and prevents issues with version control. The only exception to this is if you are moving files which are not tracked in git, as in that case `git mv` will have no effect.

### Temporary Files

```bash
curl https://example.com > ./tmp/example.html # Use the local project tmp directory when you need to store files on desk that you do not want to save.

curl https://example.com > /tmp/example.html # BAD! Do NOT use the system tmp directory.
```

**CRITICAL**: Always use `./tmp` instead of `/tmp` when creating files. The local temporary directory (`./tmp`) has isolation in place that allows it to be used securely. Never attempt to write to `/tmp`.

### Testing and Validation

```bash
make tests # Run all tests and checks (pytest, ruff, format checks, mypy, prettier, TOML lint, schema checks, frontend checks)
make pytest # Run pytest with coverage report
make pytest_loud # Run pytest with debug logging enabled
uv run pytest # Run pytest directly with uv, adding any arguments and options needed
```

### Code Quality Checks

```bash
make ruff_check # Check code with ruff linter
make black_check # Check code formatting with ruff format using the black format
make mypy_check # Run type checking with mypy
make prettier_check # Check markdown/json/yaml/etc formatting with prettier
make tomlsort_check # Check TOML file linting and formatting
make paracelsus_check # Check generated database docs are up to date
make check_ungenerated_migrations # Ensure no missing Alembic migration changes
make validate # Validate content packages
```

### Code Formatting (Auto-fix)

```bash
make chores # Run all formatting fixes (ruff, format, prettier, TOML, frontend formatting, schema docs)
make ruff_fixes # Auto-fix ruff issues
make black_fixes # Auto-format code with ruff using the black format
make prettier_fixes # Auto-format markdown/json/yaml/etc
make tomlsort_fixes # Auto-format TOML files
make frontend_format_fix # Auto-format frontend source files
```

### Frontend Development and Testing

```bash
make frontend_install # Install frontend npm dependencies
make frontend_dev # Start Vite dev server
make frontend_build # Build frontend assets
make frontend_check # Run svelte-check
make frontend_test # Run vitest suite
make frontend_e2e # Run Playwright E2E via managed stack
make frontend_a11y # Run Playwright accessibility tests
make frontend_playwright_all # Run accessibility + E2E across chromium/firefox/webkit
```

### Dependency Management

```bash
make lock # Update and lock dependencies
make lock-check # Check if lock file is up to date
uv add package_name # Add a new package dependency
uv add --group dev package_name # Add a dev dependency
uv remove package_name # Remove a package dependency
```

### Database Operations

```bash
make create_migration MESSAGE="description of changes" # Create a new migration
make check_ungenerated_migrations # Check for ungenerated migrations
make document_schema # Update database schema documentation
```

### Packaging

```bash
make build # Build package distribution
```

### Docker

```bash
docker compose up -d # Start all services (gateway, backend, frontend, db, redis, mailhog)
docker compose down # Stop development environment (preserves volumes)
docker compose down -v # Stop and remove development environment (including volumes)
docker compose restart # Restart all services without destroying containers or volumes
docker compose logs # View logs from all services
docker compose logs -f # Follow logs in real-time from all services
docker compose logs -f service_name # Follow logs for a specific service
docker compose ps # List running services and their status
docker compose exec service_name bash # Open a bash shell in a running service container
```

### JSON Parsing

Always use the `jq` utility to parse json output from commands. Do _not_ create bespoke python scripts, even inline ones, simply to parse json.

## Best Practices

### General

- Assume the minimum version of Python is 3.12.
- Prefer async libraries and functions over synchronous ones.
- Always define dependencies and tool settings in `pyproject.toml`: never use `setup.py` or `setup.cfg` files.
- Prefer existing dependencies over adding new ones when possible.
- For complex code, always consider using third-party libraries instead of writing new code that has to be maintained.
- Use keyword arguments instead of positional arguments when calling functions and methods.
- Do not put `import` statements inside functions unless necessary to prevent circular imports. Imports must be at the top of the file.

### Personality

- Always use American English Spelling conventions (ie, normalizes instead of normalises).
- Treat the developer as a partner with deep subject matter expertise, but assume they are fallible and challenge requests or guidance that appears wrong.
- Do not make assumptions. When confronted with ambiguity or multiple options seek guidance from the developer.
- Speak concisely while still communicating: over communicate but avoid being overly verbose.

### Security

- Always write secure code.
- Never hardcode sensitive data.
- Do not log sensitive data.
- All user input must be validated.
- Never roll your own cryptography system.
- Always load YAML files in safe mode to prevent arbitrary Python object deserialization.

```python
# Good: safe mode prevents arbitrary Python object deserialization
from ruamel.yaml import YAML
_yaml = YAML(typ="safe")
data = _yaml.load(text)

# Bad: never use these
import yaml
yaml.load(text)          # unsafe — allows arbitrary object instantiation
YAML().load(text)        # unsafe — ruamel default is not safe mode
```

### Production Ready

- All generated code must be production ready.
- There must be no stubs "for production".
- There must not be any non-production logic branches in the main code package itself.
- Any code or package differences between Development and Production must be avoided unless absolutely necessary.

### Logging

- Do not use `print` for logging or debugging: use the `getLogger` logger instead.
- Each file must get its own logger using the `__name__` variable for a name.
- Use logging levels to allow developers to enable richer logging while testing than in production.
- Most caught exceptions must be logged with `logger.exception`.

```python
from logging import getLogger
from typing import Dict

logger = getLogger(__name__)

def process_data(data: Dict[str, str]) -> None:
    logger.debug("Starting data processing")
    try:
        result = transform_data(data)
        logger.info("Data processed successfully")
    except ValueError as e:
        logger.exception("Failed to process data")
        raise
```

### Commenting

- Comments must improve code readability and understandability.
- Comments must not simply exist for the sake of existing.
- Examples of good comments include unclear function names/parameters, decisions about settings or function choices, logic descriptions, variable definitions, security risks, edge cases, and advice for developers refactoring or expanding code.
- Comments must be concise, accurate, and add value to the codebase.

### Error Handling

- Do not suppress exceptions unless expected, and handle them properly when suppressing.
- When suppressing exceptions, log them using `logger.exception`.

```python
# Bad: Suppressing without handling
try:
    risky_operation()
except Exception:
    pass  # Never do this

# Good: Proper handling with logging
try:
    risky_operation()
except ValueError as e:
    logger.exception("Operation failed with invalid value")
    raise
except FileNotFoundError:
    logger.warning("File not found, using defaults")
    use_defaults()
```

### Typing

- Everything must be typed: function signatures (including return values), variables, and anything else.
- Use the union operator for multiple allowed types.
- Do not use `Optional`: use a union with `None` (i.e., `str | None`).
- Use typing library metaclasses instead of native types for objects and lists (i.e., `Dict[str, str]` and `List[str]` instead of `dict` or `list`).
- Avoid using `Any` unless absolutely necessary.
- If the schema is defined, use a `dataclass` with properly typed parameters instead of a `dict`.

```python
from dataclasses import dataclass
from typing import Dict, List

# Good: Proper typing
@dataclass
class User:
    name: str
    email: str
    age: int | None = None

def process_users(users: List[User], tags: Dict[str, str]) -> List[str]:
    results: List[str] = []
    for user in users:
        results.append(user.name)
    return results

# Bad: Using dict instead of dataclass (and using native types)
def process_users_bad(users: list[dict], config: dict) -> list:
    pass  # Avoid this
```

### Settings

- Manage application settings with the `pydantic-settings` library.
- The main Settings class is located in `oscilla/conf/settings.py` - update this existing class rather than creating new ones.
- Sensitive configuration data must always use Pydantic `SecretStr` or `SecretBytes` types.
- Settings that are allowed to be unset must default to `None` instead of empty strings.
- Define settings with the Pydantic `Field` function and include descriptions for users.

```python
# File: oscilla/conf/settings.py
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = Field(default="MyProject", description="Project name")

    # Good: Using SecretStr for sensitive data
    database_password: SecretStr = Field(
        description="Database password"
    )

    # Good: Optional field defaults to None
    api_key: SecretStr | None = Field(
        default=None,
        description="Optional API key for external service"
    )

    # Good: Using Field with description
    max_connections: int = Field(
        default=10,
        description="Maximum number of database connections"
    )
```

### FastAPI

- APIs must adhere as closely as possible to REST principles, including appropriate use of GET/PUT/POST/DELETE HTTP verbs.
- All routes must use Pydantic models for input and output.
- Use different Pydantic models for inputs and outputs (i.e., creating a `Post` must require a `PostCreate` and return a `PostRead` model, not reuse the same model).
- Parameters in Pydantic models for user input must use the Field function with validation and descriptions.
- All application routes must be registered under the `/api` prefix in `oscilla/www.py`. The only exceptions are `/health`, `/ready` (liveness/readiness probes — no `/api` prefix by convention), and `/static` (static file serving).
- The OpenAPI docs are served at `/api/docs` (Swagger UI), `/api/redoc` (ReDoc), and `/api/openapi.json`. Do not move them away from the `/api` scope.

```python
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()

class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="Post title")
    content: str = Field(min_length=1, description="Post content")

class PostRead(BaseModel):
    id: UUID
    title: str
    content: str
    created_at: str

class PostUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str | None = None

@router.post("/posts", response_model=PostRead, status_code=status.HTTP_201_CREATED)
async def create_post(post: PostCreate) -> PostRead:
    # Use different model for input (PostCreate) and output (PostRead)
    pass

@router.get("/posts/{post_id}", response_model=PostRead)
async def get_post(post_id: UUID) -> PostRead:
    pass

@router.put("/posts/{post_id}", response_model=PostRead)
async def update_post(post_id: UUID, post: PostUpdate) -> PostRead:
    pass

@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: UUID) -> None:
    pass
```

### SQLAlchemy

- Always use async SQLAlchemy APIs with SQLAlchemy 2.0 syntax.
- Represent database tables with the declarative class system.
- Use Alembic to define migrations.
- Migrations must be compatible with both SQLite and PostgreSQL.
- Never use JSON as a field unless explicitly asked by the developer.
- When creating queries, do not use implicit `and`: instead use the `and_` function (instead of `where(Model.parameter_a == A, Model.parameter_b == B)` do `where(and_(Model.parameter_a == A, Model.parameter_b == B))`).

```python
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from oscilla.models.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)

# Good: Async query with explicit and_()
async def get_active_user(session: AsyncSession, email: str, name: str) -> User | None:
    stmt = select(User).where(
        and_(
            User.email == email,
            User.name == name,
            User.is_active == True
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

# Bad: Implicit and (avoid this)
async def get_user_bad(session: AsyncSession, email: str, name: str) -> User | None:
    stmt = select(User).where(User.email == email, User.name == name)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
```

### Typer

- Any CLI command or script that must be accessible to users must be exposed via the Typer library.
- The main CLI entrypoint must be `PACKAGE_NAME/cli.py`.
- For async commands, use the `@syncify` decorator provided in `cli.py` to convert async functions to sync for Typer compatibility.

```python
import typer
from typing import Annotated

from oscilla.cli import syncify

app = typer.Typer()

@app.command()
def process(
    input_file: Annotated[str, typer.Argument(help="Path to input file")],
    output_file: Annotated[str | None, typer.Option(help="Path to output file")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
) -> None:
    """Process the input file and generate output."""
    if verbose:
        typer.echo(f"Processing {input_file}...")
    # Processing logic here
    typer.echo("Done!")

@app.command()
@syncify
async def fetch(
    url: Annotated[str, typer.Argument(help="URL to fetch data from")],
) -> None:
    """Fetch data from a URL asynchronously."""
    # Async operations here (database queries, HTTP requests, etc.)
    typer.echo(f"Fetching from {url}")

if __name__ == "__main__":
    app()
```

### Testing

- Do not wrap test functions in classes unless there is a specific technical reason: instead prefer single functions.
- All fixtures must be defined or imported in `conftest.py` so they are available to all tests.
- Do not use mocks to replace simple dataclasses or Pydantic models unless absolutely necessary: instead create an instance of the appropriate class with desired parameters.
- Use the FastAPI Test Client (preferably with a fixture) rather than calling FastAPI router classes directly.
- Use a test database fixture with memory-backed SQLite for tests requiring a database. Including a dependency override for this test database as part of the FastAPI App fixture is extremely useful.
- When adding new code, you must also add appropriate tests to cover that new code.
- The test suite file structure must mirror the main code file structure.

#### Game Engine Testing

- Engine tests must never reference the `content/` directory. Changing or replacing the POC content package must never break any test.
- For unit tests on already-loaded objects (conditions, player state, step handlers), construct Pydantic models and dataclasses directly in Python — no YAML loading required.
- For integration tests that exercise the loader or full pipeline, use a minimal fixture set from `tests/fixtures/content/<scenario>/` containing only the manifests needed for that test.
- Each distinct test scenario gets its own fixture subdirectory. Fixture manifests use a `test-` name prefix followed by the **kind or role** (e.g. `test-enemy`, `test-item`, `test-region-root`), never a content-flavoured name (e.g. never `test-goblin` or `test-sword`). This keeps fixtures unambiguously structural and prevents building narrative coherence inside test fixtures.
- The `mock_tui` fixture in `conftest.py` must be used to drive all pipeline tests. No test should produce real terminal output.

### Proposals

A proposal is an openspec change consisting of `proposal.md`, `design.md`, and `tasks.md`. Documentation and testing are **first-class deliverables**, not afterthoughts. Every proposal must address them at the same level of detail and specificity as the feature itself.

- Before writing a proposal or specification, you **must** use Context7 to pull current documentation for every library involved — both newly introduced libraries and existing dependencies whose APIs are relevant to the change. Design decisions must reflect the actual, up-to-date API rather than assumptions or stale knowledge.
- You _must_ review at least one recent `design.md` file to understand the expected level of detail and complexity of the design that you are proposing.
- `design.md` must include a **Documentation Plan** section that names every document to be created or updated, identifies its intended audience, and lists the specific topics it must cover. Vague statements like "update the docs" are not acceptable.
- `design.md` must include a **Testing Philosophy** section (or equivalent) that describes what tiers of tests apply, what fixtures are needed, and which behaviours are verified by tests. It must call out any constraints (e.g. no tests may reference `content/`).
- `tasks.md` must include dedicated sections for documentation tasks and testing tasks, at the same granularity as implementation tasks. Each doc and each meaningful test scenario must be its own line item.
- New developer documents must follow `docs/dev/` placement and naming rules and must be added to the table of contents in `docs/dev/README.md`. New content author documents must follow `docs/authors/` placement and naming rules and must be added to `docs/authors/README.md`.
- The documentation and testing sections of a proposal are reviewed with the same rigour as the implementation sections. A proposal that fully specifies the code but leaves documentation or testing vague is incomplete.
- When archiving proposals you **must** always sync deltas first, and you **must** update the Roadmap if you completed an item in it.

### Files

- Filenames must always be lowercase for better compatibility with case-insensitive filesystems.
- This includes documentation files, except standard files (like `README.md`, `LICENSE`, etc.).
- Developer documentation must live in `docs/dev`.
- New developer documents must be added to the table of contents in `docs/dev/README.md`.
- Content author documentation must live in `docs/authors`.
- New content author documents must be added to the table of contents in `docs/authors/README.md`.
- Files only meant for building containers must live in the `docker/` folder.
- Database models must live in `PACKAGE_NAME/models/`.
- The primary settings file must live in `PACKAGE_NAME/conf/settings.py`.

### Developer Environments

- Common developer tasks must be defined in the `makefile` to easy reuse.
- Developers must always be able to start a fully functional developer instance with `docker compose up`.
- Developer environments must be initialized with fake data for easy use.
- Developer settings must live in the `.env` file, which must be in `.gitignore`.
- A `.env.example` file must exist as a template for new developers to create their `.env` file and learn what variables to set.
- Python projects must always use virtual environments at `.venv` in the project root. This must be activated before running tests.
- Use `uv` for Python version management and package installation instead of pyenv and pip for significantly faster installations and automatic Python version handling.
