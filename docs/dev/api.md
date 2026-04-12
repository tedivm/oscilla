# FastAPI

This project uses [FastAPI](https://fastapi.tiangolo.com/), a modern, fast web framework for building APIs with Python based on standard Python type hints.

## Application Structure

The FastAPI application is defined in `oscilla/www.py` and includes:

- **Automatic API documentation** at `/docs` (Swagger UI) and `/redoc` (ReDoc)
- **Static file serving** from `oscilla/static/` via the `/static/` endpoint
- **OpenAPI schema** available at `/openapi.json`
- **Root redirect** from `/` to `/docs` for convenient access to documentation

## Configuration

### Environment Variables

FastAPI-specific settings can be configured through environment variables in the Settings class:

- **PROJECT_NAME**: The name of the project (displayed in API docs)
- **DEBUG**: Enable debug mode (default: `False`)
  - Shows detailed error messages
  - Enables hot-reload in development

### Startup Events

The application automatically initializes required services on startup:

- **Cache initialization**: If aiocache is enabled, caches are configured and ready

Note: Database connections are NOT initialized at startup. Instead, they are established lazily when first accessed via dependency injection (see Database Integration section below).

## Adding Routes

### Basic Route

Create a new route in `oscilla/www.py`:

```python
@app.get("/hello")
async def hello_world():
    return {"message": "Hello, World!"}
```

### Route with Path Parameters

```python
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    # FastAPI automatically validates user_id is an integer
    return {"user_id": user_id, "name": "John Doe"}
```

### Route with Query Parameters

```python
from typing import Optional

@app.get("/items")
async def list_items(skip: int = 0, limit: int = 10, search: Optional[str] = None):
    # Query params: ?skip=0&limit=10&search=foo
    return {"skip": skip, "limit": limit, "search": search}
```

### Route with Request Body

```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None

@app.post("/users")
async def create_user(user: UserCreate):
    # FastAPI automatically validates and deserializes the JSON body
    return {"user": user.dict(), "id": 123}
```

## Response Models

Use Pydantic models to define response schemas:

```python
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    # FastAPI ensures the response matches UserResponse schema
    return {
        "id": user_id,
        "username": "johndoe",
        "email": "john@example.com",
        "created_at": datetime.now()
    }
```

## Dependency Injection

FastAPI's dependency injection system allows you to share logic across routes:

```python
from fastapi import Depends, HTTPException

async def get_current_user(token: str = Header(...)):
    # Validate token and get user
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"username": "johndoe"}

@app.get("/me")
async def read_current_user(current_user: dict = Depends(get_current_user)):
    return current_user
```

## Database Integration

If SQLAlchemy is enabled, use dependency injection for database sessions:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from oscilla.services.db import get_session_depends

@app.get("/users")
async def list_users(session: AsyncSession = Depends(get_session_depends)):
    result = await session.execute(select(User))
    users = result.scalars().all()
    return users
```

## Error Handling

### Custom Exception Handlers

```python
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )
```

### Raising HTTP Exceptions

```python
from fastapi import HTTPException

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    user = await fetch_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

## Static Files

Static files are served from `oscilla/static/`:

1. **Add files** to the `static/` directory:

   ```
   oscilla/static/
   ├── css/
   │   └── styles.css
   ├── js/
   │   └── app.js
   └── images/
       └── logo.png
   ```

2. **Access files** via the `/static/` URL path:
   - `http://localhost:8000/static/css/styles.css`
   - `http://localhost:8000/static/images/logo.png`

## Middleware

Add middleware for cross-cutting concerns:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Background Tasks

Run tasks in the background without blocking the response:

```python
from fastapi import BackgroundTasks

def send_email(email: str, message: str):
    # Send email logic here
    print(f"Sending email to {email}: {message}")

@app.post("/send-notification")
async def send_notification(
    email: str,
    background_tasks: BackgroundTasks
):
    background_tasks.add_task(send_email, email, "Hello from FastAPI!")
    return {"message": "Notification will be sent"}
```

## Testing

### Using the FastAPI Client Fixture

The project includes a `fastapi_client` fixture in `tests/conftest.py` that provides a TestClient instance. Use this fixture in your tests:

