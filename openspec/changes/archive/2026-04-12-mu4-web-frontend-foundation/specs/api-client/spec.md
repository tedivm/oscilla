# TypeScript API Client

## Purpose

Specifies the hand-written TypeScript API client layer: the base request wrapper (`client.ts`), the auth store (`stores/auth.ts`), the typed interfaces (`types.ts`), and the per-domain API modules (`auth.ts`, `games.ts`, `characters.ts`). This layer is the single integration point between SvelteKit components and the FastAPI backend.

---

## Requirements

### Requirement: `types.ts` interfaces match implemented Pydantic models

`frontend/src/lib/api/types.ts` SHALL export TypeScript interfaces that exactly match the JSON serialization of the Pydantic response models implemented in MU1–MU3. Field names SHALL use `snake_case`. UUIDs SHALL be typed as `string`. Timestamps SHALL be typed as `string` (ISO 8601 from FastAPI). Integer tick counters SHALL be typed as `number`.

The interfaces SHALL cover: `UserRead`, `TokenPair`, `GameFeatureFlags`, `GameRead`, `CharacterSummaryRead`, `StatValue`, `StackedItemRead`, `ItemInstanceRead`, `SkillRead`, `BuffRead`, `ActiveQuestRead`, `MilestoneRead`, `ArchetypeRead`, `ActiveAdventureRead`, and `CharacterStateRead`.

The exact field names and types are specified in the `types.ts` code block in `design.md`. Any deviation from the actual Pydantic models causes `svelte-check` type errors in components that access the response data — this is the correctness signal.

#### Scenario: TypeScript type error on renamed field

- **GIVEN** a component accesses `character.instances[0].id`
- **WHEN** `svelte-check` runs
- **THEN** a type error is reported because `ItemInstanceRead` has `instance_id`, not `id`.

---

### Requirement: `client.ts` base request wrapper

`frontend/src/lib/api/client.ts` SHALL export an `ApiError` class and an `api` object with `get`, `post`, `patch`, and `delete` helpers. All helpers SHALL:

1. Read the current access token from `authStore` via `get(authStore)`.
2. Inject `Authorization: Bearer <token>` on every request not marked `skipAuth: true`.
3. On `401` response: call `authStore.refreshTokens()` once; if successful, retry the original request with the new token; if the retry also fails or refresh returns false, call `authStore.logout()` and `goto('/app/login?next=<current_path>')`.
4. On any non-2xx response (after the refresh/retry path): throw `ApiError` with the HTTP status code and the `detail` field from the JSON body (or the raw `statusText` if the body is not JSON).
5. Return `undefined as T` for `204 No Content` responses.

`client.ts` SHALL NOT import any high-level API functions from `auth.ts` (to prevent a circular import). Token refresh is handled by calling `authStore.refreshTokens()` directly on the store, which uses `fetch` internally.

#### Scenario: Request includes Authorization header

- **GIVEN** `authStore` has a non-null `accessToken`
- **WHEN** `api.get('/games')` is called
- **THEN** the outgoing `fetch` call includes `Authorization: Bearer <token>` in its headers.

#### Scenario: 401 triggers refresh and retry

- **GIVEN** the access token is expired and `refreshTokens()` returns `true` with a new token
- **WHEN** an API call receives a `401`
- **THEN** `authStore.refreshTokens()` is called exactly once
- **AND** the original request is retried with the new token
- **AND** the component receives the response data (not an error).

#### Scenario: Failed refresh triggers logout and redirect

- **GIVEN** the access token is expired and `refreshTokens()` returns `false`
- **WHEN** an API call receives a `401`
- **THEN** `authStore.logout()` is called
- **AND** `goto('/app/login?next=...')` is called
- **AND** `ApiError(401, ...)` is thrown.

#### Scenario: Non-2xx response throws ApiError

- **GIVEN** the server returns `422 Unprocessable Entity` with body `{ "detail": "Invalid data" }`
- **WHEN** an API call is made
- **THEN** `ApiError` is thrown with `status=422` and `detail="Invalid data"`.

---

### Requirement: `stores/auth.ts` manages token lifecycle

`frontend/src/lib/stores/auth.ts` SHALL export `authStore` (a Svelte `writable`-based custom store) and `isLoggedIn` (a `derived` store).

