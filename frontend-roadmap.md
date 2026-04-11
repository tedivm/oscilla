# Multi-User Platform: Frontend Roadmap

This document captures the full architectural exploration, all technology decisions and their rationale, and the phased implementation plan for the Oscilla Multi-User Platform. It is the authoritative reference to consult before writing any change proposals in this group.

---

## Background

Oscilla currently runs as a single-user terminal application (TUI). Every player runs the engine locally against a local or networked database. The Multi-User Platform converts Oscilla into a shared server deployment where many players each run independent single-player game sessions against the same server and content library. This is explicitly **not multiplayer** — players never interact with each other.

The TUI remains a valid, supported client after this work. The web platform is an additional interface layer on top of the same engine, not a replacement for the TUI.

### Guiding Constraints

Two principles from the design philosophy are especially relevant here:

1. **The engine is a platform, not a game.** Every API and frontend design decision must work for all possible games, not just `testlandia`. No game-specific assumptions.
2. **Content from engine separation.** The web platform serves content from the file system at runtime; API responses must never embed content assumptions baked in at build time.

---

## Key Architectural Decisions

### Decision 1: Authentication — Custom JWT (not fastapi-users)

**Chosen:** Custom JWT auth stack using PyJWT + passlib[bcrypt] + itsdangerous.

**Rejected alternative:** `fastapi-users` library.

**Rationale:**

`fastapi-users` (v15.0.5, released March 2026) is explicitly **in maintenance mode**. Their README states:

> "This project is now in maintenance mode. While we'll continue to provide security updates and dependency maintenance, no new features will be added. We're currently working on a new Python authentication toolkit that will ultimately supersede FastAPI Users."

Building the platform's authentication foundation on a sunsetted library creates a guaranteed migration cost at a future, unknown date, with no upgrade path defined. The v15.0.5 release itself was a security patch that bumped PyJWT's minimum version to fix a critical header vulnerability — meaning the library still needs patching but won't evolve.

The custom approach is not complex. The core pieces are:

| Library           | Purpose                                                      | Status                                                                                      |
| ----------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| `PyJWT`           | JWT encode/decode (access + refresh tokens)                  | Battle-hardened, actively maintained                                                        |
| `argon2-cffi`     | Password hashing and verification (Argon2id)                 | Recommended by the Python cryptography project; Argon2 won the Password Hashing Competition |
| `itsdangerous`    | Time-limited HMAC tokens for email verify and password reset | Used by Flask, Django; actively maintained                                                  |
| `aiosmtplib`      | Async SMTP email sending                                     | Fits the async-first stack                                                                  |
| `email-validator` | RFC-compliant email validation (used by Pydantic)            | Pydantic dependency, already available                                                      |

Total implementation surface: approximately 300 lines across `services/auth.py` and two API routers. This code is entirely under our control, does not conflict with the existing `UserRecord` schema, and has no external deprecation risk.

**Token strategy:** JWT access tokens (short-lived, 15 minutes) + opaque refresh tokens stored in the DB (long-lived, 30 days). Refresh tokens support rotation and revocation. Access tokens are stateless — no per-request DB lookup required on protected routes.

**Email requirements:** Email is mandatory for web users (not TUI users). Whether email verification is required before a user can play is controlled by a settings flag (`require_email_verification`, default `False`). When disabled, accounts are active immediately on registration — appropriate for local development and private deployments. When enabled, unverified accounts cannot access game content. Password reset uses time-limited HMAC tokens via `itsdangerous` — no extra DB table needed.

---

### Decision 2: Pipeline Execution Model — Run-Until-Decision + SSE

**Chosen:** Option C ("Run-Until-Decision") with Server-Sent Events for narrative streaming.

**Rejected alternatives:**

