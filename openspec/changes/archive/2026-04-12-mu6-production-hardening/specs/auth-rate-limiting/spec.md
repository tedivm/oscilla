# Auth Rate Limiting

## Purpose

Specifies the rate limiting and account lockout controls on auth endpoints in `oscilla/routers/auth.py` using the existing `aiocache` `"persistent"` cache alias. These controls protect against brute-force credential attacks without introducing new infrastructure dependencies.

---

## Requirements

### Requirement: `POST /auth/login` is rate-limited per email address

The login endpoint SHALL reject requests that exceed `settings.max_login_attempts_per_hour` (default 10) for a given email address within a rolling 3600-second window by returning `HTTP 429 Too Many Requests`.

The rate limit SHALL be enforced before any database query or password verification to prevent user enumeration via timing differences.

With `cache_enabled=False` (the default test and development configuration), the `NoOpCache._increment` method returns `delta=1` on every call, causing the `count <= max_attempts` check to always pass. Rate limiting is transparently disabled — no test or development configuration change is required.

#### Scenario: login within limit returns token pair

- **GIVEN** an authenticated user and `max_login_attempts_per_hour = 10`
- **WHEN** the user submits 10 sequential valid login requests
- **THEN** all 10 requests return `HTTP 200` with a `TokenPairRead`

#### Scenario: login exceeding per-hour limit returns 429

- **GIVEN** a real Redis-backed cache where the counter has reached `max_login_attempts_per_hour`
- **WHEN** another login request is submitted for the same email
- **THEN** the response is `HTTP 429` with `detail: "Too many login attempts. Try again later."`
- **AND** no database query is executed

#### Scenario: rate limit is disabled with NoOpCache

- **GIVEN** `cache_enabled = False` (default test environment)
- **WHEN** 100 sequential login requests are submitted
- **THEN** none return `HTTP 429`

---

### Requirement: `POST /auth/register` is rate-limited per client IP address

The register endpoint SHALL reject requests exceeding `settings.max_registrations_per_hour_per_ip` (default 5) from a single IP address within a rolling 3600-second window by returning `HTTP 429 Too Many Requests`.

The IP address SHALL be extracted from `request.client.host`. If `request.client` is `None`, the key SHALL use `"unknown"` as the IP component.

The rate limit check SHALL occur before any DB query.

#### Scenario: registrations within IP limit succeed

- **GIVEN** `max_registrations_per_hour_per_ip = 5`
- **WHEN** 5 registration requests arrive from the same IP
- **THEN** all 5 are processed normally (success or appropriate business error, not 429)

#### Scenario: registrations exceeding IP limit return 429

- **GIVEN** a real Redis-backed cache where the IP counter has reached the limit
- **WHEN** another registration from the same IP is attempted
- **THEN** the response is `HTTP 429` with a rate limit detail message

---

### Requirement: Account lockout after consecutive failed logins

The login endpoint SHALL lock an account after `settings.max_login_attempts_before_lockout` (default 5) consecutive failed password verifications within `settings.lockout_window_seconds` (default 300 seconds). A locked account SHALL return `HTTP 423 Locked` on subsequent login attempts for `settings.lockout_duration_minutes` (default 15 minutes), regardless of whether the submitted password is correct.

On any successful login, the lockout counter and lockout flag SHALL both be cleared.

#### Scenario: failed login below threshold does not lock

- **GIVEN** `max_login_attempts_before_lockout = 5`
- **WHEN** a user submits 4 consecutive wrong passwords
- **THEN** all 4 return `HTTP 401 Unauthorized`
- **AND** the account is NOT locked

#### Scenario: failed login at threshold sets lockout

- **GIVEN** a Redis-backed cache and a user with `max_login_attempts_before_lockout = 5`
- **WHEN** the user submits 5 consecutive wrong passwords
- **THEN** the 5th attempt sets the `lockout:{email}` key and returns `HTTP 401`
- **AND** the next attempt (6th) returns `HTTP 423 Locked`

#### Scenario: correct password after lockout returns 423

- **GIVEN** an account is locked (the `lockout:{email}` key exists in cache)
- **WHEN** the user submits the correct password
- **THEN** the response is `HTTP 423 Locked`
- **AND** the lockout is NOT cleared (correct password does not bypass lockout)

#### Scenario: successful login clears lockout

- **GIVEN** an account has 3 failed attempts recorded in `lockout_count:{email}` but is NOT yet locked
- **WHEN** the user logs in successfully
- **THEN** `clear_lockout` deletes both `lockout:{email}` and `lockout_count:{email}`
- **AND** the response is `HTTP 200`

#### Scenario: lockout is disabled with NoOpCache

- **GIVEN** `cache_enabled = False` (default test environment)
- **WHEN** 10 sequential failed login requests are submitted
- **THEN** none return `HTTP 423` (NoOpCache `exists` always returns `False`)

---

### Requirement: `check_rate_limit` is a reusable service function

`oscilla/services/rate_limit.py` SHALL export `check_rate_limit(key: str, max_attempts: int, window_seconds: int) -> bool`. It SHALL use `caches.get("persistent")` to atomically increment the counter, set the TTL only on the first increment (when the returned count equals `delta`), and return `True` (allowed) or `False` (blocked).

#### Scenario: check_rate_limit returns True at and below threshold

- **GIVEN** a Redis-backed cache stub where increment returns 1, then 2, ...
- **WHEN** `check_rate_limit(key, max_attempts=3, window_seconds=60)` is called 3 times
- **THEN** all 3 calls return `True`

#### Scenario: check_rate_limit returns False above threshold

- **GIVEN** the counter has already reached `max_attempts`
- **WHEN** `check_rate_limit` is called again
- **THEN** it returns `False`

#### Scenario: TTL is set only on the first increment

- **GIVEN** a Redis-backed cache stub
- **WHEN** `check_rate_limit` is called 3 times
- **THEN** `expire(key, ttl=window_seconds)` is called exactly once (on the first call, when count == 1)