The store MUST use `writable` from `svelte/store` and NOT Svelte 5 runes. Plain `.ts` modules (like `client.ts`) must be able to synchronously read the current state via `get(authStore)`, which is incompatible with rune-based state that only works in `.svelte` and `.svelte.ts` files.

`authStore` SHALL expose:

- `init()` — async; reads tokens from `localStorage`; calls `GET /auth/me` to validate the access token and restore `UserRead`; if `GET /auth/me` returns 401, calls `refreshTokens()` once before clearing state.
- `login(pair, user)` — stores both tokens in `localStorage` and in the store; sets `user`.
- `applyTokenPair(pair)` — replaces tokens in `localStorage` and the store without clearing `user`; used after a successful refresh.
- `logout()` — clears tokens from `localStorage` and the store.
- `setError(message)` — sets the auth-layer error for the global `ErrorBanner`.
- `refreshTokens()` — calls `POST /auth/refresh` directly via `fetch` (not via `client.ts`!) to avoid circular imports; on success calls `applyTokenPair`; on failure calls `logout()` and returns `false`.

`isLoggedIn` SHALL be `true` only when both `accessToken !== null` and `user !== null`.

Tokens SHALL be stored in `localStorage` under keys `oscilla_access_token` and `oscilla_refresh_token`.

#### Scenario: init() restores session from localStorage

- **GIVEN** `localStorage` contains valid tokens
- **AND** `GET /auth/me` returns a `UserRead`
- **WHEN** `authStore.init()` is called
- **THEN** `$isLoggedIn === true`
- **AND** `$authStore.user` is populated.

#### Scenario: init() handles expired access token

- **GIVEN** `localStorage` contains tokens where the access token is expired
- **AND** `GET /auth/me` returns 401
- **AND** `POST /auth/refresh` returns a new `TokenPair`
- **WHEN** `authStore.init()` is called
- **THEN** the new tokens are stored and `$isLoggedIn === true`.

#### Scenario: logout() clears all state

- **WHEN** `authStore.logout()` is called
- **THEN** `localStorage.getItem('oscilla_access_token')` is `null`
- **AND** `$isLoggedIn === false`
- **AND** `$authStore.user` is `null`.

---

### Requirement: `api/auth.ts` functions

`frontend/src/lib/api/auth.ts` SHALL export the following async functions:

| Function                                   | API call                            | Notes                                     |
| ------------------------------------------ | ----------------------------------- | ----------------------------------------- |
| `register(email, password, display_name?)` | `POST /auth/register`               | `skipAuth=true`; returns `UserRead`       |
| `login(email, password)`                   | `POST /auth/login`                  | `skipAuth=true`; returns `TokenPair`      |
| `logout(refreshToken)`                     | `POST /auth/logout`                 | Returns `void` (204)                      |
| `refreshTokens(refreshToken)`              | `POST /auth/refresh`                | Returns `TokenPair` — called by authStore |
| `getMe()`                                  | `GET /auth/me`                      | Returns `UserRead`                        |
| `updateMe(updates)`                        | `PATCH /auth/me`                    | Returns `UserRead`                        |
| `requestVerification()`                    | `POST /auth/request-verify`         | Returns `void`                            |
| `requestPasswordReset(email)`              | `POST /auth/request-password-reset` | `skipAuth=true`; returns `void`           |
| `resetPassword(token, newPassword)`        | `POST /auth/password-reset/{token}` | `skipAuth=true`; returns `void`           |

---

### Requirement: `api/games.ts` functions

`frontend/src/lib/api/games.ts` SHALL export:

- `listGames() -> Promise<GameRead[]>` — `GET /games`
- `getGame(name: string) -> Promise<GameRead>` — `GET /games/{name}`

---

### Requirement: `api/characters.ts` functions

`frontend/src/lib/api/characters.ts` SHALL export:

- `listCharacters(gameName?: string) -> Promise<CharacterSummaryRead[]>` — `GET /characters?game={name}` (the `?game=` filter is optional)
- `createCharacter(gameName: string) -> Promise<CharacterSummaryRead>` — `POST /characters` with body `{ game_name: gameName }`
- `getCharacter(id: string) -> Promise<CharacterStateRead>` — `GET /characters/{id}`
- `deleteCharacter(id: string) -> Promise<void>` — `DELETE /characters/{id}`
- `renameCharacter(id: string, name: string) -> Promise<CharacterSummaryRead>` — `PATCH /characters/{id}` with body `{ name }`
