# Security Middleware

## Purpose

Specifies the three HTTP middleware layers added to `oscilla/www.py`: `SecurityHeadersMiddleware` (OWASP response headers), `CORSMiddleware` (configurable origin allowlist), and `RequestLoggingMiddleware` (structured per-request logging with request IDs). All three are implemented as FastAPI middleware with zero new infrastructure dependencies.

---

## Requirements

### Requirement: SecurityHeadersMiddleware injects OWASP response headers

`oscilla/middleware/security_headers.py` SHALL define `SecurityHeadersMiddleware(BaseHTTPMiddleware)`. Its `dispatch` method SHALL call `call_next(request)` and add the following headers to every response before returning:

| Header                      | Value                                                                                                                                       |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains`                                                                                                       |
| `X-Content-Type-Options`    | `nosniff`                                                                                                                                   |
| `X-Frame-Options`           | `DENY`                                                                                                                                      |
| `Content-Security-Policy`   | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'` |
| `Referrer-Policy`           | `strict-origin-when-cross-origin`                                                                                                           |

The `unsafe-inline` in `style-src` is required because SvelteKit injects inline `<style>` blocks in the generated HTML served from the static build. This is the minimum viable CSP for MU6; nonce-based CSP is a future improvement.

Both `X-Frame-Options: DENY` and `frame-ancestors 'none'` in the CSP are intentionally redundant: `X-Frame-Options` provides clickjacking protection for browsers that do not support CSP `frame-ancestors`.

#### Scenario: all five headers are present on every response

- **GIVEN** a running application with `SecurityHeadersMiddleware` registered
- **WHEN** any HTTP request is made (e.g., `GET /health`)
- **THEN** the response contains all five headers listed above with the exact values specified

#### Scenario: HSTS header includes includeSubDomains

- **GIVEN** a response from any endpoint
- **THEN** `Strict-Transport-Security` contains `includeSubDomains`

#### Scenario: CSP denies framing via both mechanisms

- **GIVEN** a response from any endpoint
- **THEN** `Content-Security-Policy` contains `frame-ancestors 'none'`
- **AND** `X-Frame-Options` is `DENY`

---

### Requirement: CORSMiddleware allows configured origins only

FastAPI's `CORSMiddleware` SHALL be added with `allow_origins=settings.cors_origins`, `allow_credentials=True`, `allow_methods=["*"]`, and `allow_headers=["*"]`. The default value of `cors_origins` is `["http://localhost:5173"]` (the SvelteKit dev server). In production, operators set `CORS_ORIGINS='["https://play.example.com"]'` in their `.env` file.

The middleware SHALL be registered last (innermost) so it handles CORS preflight before security headers are applied.

#### Scenario: preflight from allowed origin returns CORS headers

- **GIVEN** `cors_origins = ["http://localhost:5173"]`
- **WHEN** an `OPTIONS` request arrives with `Origin: http://localhost:5173`
- **THEN** the response contains `Access-Control-Allow-Origin: http://localhost:5173`

#### Scenario: preflight from disallowed origin does not return permissive header

- **GIVEN** `cors_origins = ["http://localhost:5173"]`
- **WHEN** an `OPTIONS` request arrives with `Origin: https://evil.example.com`
- **THEN** the response does NOT contain `Access-Control-Allow-Origin: *` or `Access-Control-Allow-Origin: https://evil.example.com`

---

### Requirement: RequestLoggingMiddleware logs structured per-request records

`oscilla/middleware/request_logging.py` SHALL define `RequestLoggingMiddleware(BaseHTTPMiddleware)`. For every request it SHALL:

1. Generate a `request_id` UUID and set it on `request.state.request_id`.
2. Log `"request_start"` at `INFO` with `extra` containing `request_id`, `method`, and `path`.
3. Call `call_next(request)` and measure elapsed time via `time.monotonic()`.
4. After the response is received, read `user_id = getattr(request.state, "user_id", None)` (set by `get_current_user` for authenticated requests).
5. Log `"request_end"` at `INFO` with `extra` containing `request_id`, `status_code`, `duration_ms` (integer milliseconds), and `user_id` (string UUID or `None`).

The middleware SHALL be the outermost layer — registered first in `www.py` so it wraps the entire request lifecycle including CORS and security header processing.

#### Scenario: request_start is logged with request_id

- **GIVEN** `RequestLoggingMiddleware` is active
- **WHEN** any HTTP request is made
- **THEN** a log record with message `"request_start"` is emitted at `INFO`
- **AND** the record's `extra["request_id"]` is a valid UUID string

#### Scenario: request_end is logged with status_code and duration

- **GIVEN** `RequestLoggingMiddleware` is active
- **WHEN** any HTTP request completes
- **THEN** a log record with message `"request_end"` is emitted at `INFO`
- **AND** `extra["status_code"]` matches the response status code
- **AND** `extra["duration_ms"]` is an integer `>= 0`

#### Scenario: user_id is null for unauthenticated requests

- **GIVEN** an unauthenticated `GET /health` request
- **WHEN** the `"request_end"` log record is emitted
- **THEN** `extra["user_id"]` is `None`

#### Scenario: user_id is set for authenticated requests

- **GIVEN** a request where `get_current_user` successfully resolves and sets `request.state.user_id`
- **WHEN** the `"request_end"` log record is emitted
- **THEN** `extra["user_id"]` is the string form of the authenticated user's UUID

---

### Requirement: Middleware registration order in <www.py>

Middleware SHALL be registered in `oscilla/www.py` in the following order (first registered = outermost in execution):

```python
app.add_middleware(RequestLoggingMiddleware)   # 1. registered first → outermost
app.add_middleware(SecurityHeadersMiddleware)  # 2.
app.add_middleware(CORSMiddleware, ...)        # 3. registered last → innermost
```

FastAPI applies middleware in reverse registration order (last-added wraps first), so the execution order is RequestLogging → SecurityHeaders → CORS → route handler → CORS → SecurityHeaders → RequestLogging.

A comment in `www.py` SHALL explain this reverse-registration ordering to prevent future contributors from inadvertently reordering the declarations.