- **Option A (WebSocket):** Server holds a live coroutine per active player. Requires session affinity (or Redis-backed coroutine serialization), complex reconnect logic, and memory pressure per active session. Substantially increases operational complexity.
- **Option B (Pure REST step-commit):** Every possible state-change is an independent atomic REST operation. Requires the adventure pipeline to be completely redesigned as a non-coroutine state machine. Very large engine refactor with high risk.
- **Option C without SSE (pure REST batch):** All narrative text arrives in one JSON blob. The game feels like a database query, not a story.

**How Option C + SSE works:**

The adventure pipeline (`AdventurePipeline`) is a coroutine that currently pauses at two kinds of "decision points": `show_menu` (player must choose) and `wait_for_ack` (player must press Enter). The existing database columns `adventure_step_index` and `adventure_step_state` already persist exactly where the pipeline stopped.

A new `WebTUICallbacks` implementation of the `TUICallbacks` protocol buffers output into an SSE queue instead of writing to the terminal. Each HTTP request runs the pipeline forward from the current `step_index` until it hits the next pause point:

```
POST /characters/{id}/play/advance
body: { "choice": 2 }   ← null for ack

Response: text/event-stream

event: narrative
data: {"text": "You push open the iron door.", "context": {...}}

event: narrative
data: {"text": "The chieftain rises from his throne."}

event: combat_state
data: {"player_hp": 42, "player_max_hp": 60, "enemy_hp": 85, ...}

event: choice
data: {"prompt": "How do you respond?", "options": ["Fight", "Flee", "Negotiate"]}

[server closes stream — pipeline hit show_menu, saved step_index to DB]
```

SSE is one-directional HTTP. It works through every reverse proxy and load balancer, reconnects automatically if the connection drops, and requires no client-side library beyond the browser-native `EventSource` API. It is strictly better than polling for this use case.

**Crash recovery:** A `GET /characters/{id}/play/current` endpoint returns the pending state (choice or ack required) and a log of narrative output produced so far in this "session" (between the last overworld action and now). This log is persisted to a `character_session_output` table. Browser refresh is always safe — the client re-fetches the pending state and re-renders the output log.

---

### Decision 3: Frontend — SvelteKit

**Chosen:** SvelteKit with TypeScript.

**Rejected alternative:** HTMX + Alpine.js + Jinja2 SSR.

**Rationale:**

The HTMX path is faster to start and leverages existing Jinja2 infrastructure. For a pure read-heavy text application, it would be the right choice. However, the full roadmap includes several features that require genuine interactive graph/spatial UI:

| Roadmap Feature                  | UI Requirement                                                       |
| -------------------------------- | -------------------------------------------------------------------- |
| Talent Trees / Passive Upgrades  | Clickable DAG — node unlock, prerequisite visualization              |
| Region Maps                      | SVG node graph with pan/zoom, visited state, current location marker |
| Inventory Storage                | Two-pane drag-and-drop item transfer                                 |
| NPC portraits + dialogue framing | Speaker panel alongside scrolling narrative                          |
| Faction reputation display       | Animated progress bars with history                                  |

With HTMX, each of these requires pulling in separate JavaScript libraries or writing vanilla JS alongside the HTMX templates — producing an inconsistent technology mix with no uniform component model or type safety. The "HTMX for everything and add JS where needed" approach is a gradual accumulation of complexity.

SvelteKit gives a single, uniform component model for all UI surface from the simplest stats table to the most complex talent tree DAG. TypeScript ensures the API response shapes are validated at compile time. The build pipeline (Vite) is a one-time setup cost that does not grow with feature count.

The Docker multi-stage build for a Node build stage feeding a Python runtime is a well-understood, solved pattern and does not add ongoing maintenance burden.

**SvelteKit architecture:**

- SvelteKit runs as a static build deployed via the Python server's `/static` or as a Node SSR process (decision to be made in Change 4). Static build preferred for simplicity.
- All data fetching uses the API. SvelteKit does not access the database directly.
- The existing `oscilla/templates/` and `oscilla/static/` infrastructure will be used only for the few non-SvelteKit pages (e.g., email verification landing — a simple HTML page served by FastAPI).