```python
# tests/conftest.py
import pytest_asyncio
from fastapi.testclient import TestClient
from oscilla.www import app


@pytest_asyncio.fixture
async def fastapi_client():
    """Fixture to create a FastAPI test client."""
    client = TestClient(app)
    yield client
```

### Writing Tests with the Fixture

Use the `fastapi_client` fixture in your test functions:

```python
# tests/test_www.py

def test_root_redirects_to_docs(fastapi_client):
    """Test that root path redirects to /docs."""
    response = fastapi_client.get("/", follow_redirects=False)
    assert response.status_code == 307  # Temporary redirect
    assert response.headers["location"] == "/docs"


def test_root_redirect_follows(fastapi_client):
    """Test that following redirect from root goes to docs."""
    response = fastapi_client.get("/", follow_redirects=True)
    assert response.status_code == 200
    # Should reach the OpenAPI docs page


def test_api_endpoint(fastapi_client):
    """Test a custom API endpoint."""
    response = fastapi_client.get("/api/users/123")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 123
```

### Testing POST Requests

```python
def test_create_user(fastapi_client):
    """Test creating a user via POST."""
    user_data = {
        "username": "testuser",
        "email": "test@example.com"
    }
    response = fastapi_client.post("/api/users", json=user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data
```

### Testing with Headers

```python
def test_authenticated_endpoint(fastapi_client):
    """Test endpoint that requires authentication."""
    headers = {"Authorization": "Bearer test-token"}
    response = fastapi_client.get("/api/me", headers=headers)
    assert response.status_code == 200
```

## Running the Application

### Development

```bash
# Using uvicorn directly
uvicorn oscilla.www:app --reload --host 0.0.0.0 --port 8000

# The app is accessible at http://localhost:8000
# API docs available at http://localhost:8000/docs
```

### Production

