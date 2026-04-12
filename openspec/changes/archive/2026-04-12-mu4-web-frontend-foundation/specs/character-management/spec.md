# Character Management

## Purpose

Specifies the game selection page, character list page, character creation page, and character sheet page — the core of the MU4 experience. All pages are protected routes. The character sheet is read-only in MU4; adventure interaction ships in MU5.

---

## Requirements

### Requirement: Game selection page (`/app/games`)

The game selection page SHALL:

- Fetch `GET /games` on mount using the three-state async pattern (loading → error | data).
- Render a `GameCard` component for each game returned. Each `GameCard` shows the game's `display_name`, `description` (if non-null), and a "Play" or "Select" button that navigates to `/app/characters?game={name}`.
- Render an empty-state prompt if the games list is empty.

#### Scenario: Games render as cards

- **GIVEN** `GET /games` returns two game objects
- **WHEN** the page mounts
- **THEN** two `GameCard` components are rendered, each showing the game's `display_name`.

#### Scenario: Empty state is shown

- **GIVEN** `GET /games` returns an empty list
- **WHEN** the page mounts
- **THEN** an informational empty-state message is rendered (e.g., "No games are currently available.").

---

### Requirement: Character list page (`/app/characters`)

The character list page SHALL:

- Accept an optional `?game=` query parameter to filter characters by game.
- Fetch `GET /characters?game={name}` (or `GET /characters` if no filter) on mount.
- Render a `CharacterCard` for each character, showing at minimum: `name`, `game_name`, `prestige_count`, and `created_at`.
- Provide a "New Character" button that navigates to `/app/characters/new?game={name}` (using any active game filter).
- Render an empty-state prompt with a "Create your first character" call-to-action when the list is empty.

#### Scenario: List renders character cards

- **GIVEN** `GET /characters` returns two characters
- **WHEN** the page mounts
- **THEN** two `CharacterCard` components are rendered.

#### Scenario: Game filter is applied

- **GIVEN** the URL includes `?game=testlandia`
- **WHEN** the page fetches characters
- **THEN** `GET /characters?game=testlandia` is called (not `GET /characters`).

#### Scenario: Empty state includes create link

- **GIVEN** `GET /characters` returns an empty list
- **WHEN** the page mounts
- **THEN** an empty-state prompt with a "Create your first character" link/button is rendered.

---

### Requirement: Character creation page (`/app/characters/new`)

Character creation SHALL be a single-step form — not a multi-step wizard. `POST /characters` accepts only `game_name`; all name, pronoun, and archetype customization is handled by the game's triggered creation adventure in MU5.

The creation page SHALL:

- Accept an optional `?game=` pre-selection parameter.
- If `?game=` is present: show a confirmation card with the game's `display_name` and a single "Create Character" button that POSTs to `POST /characters` with `{ game_name }`.
- If `?game=` is absent: show the same game selection grid (`GET /games`) so the user can pick first; selecting a game proceeds to the confirmation step.
- On success (`201 Created`): navigate to `/app/characters/{new_id}` (the character sheet).
- On error: display an `ErrorBanner` with the server's `detail` message.

#### Scenario: Pre-selected game shows confirmation

- **GIVEN** the URL is `/app/characters/new?game=testlandia`
- **WHEN** the page mounts
- **THEN** the game picker is not shown
- **AND** a confirmation UI showing the game name is rendered.

#### Scenario: Successful creation navigates to character sheet

- **GIVEN** the user confirms creation
- **AND** `POST /characters` returns `201` with a `CharacterSummaryRead`
- **THEN** the user is navigated to `/app/characters/{id}`.

---

### Requirement: Character sheet page (`/app/characters/[id]`)

The character sheet page SHALL:

- Fetch `GET /characters/{id}` on mount, then fetch `GET /games/{game_name}` using the resolved character game name (using the three-state async pattern).
- Pass the `CharacterStateRead` and `GameFeatureFlags` to the panel components.
- Render a `CharacterHeader` showing at minimum: `name`, `game_name`, `pronoun_set`, `prestige_count`, and current location (`current_location_name`, `current_region_name`).
- Render the panels listed in the table below according to `GameFeatureFlags`.
- Return to the character list via a "Back" link.
- The page is read-only in MU4. Adventure controls are not shown.

| Panel             | When shown                         | Data source                                                                        |
| ----------------- | ---------------------------------- | ---------------------------------------------------------------------------------- |
| `StatsPanel`      | Always                             | `CharacterStateRead.stats` (a `Record<string, StatValue>`)                         |
| `InventoryPanel`  | Always                             | `stacks` (stacked) and `instances` (item instances), displayed in tabs             |
| `EquipmentPanel`  | Always                             | `equipment` (slot → `ItemInstanceRead`)                                            |
| `SkillsPanel`     | `features.has_skills === true`     | `skills` list; cooldown state is NOT in the current API — display name or ref only |
| `BuffsPanel`      | Always (shows empty state)         | `active_buffs` list                                                                |
| `QuestsPanel`     | `features.has_quests === true`     | `active_quests`, `completed_quests`, `failed_quests`                               |
| `MilestonesPanel` | Always (hides when empty)          | `milestones` record                                                                |
| `ArchetypesPanel` | `features.has_archetypes === true` | `archetypes` list                                                                  |

Panels whose feature flag is `false` SHALL not be rendered at all — not just empty. The `GameFeatureFlags` check is the sole source of panel visibility.

#### Scenario: Skills panel hidden when game has no skills

- **GIVEN** `features.has_skills === false`
- **WHEN** the character sheet renders
- **THEN** no `SkillsPanel` DOM node is present.

#### Scenario: Quests panel shown when game has quests

- **GIVEN** `features.has_quests === true`
- **WHEN** the character sheet renders
- **THEN** the `QuestsPanel` component is rendered.

#### Scenario: Another user's character returns 404

- **GIVEN** the character `{id}` belongs to a different user
- **WHEN** the page fetches `GET /characters/{id}`
- **THEN** a 404 `ApiError` is received
- **AND** the page renders a not-found error state.

#### Scenario: Inventory panel shows stacked and instance tabs

- **GIVEN** the character has both stacked items and item instances
- **WHEN** the inventory panel renders
- **THEN** two tabs ("Stacked" and "Instances") are visible and each tab displays its respective data.

---

### Requirement: Three-state async pattern on all data-fetching pages

Every page that fetches data SHALL follow the pattern specified in design D8:

- Show `LoadingSpinner` while `loading === true`.
- Show a local `ErrorBanner` (not the global `authStore.error` banner) when `error !== null`.
- Render page content only when `loading === false && error === null`.

HTTP 404 errors from `ApiError` SHALL navigate to a not-found state rather than showing a generic error. HTTP 403 errors SHALL display a prompt to verify email. HTTP 5xx errors SHALL show a generic "server error" message through `ErrorBanner`.