---

### Decision 4: UserRecord Migration — Additive Extension

**Chosen:** Extend the existing `UserRecord` model with new nullable columns. TUI and web auth paths stay on the same table but use different fields.

The existing `user_key` field (e.g., `"alice@hostname"`) is the TUI identity. Web auth identity is `email` + `hashed_password`. Both live on `UserRecord`. All new columns are nullable so TUI user rows remain valid:

```
UserRecord (extended)
├── id                  UUID PK
├── user_key            str  UNIQUE NULLABLE   ← TUI identity ("alice@hostname")
├── email               str  UNIQUE NULLABLE   ← Web auth identity
├── hashed_password     str  NULLABLE          ← NULL for TUI users
├── display_name        str  NULLABLE
├── is_email_verified   bool DEFAULT FALSE
├── is_active           bool DEFAULT TRUE
├── created_at          datetime
└── updated_at          datetime (new)
```

TUI code paths call `get_or_create_user(user_key=...)` — unchanged. Web auth creates rows via `email` + hashed password. Future account linking (same person using both TUI and web) is supported by allowing a row to have both `user_key` and `email` set.

---

### Decision 5: Content Registry Loading — Startup, Restart to Reload

**Chosen:** Load all game `ContentRegistry` instances once at app startup via the FastAPI lifespan handler, stored in `app.state.registries` as `Dict[str, ContentRegistry]`. A server restart is required to pick up new or changed content.

**Rationale:** Content registries are large, read-only, in-memory structures built by scanning and validating all YAML manifests. They are not mutated by game play — only `CharacterState` changes. Loading once at startup and sharing across all requests is safe and efficient. The alternative (per-request loading) would be prohibitively slow. Hot-reload adds significant complexity (file watching, registry swap locking, partial-load error handling) for a benefit that does not justify the cost at this stage.

---

### Decision 6: UICallbacks Protocol Refactor

**Chosen:** Rename `TUICallbacks` to `UICallbacks` as the canonical protocol. `TextualTUI` and `WebCallbacks` are the two concrete implementations. The name `TUICallbacks` is retired as a protocol name.

**Rationale:** The existing `TUICallbacks` protocol in `oscilla/engine/pipeline.py` defines the interface between the adventure pipeline and any UI client. It was named for its first and only implementation. Adding a web-specific implementation called `WebTUICallbacks` — as initially proposed — is an awkward name that reveals the historical accident rather than the intent.

The correct model is:

```
UICallbacks (Protocol)           ← pipeline.py: the engine's interface contract
├── TextualTUI                   ← engine/tui.py: terminal implementation
└── WebCallbacks                 ← www/ or engine/web.py: SSE-backed implementation
```

`UICallbacks` defines the same methods currently on `TUICallbacks` (`show_text`, `show_menu`, `show_combat_round`, `wait_for_ack`, `input_text`, `show_skill_menu`). The rename is purely mechanical — no method signatures change. All existing call sites in the pipeline and step handlers that type-hint `TUICallbacks` are updated to `UICallbacks`.

This refactor belongs in **Phase 3** (Adventure Execution API), since that is when `WebCallbacks` is first introduced and the protocol's dual-implementation nature becomes real. It should not be deferred to a later cleanup pass — naming it correctly from the first web use prevents the awkward name from propagating into tests, documentation, and frontend mental models.

---

### Decision 7: Session Locking for Web

The TUI uses a `session_token` soft lock on the active `CharacterIterationRecord` to detect dead processes that did not release their lock. The web platform reuses this mechanism but must prevent a user from playing the same character in two browser tabs simultaneously.

The web session lock model extends the existing `session_token` column: when a web session acquires the lock, it writes a UUID tied to the authenticated user's request session. A second tab attempting to run an adventure for the same character finds the lock held and receives a `409 Conflict` response with a descriptive message. The lock is released when the adventure ends or when the user explicitly navigates away from the adventure screen.

