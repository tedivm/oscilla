## Why

The engine has carried a `ClassManifest` / `ClassCondition` placeholder since the foundation change — a no-op stub that always evaluates to `true` and carries no mechanics. The design philosophy explicitly names archetypes as a first-class authoring primitive, and the condition, effect, and template surfaces are now mature enough to implement them properly. Doing it now eliminates the misleading `Class` stub and completes the "three surfaces" requirement for character type data.

## What Changes

- **BREAKING**: Remove `ClassManifest`, `ClassSpec`, `ClassCondition`, `game_class.py`, and the `Class` entry in all dispatch tables. Content using `kind: Class` or `type: class` must migrate.
- Add `Archetype` as a new first-class manifest kind, independent like `Skill` and `Item` — one YAML file per archetype, organized freely by the content author.
- `ArchetypeSpec` declares: `displayName`, `description`, `gain_effects`, `lose_effects`, `passive_effects`.
  - `gain_effects` — dispatched immediately when `archetype_add` fires for this archetype.
  - `lose_effects` — dispatched immediately when `archetype_remove` fires for this archetype.
  - `passive_effects` — evaluated continuously in `effective_stats()` and `available_skills()`; the archetype being held serves as the implicit outer condition; each entry may carry an optional additional `condition` to refine within that baseline.
- Add `archetype_add` and `archetype_remove` to the `Effect` union. Both are **idempotent by default**: `archetype_add` on an already-held archetype is a no-op; `archetype_remove` on a non-held archetype is a no-op. A `force: bool = False` field on each effect overrides this — when `true`, lifecycle effects are dispatched regardless of current held state.
- Add `skill_revoke` to the `Effect` union. Removes a named skill from `CharacterState.known_skills`; no-op if the skill is not present.
- Add five new condition predicates: `has_archetype`, `has_all_archetypes`, `has_any_archetype`, `archetype_count`, and `archetype_ticks_elapsed`.
- Add `archetypes: Dict[str, GrantRecord]` to `CharacterState`, recording the tick and timestamp each archetype was granted — same structure as milestones.
- Rename `MilestoneRecord` → `GrantRecord` in `oscilla/engine/models/base.py`. Both milestones and archetypes use `GrantRecord`.
- Loader validates all archetype references (all four condition predicates, `archetype_add`, `archetype_remove`) against declared `Archetype` manifests — unknown names are hard **load errors**, not warnings.
- `effective_stats()` and `available_skills()` loop each archetype's `passive_effects` when the archetype is held.

## Capabilities

### New Capabilities

- `archetype-system`: `ArchetypeManifest` / `ArchetypeSpec` model with `gain_effects`, `lose_effects`, `passive_effects`; `archetypes: Dict[str, GrantRecord]` on `CharacterState`; persistence; template exposure.
- `archetype-conditions`: `has_archetype`, `has_all_archetypes`, `has_any_archetype`, `archetype_count`, and `archetype_ticks_elapsed` condition predicates.
- `archetype-effects`: `archetype_add` and `archetype_remove` effect types with idempotent-by-default lifecycle dispatch and optional `force` override.
- `skill-revoke`: `skill_revoke` effect type; removes skill from `known_skills`; primarily useful in archetype `lose_effects` but valid anywhere effects are accepted.

### Modified Capabilities

- `condition-evaluator`: Five new predicates added; `ClassCondition` removed (**BREAKING**).
- `passive-effects`: `effective_stats()` and `available_skills()` now also loop archetype-scoped passive effects in addition to global `game.yaml` passive effects.
- `manifest-system`: `Archetype` kind added to `MANIFEST_REGISTRY`, `ContentRegistry`, `kinds.py`, and `schema_export.py`; `Class` kind removed from all (**BREAKING**).

## Impact

- New file: `oscilla/engine/models/archetype.py`
- Deleted: `oscilla/engine/models/game_class.py`
- `oscilla/engine/models/base.py` — `MilestoneRecord` renamed to `GrantRecord`; four new condition models; `ClassCondition` removed; `Condition` union updated
- `oscilla/engine/models/adventure.py` — `ArchetypeAddEffect`, `ArchetypeRemoveEffect`, `SkillRevokeEffect` added to `Effect` union
- `oscilla/engine/models/__init__.py` — replace `ClassManifest` with `ArchetypeManifest`; remove `game_class` import
- `oscilla/engine/conditions.py` — four new `case` branches; `ClassCondition` case removed
- `oscilla/engine/character.py` — `archetypes: Dict[str, GrantRecord]` field; `effective_stats()` and `available_skills()` loop archetype passive effects; serialization/deserialization updated
- `oscilla/engine/steps/effects.py` — `archetype_add`, `archetype_remove`, `skill_revoke` dispatch cases
- `oscilla/engine/registry.py` — `classes` registry removed; `archetypes: KindRegistry[ArchetypeManifest]` added
- `oscilla/engine/kinds.py` — `class` kind removed; `archetype` kind added (`creatable=True`)
- `oscilla/engine/schema_export.py` — `AnyManifest` union updated
- `oscilla/engine/loader.py` — archetype ref validation added; condition tree walker for archetype predicates; effect walker for `archetype_add`/`archetype_remove`; class loading removed; `_collect_quest_stage_conditions_from_manifest` extended to cover archetype manifests
- `docs/authors/archetypes.md` — new authoring document; added to `docs/authors/README.md` TOC
- `docs/dev/game-engine.md` — archetype section added
- `content/testlandia/` — archetype manifests demonstrating all features for manual QA