```bash
# With more workers for production
uvicorn oscilla.www:app --host 0.0.0.0 --port 8000 --workers 4

# Or using gunicorn with uvicorn workers
gunicorn oscilla.www:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Docker

If Docker is configured, use docker-compose:

```bash
docker-compose up www
```

## Best Practices

1. **Use Response Models**: Always define Pydantic models for responses to ensure type safety and automatic documentation

2. **Leverage Dependency Injection**: Use `Depends()` to share logic like authentication, database sessions, and configuration

3. **Async All the Way**: Use `async def` for route handlers when performing I/O operations (database, external APIs, file operations)

4. **Validate Input**: Leverage Pydantic's validation for request bodies and FastAPI's parameter validation for path and query parameters

5. **Document Your API**: Add docstrings to route functions - they appear in the auto-generated docs:

   ```python
   @app.get("/users")
   async def list_users():
       """
       Retrieve a list of all users.

       Returns a paginated list of user objects with their basic information.
       """
       return users
   ```

6. **Use HTTP Status Codes**: Return appropriate status codes (201 for created, 204 for no content, etc.):

   ```python
   from fastapi import status

   @app.post("/users", status_code=status.HTTP_201_CREATED)
   async def create_user(user: UserCreate):
       return {"user": user}
   ```

7. **Separate Concerns**: Keep business logic separate from route handlers - use service layers or utility modules

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Uvicorn Documentation](https://www.uvicorn.org/)

## Authentication Endpoints

The `/auth` router handles user registration, login, token refresh, and email
verification. For a full description of the authentication system see
[Authentication](./authentication.md).

| Method | Path                           | Auth required | Description                             |
| ------ | ------------------------------ | ------------- | --------------------------------------- |
| POST   | `/auth/register`               | No            | Create a new account (201)              |
| POST   | `/auth/login`                  | No            | Exchange credentials for tokens         |
| POST   | `/auth/refresh`                | No            | Rotate refresh token, get new pair      |
| POST   | `/auth/logout`                 | No            | Revoke refresh token (204)              |
| POST   | `/auth/request-verify`         | Bearer JWT    | Resend verification email (204)         |
| GET    | `/auth/verify/{token}`         | No            | Verify email address (204)              |
| POST   | `/auth/request-password-reset` | No            | Send password-reset email (204)         |
| POST   | `/auth/password-reset/{token}` | No            | Set new password with reset token (204) |
| GET    | `/auth/me`                     | Bearer JWT    | Get current user profile                |
| PATCH  | `/auth/me`                     | Bearer JWT    | Update display name / password          |

All endpoints are documented interactively at `/docs`.

## Games Endpoints

The `/games` router exposes read-only discovery endpoints for loaded game
packages. These endpoints are unauthenticated.

| Method | Path                 | Auth required | Description                           |
| ------ | -------------------- | ------------- | ------------------------------------- |
| GET    | `/games`             | No            | List all loaded games as `GameRead[]` |
| GET    | `/games/{game_name}` | No            | Get one loaded game as `GameRead`     |

`GameRead` includes:

- `name`: machine-readable game key (from manifest metadata)
- `display_name`: game display name (from `game.yaml`)
- `description`: nullable game description
- `features`: derived `GameFeatureFlags` from the live `ContentRegistry`

`GameFeatureFlags` fields:

- `has_skills`
- `has_quests`
- `has_archetypes`
- `has_ingame_time` (true when `registry.game.spec.time` is present)
- `has_recipes`
- `has_loot_tables`

## Characters Endpoints

The `/characters` router exposes authenticated character CRUD APIs. All routes
require a Bearer JWT and enforce ownership using the current user id.

| Method | Path               | Auth required | Description                                            |
| ------ | ------------------ | ------------- | ------------------------------------------------------ |
| GET    | `/characters`      | Bearer JWT    | List the caller's characters (`?game=<name>` optional) |
| POST   | `/characters`      | Bearer JWT    | Create a character for a loaded game (201)             |
| GET    | `/characters/{id}` | Bearer JWT    | Get full `CharacterStateRead`                          |
| PATCH  | `/characters/{id}` | Bearer JWT    | Rename character (`name`)                              |
| DELETE | `/characters/{id}` | Bearer JWT    | Delete character (204)                                 |

### CharacterStateRead Field Reference

| Category  | Fields                                                                                                              |
| --------- | ------------------------------------------------------------------------------------------------------------------- |
| Identity  | `id`, `name`, `game_name`, `character_class`, `prestige_count`, `pronoun_set`, `created_at`                         |
| Location  | `current_location`, `current_location_name`, `current_region_name`                                                  |
| Stats     | `stats: Dict[str, StatValue]`                                                                                       |
| Inventory | `stacks: Dict[str, StackedItemRead]`, `instances: List[ItemInstanceRead]`, `equipment: Dict[str, ItemInstanceRead]` |
| Skills    | `skills: List[SkillRead]`                                                                                           |
| Buffs     | `active_buffs: List[BuffRead]`                                                                                      |
| Quests    | `active_quests: List[ActiveQuestRead]`, `completed_quests: List[str]`, `failed_quests: List[str]`                   |
| Progress  | `internal_ticks`, `game_ticks`, `active_adventure`                                                                  |

`stats` always includes all declared stats from `character_config.yaml`,
including unset or derived stats where `StatValue.value` is `null`.

## Registry Loading and get_registry Dependency

At startup, `oscilla/www.py` scans `settings.games_path` for child directories
containing `game.yaml` and calls `load_from_disk(...)` for each game package.
Loaded registries are stored in `app.state.registries: Dict[str, ContentRegistry]`
keyed by game name.

- If an individual game fails to load, the error is logged and startup continues.
- New or changed game content requires a server restart to be reloaded.

The `get_registry(game_name, request)` dependency in
`oscilla/dependencies/games.py` resolves a registry from
`request.app.state.registries` and raises HTTP 404 when missing.

## Adventure Execution Endpoints

The `/play/` family of endpoints streams adventure execution to the browser
using [Server-Sent Events (SSE)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
and integrates session locking and crash recovery.

### Endpoint Reference

| Method | Path                             | Auth       | Description                                           |
| ------ | -------------------------------- | ---------- | ----------------------------------------------------- |
| GET    | `/characters/{id}/play/current`  | Bearer JWT | Return persisted session output for crash recovery    |
| POST   | `/characters/{id}/play/begin`    | Bearer JWT | Begin an adventure and stream SSE events (200 or 409) |
| POST   | `/characters/{id}/play/advance`  | Bearer JWT | Submit a player decision and continue streaming       |
| POST   | `/characters/{id}/play/abandon`  | Bearer JWT | Exit the current adventure (204)                      |
| POST   | `/characters/{id}/play/takeover` | Bearer JWT | Force-acquire a stale session lock (returns state)    |

### SSE Event Type Contract

All streaming responses (`begin`, `advance`) emit newline-delimited SSE
blocks with an `event:` line and a `data:` JSON payload:

```
event: narrative
data: {"text": "...", "context": {"location_ref": "...", ...}}

