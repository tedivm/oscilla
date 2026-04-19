---
name: python-testing
description: "Write or modify Python tests in Oscilla. Use when: adding new tests, understanding testing conventions, working with fixtures, writing FastAPI route tests, database tests, or game engine tests. Covers pytest patterns, fixture structure, and the game engine testing constraints."
---

# Python Testing

> **context7**: If the `mcp_context7` tool is available, resolve and load the full `pytest` documentation before creating new tests or running pytests commands not in the makefile:
> ```
> mcp_context7_resolve-library-id: "pytest"
> mcp_context7_get-library-docs: <resolved-id>
> ```

Guidelines and patterns for writing tests in the Oscilla codebase.

---

## General Rules

- **No test classes** unless there is a specific technical reason. Prefer standalone functions.
- **All fixtures** must be defined or imported in `conftest.py` so they are automatically available to all tests in that directory.
- **No mocks for simple dataclasses or Pydantic models** — construct an instance directly with the desired parameters instead.
- **Test file structure mirrors the main code** — a test for `oscilla/engine/foo.py` lives at `tests/engine/test_foo.py`.

---

## Running Tests

```bash
make pytest              # Run full test suite with coverage report
make pytest_loud         # Run with debug logging enabled
uv run pytest            # Run directly — append any pytest options/arguments
uv run pytest tests/engine/test_foo.py -k test_my_function -s
```

---

## FastAPI Tests

Use the FastAPI `TestClient` via a fixture rather than calling router classes directly.

```python
import pytest
from fastapi.testclient import TestClient
from oscilla.www import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_get_post(client: TestClient) -> None:
    response = client.get("/api/posts/some-uuid")
    assert response.status_code == 200
```

---

## Database Tests

Use a memory-backed SQLite fixture. Wire it into the FastAPI app via a dependency override so routes use the test database automatically.

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from oscilla.models.base import Base
from oscilla.dependencies.database import get_session


@pytest.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def client(db_session: AsyncSession) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    return TestClient(app)
```

---

## Game Engine Testing

The game engine has strict isolation requirements to keep tests independent of live content.

### Critical Rules

1. **Engine tests must never reference `content/`**. Replacing or modifying the content package must never break any test.
2. **Unit tests** (conditions, player state, step handlers) — construct Pydantic models and dataclasses directly in Python. No YAML loading required.
3. **Integration tests** that exercise the loader or full pipeline — use minimal fixtures from `tests/fixtures/content/<scenario>/`.

### Fixture Structure

Each test scenario gets its own subdirectory:

```
tests/fixtures/content/
├── basic-region/
│   ├── game.yaml
│   └── regions/
│       └── test-region-root.yaml
├── item-pickup/
│   └── ...
```

**Naming rules for fixture manifests:**
- Use `test-` prefix followed by the **kind or role** (e.g., `test-enemy`, `test-item`, `test-region-root`)
- **Never** use content-flavored names (e.g., never `test-goblin`, `test-sword`, `test-dark-forest`)
- This keeps fixtures structurally descriptive and prevents building narrative coherence inside the test suite

```yaml
# Good: test-enemy.yaml
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: test-enemy
spec:
  health: 10
  damage: 2

# Bad: test-goblin.yaml  ← never use narrative names
```

### `mock_tui` Fixture

The `mock_tui` fixture in `conftest.py` must be used to drive all pipeline tests. No test should produce real terminal output.

```python
def test_adventure_runs(mock_tui: MockTUI) -> None:
    # mock_tui captures all TUI output without rendering to terminal
    ...
```

---

## Fixture Conventions

- Fixtures shared across multiple test files → `tests/conftest.py`
- Fixtures specific to a subdirectory → `tests/<subdirectory>/conftest.py`
- Complex fixture content (YAML files, etc.) → `tests/fixtures/`

---

## Style Checklist

- [ ] Test is a standalone function (no wrapping class)
- [ ] Fixtures defined/imported in `conftest.py`
- [ ] No mocks for dataclasses or Pydantic models — use real instances
- [ ] Database tests use memory SQLite with dependency override
- [ ] FastAPI tests use `TestClient` fixture
- [ ] Engine tests do not reference `content/` directory
- [ ] Fixture YAML names use `test-<kind>` pattern (no narrative names)
- [ ] Pipeline tests use `mock_tui` fixture
- [ ] Test file location mirrors the module being tested

---

## Further Reading

- [docs/dev/testing.md](../../docs/dev/testing.md) — Full testing developer guide covering pytest configuration, coverage reporting, async test patterns, database test fixtures, and CI integration.
- [pytest Docs](https://docs.pytest.org/)
- [pytest-asyncio Docs](https://pytest-asyncio.readthedocs.io/)