**Force-takeover:** A frozen or crashed tab cannot cleanly release the lock. The `409 Conflict` response must include the lock's `acquired_at` timestamp and the current server time so the client can display how long the lock has been held. The frontend presents a "Take over this session" option on the conflict screen. Confirming force-takeover calls:

```
POST /characters/{id}/play/takeover
```

This endpoint forcibly clears the existing lock and immediately acquires it for the requesting session, then returns the current pending adventure state (same shape as `GET /characters/{id}/play/current`) so the frontend can resume rendering without a separate round-trip. The takeover endpoint is only accessible to the authenticated owner of the character — it is not an admin-only bypass.

---

## Technology Stack

| Layer                  | Technology                            | Notes                        |
| ---------------------- | ------------------------------------- | ---------------------------- |
| API framework          | FastAPI                               | Already in place             |
| ASGI server            | Uvicorn                               | Already in place             |
| Database               | PostgreSQL (prod) / SQLite (dev/test) | Already in place             |
| ORM                    | SQLAlchemy 2.0+ async                 | Already in place             |
| Migrations             | Alembic                               | Already in place             |
| Cache                  | Redis via aiocache                    | Already in place             |
| Content loading        | YAML manifests via ruamel.yaml        | Already in place             |
| Templating             | Jinja2                                | Already in place             |
| Auth: password hashing | argon2-cffi (Argon2id)                | New dependency               |
| Auth: JWT tokens       | PyJWT                                 | New dependency               |
| Auth: email tokens     | itsdangerous                          | New dependency               |
| Auth: email sending    | aiosmtplib                            | New dependency               |
| Frontend framework     | SvelteKit + TypeScript                | New; separate build          |
| Frontend build tool    | Vite (bundled with SvelteKit)         | New                          |
| Frontend HTTP client   | Fetch API + EventSource               | Browser-native, no library   |
| Container build        | Docker multi-stage (Node → Python)    | New stage for frontend build |

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                     MULTI-USER PLATFORM                            │
│                                                                    │
│  Browser (SvelteKit SPA)                                           │
│       │  HTTPS REST + EventSource (SSE)                           │
│       ▼                                                            │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │                   FastAPI (www.py)                        │     │
│  │                                                          │     │
│  │  /auth/*         — register, login, verify, reset        │     │
│  │  /games/*        — game discovery + metadata             │     │
│  │  /characters/*   — CRUD + full state read                │     │
│  │  /characters/{id}/play/* — adventure execution (SSE)     │     │
│  │  /content/{game}/static/* — game asset serving           │     │
│  │  /static/*       — SvelteKit built assets                │     │
│  │                                                          │     │
│  │  app.state.registries: Dict[str, ContentRegistry]        │     │
│  │  (loaded once at startup, shared read-only)               │     │
│  └──────────────────────────────────────────────────────────┘     │
│       │                                                            │
│       ▼                                                            │
│  ┌───────────────┐     ┌──────────────────────────────────┐       │
│  │  PostgreSQL   │     │  Redis                           │       │
│  │  (game state) │     │  (cache, refresh token store)    │       │
│  └───────────────┘     └──────────────────────────────────┘       │
│                                                                    │
│  Terminal (TUI — unchanged)                                        │
│       │  direct DB + engine calls (no API)                         │
│       ▼                                                            │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │         Engine (pipeline, conditions, effects)            │     │
│  │         Shared by both TUI and web execution paths        │     │
│  └──────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────┘
```

### Adventure Execution Flow (Web)

```
Player clicks "Begin Adventure"
        │
        ▼
POST /characters/{id}/play/begin
        │
        ▼
WebTUICallbacks instantiated — SSE queue initialized
        │
AdventurePipeline.run() begins
        │
        ├── step 0: narrative  → SSE event: narrative{"text": "..."}
        ├── step 1: narrative  → SSE event: narrative{"text": "..."}
        ├── step 2: choice     → SSE event: choice{"prompt": "...", "options": [...]}
        │                         pipeline pauses, saves step_index=3 to DB
        │                         SSE stream closes
        ▼
Player sees narrative log + choice menu
        │
Player selects option 2
        │
        ▼
POST /characters/{id}/play/advance  body: {"choice": 2}
        │
        ▼
Pipeline resumes from step_index=3
        │
        ├── step 3: combat     → SSE event: combat_state{...}
        │                        (per round, waits for ack)
        ├── step 4: narrative  → SSE event: narrative{"text": "..."}
        ├── step 5: [end]      → SSE event: adventure_complete{"outcome": "victory"}
        │                        adventure_step_index cleared in DB
        │                        SSE stream closes
        ▼
Player returned to overworld
```

---

## API Surface Design

Full endpoint list, designed to satisfy frontend needs throughout the roadmap (not just Change 2/3 needs):

### Auth

```
POST /auth/register              body: {email, password, display_name}
POST /auth/login                 body: {email, password}  → {access_token, refresh_token}
POST /auth/refresh               body: {refresh_token}    → {access_token}
POST /auth/logout                body: {refresh_token}    (revokes token)
POST /auth/request-verify        (resend verification email)
GET  /auth/verify/{token}        (email verification link)
POST /auth/request-password-reset  body: {email}
POST /auth/password-reset/{token}  body: {new_password}
GET  /auth/me                    → UserRead
PATCH /auth/me                   body: {display_name, password}
```

### Games

```
GET  /games                      → List[GameRead]   (all loaded games)
GET  /games/{game_name}          → GameRead         (metadata + feature flags)
GET  /content/{game_name}/static/{path}   (game asset serving — images, etc.)
```

`GameRead` includes feature flags derived from `game.yaml`: `has_skills`, `has_quests`, `has_factions`, `has_time`, `has_archetypes`, `has_talent_nodes` (roadmap). These drive frontend panel visibility — no faction panel if the game has no factions.

### Characters

```
GET  /characters                 ?game=name  → List[CharacterSummaryRead]
POST /characters                 body: CharacterCreate → CharacterSummaryRead
GET  /characters/{id}            → CharacterStateRead   (complete; all panels)
DELETE /characters/{id}
PATCH /characters/{id}           body: {display_name}   (rename)
```

`CharacterStateRead` exposes the full character state — stats, inventory (stackable + instances), equipment, milestones, active/completed quests, known skills with cooldown state, active buffs, prestige count, current location, and in-game time. If this response schema is designed completely up front, no API change is needed when new character panels land (inventory storage, factions, talent trees, prestige history).

### Adventure Execution

```
GET  /characters/{id}/play/current
     → PendingStateRead  (crash recovery: output log + pending decision)

POST /characters/{id}/play/begin
     body: BeginAdventureRequest {adventure_ref: str}
     → text/event-stream (SSE)

POST /characters/{id}/play/advance
     body: AdvanceRequest {choice: int | null, ack: bool | null}
     → text/event-stream (SSE)

POST /characters/{id}/play/abandon
     (exit current adventure, return to overworld)

POST /characters/{id}/play/takeover
     (force-release a stale lock and acquire it; returns PendingStateRead)

POST /characters/{id}/navigate
     body: NavigateRequest {location_ref: str}
     → OverworldStateRead

GET  /characters/{id}/overworld
     → OverworldStateRead
     (current location, available adventures, available navigation options,
      region tree, NPC context — everything the overworld screen needs)
```

`OverworldStateRead` includes everything needed for future roadmap panels: region hierarchy, available adventures with `displayName` and `requires` evaluation result, NPC context if any adventure is NPC-associated (for future portrait display).

### SSE Event Types

All SSE events carry a `context` object with `{location_ref, location_name, region_name}` at minimum. As roadmap features land, `context` grows (NPC speaker info, etc.) without changing the event type contract.

```
event: narrative        data: {text, context}
event: ack_required     data: {context}               ← wait_for_ack
event: choice           data: {prompt, options, context}
event: combat_state     data: {player_hp, player_max_hp, enemy_hp, enemy_max_hp,
                               player_name, enemy_name, round, context}
event: text_input       data: {prompt, context}
event: skill_menu       data: {skills, context}
event: adventure_complete  data: {outcome, context}
event: error            data: {message}
```

---

## Database Changes

### New Table: `character_session_output`

Persists the narrative output produced since the last overworld action. Used for crash recovery.

```
character_session_output
├── id              UUID PK
├── iteration_id    UUID FK → character_iterations
├── position        int      (ordering within session)
├── event_type      str      (narrative, ack_required, choice, combat_state, ...)
├── content_json    JSON     (full event data)
└── created_at      datetime
```

Rows are cleared when an adventure completes (or is abandoned) and the player returns to the overworld. This table is intentionally separate from the adventure step persistence columns — those track _where the pipeline is_, this tracks _what the player has seen_.

### New Table: `auth_refresh_tokens`

```
auth_refresh_tokens
├── id          UUID PK
├── user_id     UUID FK → users
├── token_hash  str UNIQUE  (SHA-256 of the opaque token)
├── issued_at   datetime
├── expires_at  datetime
└── revoked     bool DEFAULT FALSE
```

### Extended `UserRecord`

See Decision 4 above. Migration is additive — all new columns nullable, all existing rows remain valid.

---

## Roadmap Compatibility: Design Decisions to Get Right Now

These are design choices that must be made _before_ the first API endpoint ships. Getting them wrong requires breaking API changes.

### 1. `CharacterStateRead` Must Be Complete from Day One

If the character state response is a minimal subset today, every new panel feature (factions, talent trees, prestige history, inventory storage) requires a new API version or a breaking schema change. The complete `CharacterStateRead` should expose every domain tracked by `CharacterState` — including fields for features not yet implemented in the roadmap (empty lists/nulls are fine). Adding more to the response is non-breaking; removing fields is.

### 2. Feature Flags in `GameRead`

Frontend panel visibility must be driven by `GameRead.features`, not by hardcoded frontend logic. A game with no `archetypes` declared should never show an archetypes panel. This pattern must be in place when the first panels ship or every new feature requires a frontend code change to conditionally show/hide panels.

### 3. Game Asset Serving

Region maps (roadmap) and NPC portraits (roadmap) require the API to serve image assets from content packages. The endpoint `GET /content/{game_name}/static/{path}` must be designed as part of Change 2, reserving the URL namespace. Serving arbitrary files from this path is a security concern — path traversal must be prevented by resolving the path relative to the game's content directory and rejecting anything that escapes it.

### 4. Adventure Context Object in All SSE Events

Every SSE event carries a `context` field even before NPC portraits and region maps ship. When those features land, the context grows to include `npc_context: {name, portrait_url}` and `location_context: {coordinates, region_path}`. If context is not in the event contract from day one, NPC portraits require a frontend change to every SSE consumer.

### 5. `OverworldStateRead` Includes Region Hierarchy

The region maps feature (roadmap) needs the server to return the layout graph for the player's current region. If `OverworldStateRead` does not include region hierarchy data from day one, adding it later is a breaking change. The initial response can include the full region tree (nodes + edges in a format ready for SVG rendering) even before the frontend renders it visually.

---

## Implementation Phases

### Phase 1: Auth & User Accounts — Effort L

**What ships:** Authenticated user registration, login, optional email verification, and password reset. The TUI is fully untouched.

**Scope:**

- Extend `UserRecord` with auth fields (Alembic migration)
- `services/auth.py`: JWT encode/decode, Argon2id hash/verify, itsdangerous token generation/verification, async email sending
- Auth routes: `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/request-verify`, `/auth/verify/{token}`, `/auth/request-password-reset`, `/auth/password-reset/{token}`, `/auth/me` (GET + PATCH)
- `get_current_user` FastAPI dependency (validates JWT, returns `UserRecord`)
- `auth_refresh_tokens` table and migration
- Settings: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password` (SecretStr), `smtp_from_address`, `jwt_secret` (SecretStr), `access_token_expire_minutes`, `refresh_token_expire_days`
- `.env.example` updated

**Prereqs:** None.

**Risk:** SMTP configuration is required. Development must support a local SMTP mock (e.g., MailHog in `compose.yaml`).

---

### Phase 2: Game Discovery & Character Management API — Effort M

**What ships:** Read API for games and characters. The full `CharacterStateRead` schema is designed and locked here.

**Scope:**

- Load `ContentRegistry` instances at startup, store in `app.state.registries`
- `GET /games`, `GET /games/{game_name}` with feature flags
- `GET /content/{game_name}/static/{path}` with path traversal protection
- `GET /characters`, `POST /characters`, `GET /characters/{id}`, `DELETE /characters/{id}`, `PATCH /characters/{id}`
- Pydantic read models: `GameRead`, `GameFeatureFlags`, `CharacterSummaryRead`, `CharacterStateRead` (complete schema)
- Auth dependency wired to character endpoints

**Prereqs:** Phase 1.

**Risk:** `CharacterStateRead` schema design — must be comprehensive and correct. This is the schema that locks the frontend panel contract.

---

### Phase 3: Adventure Execution API — Effort L

**What ships:** Full game loop playable via HTTP. This is the hardest phase.

**Scope:**

- `WebTUICallbacks`: implements `TUICallbacks`, emits SSE events, accumulates to `character_session_output`
- `character_session_output` table and migration
- `GET /characters/{id}/play/current` (crash recovery)
- `POST /characters/{id}/play/begin` → SSE stream
- `POST /characters/{id}/play/advance` → SSE stream
- `POST /characters/{id}/play/abandon`
- `POST /characters/{id}/navigate`
- `GET /characters/{id}/overworld`
- Web session lock: prevent two concurrent tabs on same character
- SSE event types locked and documented

**Prereqs:** Phase 2.

**Risk:** The pipeline coroutine + SSE interaction requires careful async design. The `WebTUICallbacks` must handle the SSE queue correctly when the pipeline is running in a FastAPI background task. Concurrency testing is essential.

---

### Phase 4: Web Frontend — Foundation — Effort M

**What ships:** SvelteKit application covering auth flows, game selection, character management, and read-only character sheet.

**Scope:**

- SvelteKit project scaffolding in `frontend/`
- Docker multi-stage build: Node build stage → copies `frontend/build` into Python image
- FastAPI serves built assets from `/app`
- Base layout: navigation, auth state, responsive shell
- Pages: login, register, email verification, game selection, character list, character creation wizard (name, pronoun selection, archetype if applicable)
- Character sheet page: stats, inventory, skills, quests, buffs (read-only, no adventure actions)
- API client layer in TypeScript (typed against the Pydantic response models)
- Feature-flag driven panel visibility

**Prereqs:** Phases 1 and 2.

---

### Phase 5: Web Frontend — Game Loop — Effort L

**What ships:** Fully playable game from the browser.

**Scope:**

- Narrative log component (SSE consumer, paragraph-by-paragraph typewriter pacing)
- Choice menu component (replaces input area on `choice` event)
- Ack button (replaces input area on `ack_required` event)
- Combat state component (HP bars, round display)
- Text input component (for character naming steps, etc.)
- Skill activation from overworld
- Inventory equip/use during overworld
- Location and region navigation
- Overworld screen (location list, adventure selection, character sidebar)
- Crash recovery: re-fetch pending state on page load/refresh

**Prereqs:** Phases 3 and 4.

---

### Phase 6: Production Hardening — Effort M

**What ships:** Production-ready security posture and operational tooling.

**Scope:**

- Rate limiting on auth endpoints (failed login lockout, registration throttle)
- CORS configuration (allowlist origins)
- Security headers middleware (HSTS, X-Content-Type-Options, X-Frame-Options, CSP)
- Password strength validation (minimum entropy, not just length)
- Account lockout after N failed login attempts (Redis-backed counter)
- Structured request logging (request ID, authenticated user ID, outcome)
- Audit log for auth events (login, logout, password reset, email verify)
- `/health` and `/ready` endpoints for orchestration
- Docker production image: no hot-reload, proper Uvicorn worker configuration
- MailHog removed from production compose; SMTP settings documented

**Prereqs:** Phases 1–5.

---

## Future Roadmap Integration Notes

These are design notes for features not yet in scope but affected by platform decisions:

**Talent Trees (roadmap: M):** The `GET /characters/{id}` response should include a stable `talent_nodes` field (null or empty list until the feature ships). The SvelteKit component for the talent tree DAG can be developed in isolation and dropped into the existing character sheet page. No new API endpoints needed.

**Region Maps (roadmap: M):** `GET /characters/{id}/overworld` already includes region hierarchy data. The map layout computation (force-directed or grid) should be a server-side API response, not client-side computation, using the existing `graph.py` infrastructure. The frontend receives a `{nodes: [...], edges: [...]}` structure and renders it as SVG.

**NPC Portraits (roadmap: L, as part of Persistent NPCs):** Adventure SSE events already carry `context.npc_context`. Content manifests will gain an optional `image_path` field. The `/content/{game}/static/` endpoint already reserves the asset-serving URL. The SvelteKit narrative component needs a conditional NPC portrait panel that activates when `npc_context` is present in the event.

**Inventory Storage (roadmap: L):** `CharacterStateRead` should have a `storage` field from day one (null until the feature ships). The two-pane transfer UI is a SvelteKit component that posts to new `/characters/{id}/storage/transfer` endpoints when the feature lands.

**Full TUI Upgrade (roadmap: L):** The TUI upgrade is a completely separate track that shares no code with the web platform. The only concern is ensuring TUI panel features (inventory, skills, quests) are not designed to depend on web-only data structures.

**Picture Selection and ASCII Art (roadmap: M):** Same asset-serving infrastructure as NPC portraits. Game manifests declare relative asset paths; the server resolves them via the `/content/{game}/static/` endpoint. The frontend renders them as standard `<img>` elements with lazy loading.

---

## Open Questions

These were not resolved during the exploration session and must be addressed before or during the relevant phase:

1. **Email sending in development:** MailHog is the standard choice for local SMTP interception. It should be added to `compose.yaml` for development. Question: should the verification email be skipped entirely in development mode (i.e., `DEBUG=true` auto-verifies) to reduce friction?

2. **SvelteKit deployment mode:** Static pre-rendered build (requires `adapter-static`) vs. Node SSR (requires `adapter-node`). Static has no server-side rendering, all data fetched client-side — simplest Docker integration. Node SSR enables SSR of the character sheet (better initial load) but adds a Node.js process to the deployment. This decision belongs in Phase 4 design.

3. **OAuth2 / Social login:** Not in scope for the initial platform. The auth design does not preclude adding OAuth2 later (GitHub, Google, Discord are natural choices for a game platform). When interest is high enough, `httpx-oauth` is the natural library choice and the `UserRecord` already has room for an `oauth_provider` / `oauth_subject` column pair.

4. **Content registry invalidation:** Restart to reload is the current plan. If hot-reload becomes important (e.g., content authors want live-preview of changes without server restart), a file-watcher approach using `watchfiles` could be explored. Not blocking any phase.

5. **Admin tooling:** Phase 6 mentions no admin surface. Before a public deployment, there should be at minimum: a way to ban / deactivate user accounts and a way to see active sessions. Whether this is a CLI command or a protected admin API route is not yet decided.