event: choice
data: {"prompt": "...", "options": ["...", "..."], "context": {...}}
```

| Event type     | Emitted when                                             | Decision event? |
| -------------- | -------------------------------------------------------- | --------------- |
| `narrative`    | A narrative step displays text                           | No              |
| `choice`       | A menu step awaits player selection                      | Yes — pauses    |
| `ack_required` | A narrative step awaits acknowledgement before advancing | Yes — pauses    |
| `text_input`   | A step requires freeform text from the player            | Yes — pauses    |
| `skill_menu`   | A step awaits a skill selection                          | Yes — pauses    |
| `combat_state` | A combat round reports current HP values                 | No              |
| `complete`     | The adventure finished successfully                      | No              |

The stream terminates after the first **decision event** (pipeline pauses for
input) or after `complete`. The client should read all events before sending
the follow-up `advance` request.

### Session Locking

`begin` and `advance` each acquire a short-lived session lock to prevent
concurrent execution on the same character. The lock is stored in
`session_token` + `session_token_acquired_at` on the
`character_iterations` row and is released automatically when the SSE
stream closes.

If a non-stale lock exists, the endpoint returns **409 Conflict** with a
`SessionConflictRead` body:

```json
{
  "detail": "A live session is already in progress.",
  "acquired_at": "2024-01-01T00:00:00Z",
  "character_id": "..."
}
```

The stale-lock threshold defaults to **10 minutes** and is configurable via
`STALE_SESSION_THRESHOLD_MINUTES` in settings.

### Crash Recovery

Every SSE event emitted during a session is appended to the
`character_session_output` table, keyed by `iteration_id`. If the client
loses the connection mid-stream, it can call `GET /play/current` to replay
all received events and determine the pending decision event without
re-running the adventure.

`GET /play/current` returns a `PendingStateRead`:

```json
{
  "character_id": "...",
  "pending_event": {"type": "choice", "data": {...}},
  "session_output": [...]
}
```

`pending_event` is `null` for a fresh character or after an adventure
completes. `session_output` is cleared when `begin` starts a new adventure
and when `abandon` resets state.

### Takeover Flow

`POST /play/takeover` force-acquires the session lock regardless of whether
it is stale. It returns the same `PendingStateRead` as `GET /play/current`.
The client should call `advance` (or `abandon`) after takeover.

## Overworld Endpoints

The overworld endpoints expose the character's current world position,
available adventures, reachable locations, and a region sub-graph for map
rendering.

### Endpoint Reference

| Method | Path                         | Auth       | Description                                              |
| ------ | ---------------------------- | ---------- | -------------------------------------------------------- |
| GET    | `/characters/{id}/overworld` | Bearer JWT | Return full `OverworldStateRead` for the character       |
| POST   | `/characters/{id}/navigate`  | Bearer JWT | Teleport character to a new location (returns new state) |

### OverworldStateRead Schema

| Field                   | Type                    | Description                                      |
| ----------------------- | ----------------------- | ------------------------------------------------ |
| `character_id`          | `UUID`                  | Character identifier                             |
| `current_location`      | `str \| null`           | Machine ref of current location                  |
| `current_location_name` | `str \| null`           | Display name of current location                 |
| `current_region_name`   | `str \| null`           | Display name of current region                   |
| `available_adventures`  | `AdventureOptionRead[]` | Adventures in the location's pool                |
| `navigation_options`    | `LocationOptionRead[]`  | All locations in the same region (incl. current) |
| `region_graph`          | `RegionGraphRead`       | Node/edge neighborhood of the current region     |

`navigate` validates the destination exists and that all `effective_unlock`
conditions pass; returns **422** otherwise.

### Region Graph

`region_graph` contains the region sub-graph neighborhood scoped to the
character's current region, produced by `build_world_graph()` +
`_filter_to_neighborhood()`. Nodes carry an `id` (prefixed `region:` or
`location:`), a human-readable `label`, and a `kind` property. Edges have
`source`, `target`, and `label` fields.
