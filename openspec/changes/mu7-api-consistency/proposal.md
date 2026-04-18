## Why

The character state API (`GET /characters/{id}`) and the overworld API (`GET /characters/{id}/overworld`) return raw manifest reference keys — `ref` strings — in place of human-readable display names and descriptions for items, buffs, quests, archetypes, skills, adventures, locations, and regions. The frontend is forced to display internal identifiers to players, and several sub-models are missing fields that clients need to render the game correctly. Additionally, hidden stats leak through the character state response, `character_class` is a dead field that was never wired up, and the API has no defense against state-mutating requests made while an adventure is in progress.

## What Changes

### Backend

- **BREAKING** Remove `character_class` from `CharacterStateRead`, `CharacterState`, `CharacterIterationRecord`, both diff blocks in `session.py`, the prestige reset in `effects.py`, and both assignment sites in `services/character.py`; add an Alembic migration dropping the `character_class` column from `character_iterations`.
- **BREAKING** Filter hidden stats (those declared in `character_config.spec.hidden_stats`) out of the `stats` map in `CharacterStateRead`. Hidden stats remain fully accessible inside the engine; only the outbound API response is filtered.
- Add `updated_at: datetime` to `CharacterSummaryRead`; populate from `CharacterRecord.updated_at` (column already exists).
- Add `display_name: str | None` and `description: str | None` to `StackedItemRead`, `ItemInstanceRead`, `BuffRead`, `ActiveQuestRead`, and `ArchetypeRead`; populate from the content registry at serialization time.
- Add `display_name: str | None` and `description: str | None` to `ActiveAdventureRead`; populate from the content registry.
- Add `description: str | None`, `on_cooldown: bool`, and `cooldown_remaining_ticks: int | None` to `SkillRead` (alongside the existing `display_name`).
- Add `quest_display_name: str | None`, `quest_description: str | None`, and `stage_description: str | None` to `ActiveQuestRead`.
- Add `description: str | None` to `LocationOptionRead` in the overworld response.
- Add `description: str | None` to `RegionGraphNode` in the overworld response.
- Add a new `require_no_active_adventure` FastAPI dependency that reads iteration state and returns `409 Conflict` when a session lock is live. Apply to all state-mutating character endpoints outside the play flow (inventory, navigation, character update). The 409 response body is a structured object with `code: "active_adventure"` so clients can distinguish it from other conflicts.

### Frontend

- Update the TypeScript interfaces in `types.ts` to match all new backend fields.
- Update character sheet panels that display items, buffs, quests, archetypes, skills, and the active adventure to prefer `display_name` / `description` over raw `ref` values.
- Handle `409 Conflict` responses from character mutation endpoints: when the response body contains `adventure_ref`, redirect the user to `POST /characters/{id}/play/go` with that adventure ref (or to the play screen if already in progress) rather than showing an error dialog.
- Update the `CharacterCard` component to show `updated_at` as a last-played date.
- Update the overworld `LocationOption` rendering to show location descriptions where present.
- Update the `RegionGraphNode` rendering to carry descriptions for region tooltips.

### Testlandia

- Add `hidden` stats to `character_config.yaml` to exercise the hidden-stat filter.
- Ensure existing items, buffs, quests, archetypes, and skills have `displayName` and `description` populated so the enriched fields are non-null during manual QA.
- Add a skill with an active cooldown to the testlandia content to verify cooldown state rendering.
- Add location and region descriptions to all testlandia locations and regions.

## Capabilities

### New Capabilities

- `active-adventure-guard`: A reusable FastAPI dependency that enforces the invariant that no state-mutating request can be processed while a character has a live session lock. Returns `409 Conflict` with a structured body (`code: "active_adventure"`) that the frontend uses to redirect the user to the play screen rather than showing a generic error.

### Modified Capabilities

- `web-overworld`: `LocationOptionRead` gains `description: str | None`; `RegionGraphNode` gains `description: str | None`.
- `character-management`: `CharacterSummaryRead` gains `updated_at: datetime`; `CharacterStateRead` loses `character_class`; hidden stats filtered from `stats` map; all sub-models (`StackedItemRead`, `ItemInstanceRead`, `SkillRead`, `BuffRead`, `ActiveQuestRead`, `ArchetypeRead`, `ActiveAdventureRead`) gain display metadata fields.
- `player-state`: `CharacterState` loses `character_class`; no runtime behavior change beyond serialization.
- `skill-system`: `SkillRead` gains `description`, `on_cooldown`, and `cooldown_remaining_ticks`.

## Impact

- `oscilla/models/api/characters.py` — all sub-model additions; `character_class` removal; hidden stat filtering in `build_character_state_read`
- `oscilla/engine/character.py` — `character_class` field and serialization/deserialization removed
- `oscilla/engine/session.py` — two `character_class` diff blocks removed
- `oscilla/engine/steps/effects.py` — `player.character_class = None` prestige reset removed
- `oscilla/models/character_iteration.py` — `character_class` ORM column removed
- `oscilla/services/character.py` — two `character_class` assignment sites removed
- `oscilla/routers/overworld.py` — `LocationOptionRead` and `RegionGraphNode` enriched with `description`
- `oscilla/routers/characters.py` — `require_no_active_adventure` dependency applied to mutating endpoints
- `oscilla/dependencies/` — new `active-adventure-guard` dependency module
- `db/versions/` — new Alembic migration dropping `character_iterations.character_class`
- `tests/engine/test_character_persistence.py` — four fixture dicts updated to remove `"character_class": None`
- `frontend/src/lib/api/types.ts` — all interface updates
- `frontend/src/lib/components/` — character sheet, character card, overworld panels updated
- `docs/dev/api.md` — `character_class` removed, all new fields documented
- `docs/dev/database.md` — `character_class` column removal documented
- `content/testlandia/` — hidden stats, enriched descriptions, cooldown skill
