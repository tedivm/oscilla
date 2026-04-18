# Tasks

## 1. Backend — Remove character_class

- [x] 1.1 Remove `character_class: str | None` field from `CharacterState` dataclass in `oscilla/engine/character.py`
- [x] 1.2 Remove `character_class=None` initialization from `CharacterState.new_character()` in `oscilla/engine/character.py`
- [x] 1.3 Remove `"character_class": self.character_class` from `CharacterState.to_dict()` in `oscilla/engine/character.py`
- [x] 1.4 Change `character_class=data.get("character_class")` in `CharacterState.from_dict()` to silently ignore the key (do not pass it to constructor) in `oscilla/engine/character.py`
- [x] 1.5 Remove both `character_class` diff blocks from `oscilla/engine/session.py` (lines ~384–387 and ~884–887)
- [x] 1.6 Remove `player.character_class = None` from the prestige reset in `oscilla/engine/steps/effects.py`
- [x] 1.7 Remove `character_class: Mapped[str | None]` column from `CharacterIterationRecord` in `oscilla/models/character_iteration.py`
- [x] 1.8 Remove `character_class=state.character_class` from `save_character()` in `oscilla/services/character.py`
- [x] 1.9 Remove `"character_class": iteration.character_class` from `load_character()` in `oscilla/services/character.py`

## 2. Backend — Alembic migration

- [x] 2.1 Run `make create_migration MESSAGE="drop character_class from character_iterations"` and verify the generated migration drops the column using `batch_alter_table`

## 3. Backend — API model changes

- [x] 3.1 Add `display_name: str | None` and `description: str | None` to `StackedItemRead`
- [x] 3.2 Add `display_name: str | None` and `description: str | None` to `ItemInstanceRead`
- [x] 3.3 Add `description: str | None`, `on_cooldown: bool`, and `cooldown_remaining_ticks: int | None` to `SkillRead`
- [x] 3.4 Add `display_name: str | None` and `description: str | None` to `BuffRead`
- [x] 3.5 Add `quest_display_name: str | None`, `quest_description: str | None`, and `stage_description: str | None` to `ActiveQuestRead`
- [x] 3.6 Add `display_name: str | None` and `description: str | None` to `ArchetypeRead`
- [x] 3.7 Add `display_name: str | None` and `description: str | None` to `ActiveAdventureRead`
- [x] 3.8 Add `updated_at: datetime` to `CharacterSummaryRead`
- [x] 3.9 Remove `character_class: str | None` from `CharacterStateRead`
- [x] 3.10 Update `build_character_summary()` to pass `updated_at=record.updated_at`
- [x] 3.11 Update `build_character_state_read()` stacks block to look up item display metadata
- [x] 3.12 Update `build_character_state_read()` instances block to look up item display metadata
- [x] 3.13 Update `build_character_state_read()` skills block to include description and cooldown state
- [x] 3.14 Update `build_character_state_read()` buffs block to include display metadata
- [x] 3.15 Update `build_character_state_read()` quests block to include all three quest display fields
- [x] 3.16 Update `build_character_state_read()` archetypes block to include display metadata
- [x] 3.17 Update `build_character_state_read()` active adventure block to include display metadata
- [x] 3.18 Update `build_character_state_read()` stats block to use only `public_stats`
- [x] 3.19 Remove `character_class=state.character_class` from the `return CharacterStateRead(...)` call

## 4. Backend — Overworld router

- [x] 4.1 Add `description: str | None = None` to `LocationOptionRead` in `oscilla/routers/overworld.py`
- [x] 4.2 Add `description: str | None = None` to `RegionGraphNode` in `oscilla/routers/overworld.py`
- [x] 4.3 Update `_build_overworld_state()` location append to pass `description=loc.spec.description or None`
- [x] 4.4 Update `_build_overworld_state()` region graph to build `region_descriptions` dict and pass descriptions to `RegionGraphNode`

## 5. Backend — Active adventure guard

- [x] 5.1 Create `oscilla/dependencies/adventure_guard.py` with `require_no_active_adventure` dependency
- [x] 5.2 Apply `dependencies=[Depends(require_no_active_adventure)]` to `PATCH /characters/{id}` in `oscilla/routers/characters.py`

## 6. Backend — Semantic validator

- [x] 6.1 Add `_DESCRIPTION_CHECKS` constant to `oscilla/engine/semantic_validator.py`
- [x] 6.2 Add `_check_missing_descriptions()` function to `oscilla/engine/semantic_validator.py`
- [x] 6.3 Register `_check_missing_descriptions` in `validate_semantic()`
- [x] 6.4 Add `Tuple` to the `from typing import` line if not already present

## 7. Tests

- [x] 7.1 Update four fixture dicts in `tests/engine/test_character_persistence.py` to remove `"character_class": None`
- [x] 7.2 Add unit tests for `build_character_state_read()` in `tests/routers/test_characters.py` (or a new `tests/models/test_api_characters.py`) verifying display metadata, hidden stat filter, and character_class absence
- [x] 7.3 Add unit tests for `build_character_summary()` verifying `updated_at` is populated
- [x] 7.4 Add unit tests for `require_no_active_adventure` verifying 409 when lock is live and pass-through when not
- [x] 7.5 Add unit tests for `_check_missing_descriptions` verifying warnings for empty descriptions on all 8 checked kinds and no warning for non-empty descriptions

## 8. Frontend — Types

- [x] 8.1 Add `updated_at: string` to `CharacterSummaryRead` in `frontend/src/lib/api/types.ts`
- [x] 8.2 Add `display_name: string | null` and `description: string | null` to `StackedItemRead`
- [x] 8.3 Add `display_name: string | null` and `description: string | null` to `ItemInstanceRead`
- [x] 8.4 Add `description: string | null`, `on_cooldown: boolean`, and `cooldown_remaining_ticks: number | null` to `SkillRead`
- [x] 8.5 Add `display_name: string | null` and `description: string | null` to `BuffRead`
- [x] 8.6 Add `quest_display_name: string | null`, `quest_description: string | null`, and `stage_description: string | null` to `ActiveQuestRead`
- [x] 8.7 Add `display_name: string | null` and `description: string | null` to `ArchetypeRead`
- [x] 8.8 Add `display_name: string | null` and `description: string | null` to `ActiveAdventureRead`
- [x] 8.9 Remove `character_class` from `CharacterStateRead` (field was `@deprecated`)
- [x] 8.10 Add `description: string | null` to `LocationOptionRead`
- [x] 8.11 Add `description: string | null` to `RegionGraphNode`

## 9. Frontend — API client

- [x] 9.1 Add `ActiveAdventureConflict` interface to `frontend/src/lib/api/characters.ts`
- [x] 9.2 Add `isActiveAdventureConflict()` type guard to `frontend/src/lib/api/characters.ts`

## 10. Testlandia

- [x] 10.1 Add a `hidden_stats` section to `testlandia/character_config.yaml` with at least one hidden stat
- [x] 10.2 Add `description` fields to all items, buffs, quests, skills, archetypes, and adventures that lack them
- [x] 10.3 Add a skill with `cooldown` configured to testlandia content
- [x] 10.4 Add `description` to all testlandia locations and regions
