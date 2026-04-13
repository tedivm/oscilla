# Health Probes

## Purpose

Specifies the `GET /health` and `GET /ready` endpoints added in `oscilla/routers/health.py`. These endpoints are used by container orchestrators (Kubernetes, Docker Compose healthchecks) to determine whether the application process is alive and whether it is ready to serve traffic. Live health check never probes external dependencies so it cannot cause cascading failures; readiness check probes the database and cache to gate traffic routing.

---

## Requirements

### Requirement: GET /health returns 200 with no dependency checks

`GET /health` SHALL return HTTP 200 with a JSON response body conforming to `HealthResponse`. It SHALL NOT perform any database queries, cache lookups, or external network calls. Its only purpose is to confirm that the process is running and the event loop is responsive.

`HealthResponse` schema:

```json
{ "status": "ok" }
```

#### Scenario: health endpoint returns 200 immediately

- **GIVEN** a running application instance
- **WHEN** `GET /health` is requested
- **THEN** the response status is `200`
- **AND** the response body is `{"status": "ok"}`

#### Scenario: health endpoint requires no authentication

- **GIVEN** an unauthenticated client
- **WHEN** `GET /health` is requested
- **THEN** the response status is `200` (no 401 or 403)

---

### Requirement: GET /ready returns 200 when all dependencies are healthy

`GET /ready` SHALL probe the database by executing `SELECT 1` and probe the cache by calling the cache service's `ping` method (or equivalent connectivity check). If both probes succeed it SHALL return HTTP 200.

`ReadyResponse` schema:

```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "cache": "ok"
  }
}
```

#### Scenario: readiness returns 200 when database and cache are available

- **GIVEN** a running application with healthy database and cache connections
- **WHEN** `GET /ready` is requested
- **THEN** the response status is `200`
- **AND** `checks.database` is `"ok"`
- **AND** `checks.cache` is `"ok"`

#### Scenario: readiness requires no authentication

- **GIVEN** an unauthenticated client
- **WHEN** `GET /ready` is requested
- **THEN** the response status is `200` (no 401 or 403)

---

### Requirement: GET /ready returns 503 when any dependency is unavailable

If the database probe raises an exception, `checks.database` SHALL be set to `"error"` and the overall response `status` SHALL be `"error"`. If the cache probe raises an exception, `checks.cache` SHALL be set to `"error"` and the overall status SHALL be `"error"`. Either failure results in HTTP 503. Both failures are captured independently so the response body reports the state of each check even when multiple dependencies are down.

`ReadyResponse` schema when unhealthy:

```json
{
  "status": "error",
  "checks": {
    "database": "error",
    "cache": "ok"
  }
}
```

All dependency exceptions SHALL be caught and logged at `ERROR` level with `logger.exception` before setting the check status to `"error"`. Exceptions SHALL NOT propagate to the framework error handler (which would return an unstructured 500).

#### Scenario: readiness returns 503 when database is unavailable

- **GIVEN** a running application where the database connection raises an exception
- **WHEN** `GET /ready` is requested
- **THEN** the response status is `503`
- **AND** the response body contains `"status": "error"`
- **AND** `checks.database` is `"error"`

#### Scenario: readiness returns 503 when cache is unavailable

- **GIVEN** a running application where the cache ping raises an exception
- **WHEN** `GET /ready` is requested
- **THEN** the response status is `503`
- **AND** `checks.cache` is `"error"`

#### Scenario: readiness reports each check independently when multiple dependencies fail

- **GIVEN** a running application where both database and cache are unavailable
- **WHEN** `GET /ready` is requested
- **THEN** the response status is `503`
- **AND** `checks.database` is `"error"`
- **AND** `checks.cache` is `"error"`

---

### Requirement: Health router is mounted at the application root

`oscilla/routers/health.py` SHALL define a `router = APIRouter(tags=["health"])` and include it in `oscilla/www.py` with no prefix so both probes are reachable at `/health` and `/ready`.

The router SHALL use `response_model` on both endpoints so the output schema appears in the OpenAPI docs.
