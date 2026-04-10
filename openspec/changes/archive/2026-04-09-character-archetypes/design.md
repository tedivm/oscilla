## Context

The engine has carried a `ClassManifest` / `ClassCondition` placeholder since the game-engine-foundation change. `ClassCondition` always evaluates to `True` — it has no mechanics. `ClassManifest` holds only a display name and an optional `primary_stat` hint with no engine effect. These stubs block the condition union from ever having a real class/archetype predicate because the slot is taken by a no-op.

The design philosophy document explicitly names archetypes as a first-class authoring primitive and describes them as first-class across all three authoring surfaces (conditions, effects, templates). The passive-effects change established the pattern for continuous condition-gated stat and skill grants. The skill-system change established `skill_grant` and `known_skills`. All prerequisites are in place.

This change removes the `Class` placeholder entirely and implements archetypes properly: independent manifests, lifecycle effects, continuous passive effects, four condition predicates, two effect types, a new `skill_revoke` effect, and hard load-time validation of all cross-references.

---

## Goals / Non-Goals

**Goals:**

- Remove `ClassManifest`, `ClassSpec`, `ClassCondition`, and `game_class.py` completely.
- Add `Archetype` as a first-class manifest kind: one YAML file per archetype, loadable from any directory structure.
- `ArchetypeSpec` carries `displayName`, `description`, `gain_effects`, `lose_effects`, and `passive_effects`.
- Add `archetype_add` and `archetype_remove` to the `Effect` union; both idempotent by default, with an opt-in `force` flag.
- Add `skill_revoke` to the `Effect` union; removes a named skill from `known_skills`.
- Add four condition predicates: `has_archetype`, `has_all_archetypes`, `has_any_archetype`, `archetype_count`.
- Add `archetypes: Dict[str, GrantRecord]` to `CharacterState` with `to_dict`/`from_dict` persistence, recording the tick and timestamp each archetype was granted.
- `effective_stats()` and `available_skills()` loop archetype `passive_effects` for all held archetypes.
- All archetype references in conditions and effects are validated at load time; unknown names are hard errors.
- Expose `archetypes` in the template surface via `PlayerContext`.
- Update existing author and developer documentation; add a new `docs/authors/archetypes.md`.
- Add testlandia archetypes for manual QA of all new features.

**Non-Goals:**

- A TUI screen for browsing or selecting archetypes (UI work is separate).
- Building a full class-progression system — archetypes are primitives; a class system is authored using those primitives.
- Migrating existing `Class` manifests in the wild — `Class` was a no-op stub with no shipped content games; the breaking removal is clean.

---

## Decisions

### D1: Archetype as an independent manifest kind, not a game.yaml subdocument

**Decision:** `Archetype` is a standalone manifest kind like `Skill` and `Item`, loaded from YAML files with `kind: Archetype`. It is not a nested dict inside `game.yaml`.

**Alternatives considered:**

- Dictionary in `game.yaml` under `archetypes:` key (original roadmap sketch) — rejected. It collocates all archetypes in one file regardless of package complexity, cannot be organized into subdirectories, and does not benefit from the existing manifest loading, registry, and validation pipeline.
- Subdocument in `game.yaml` with individual files as overrides — rejected. Adds a two-level loading complexity for no benefit.

**Rationale:** A large game with dozens of factions, guilds, and progression classes should be able to separate them into `archetypes/combat/`, `archetypes/factions/`, `archetypes/guilds/`, etc. The existing manifest loader already handles arbitrary directory structures. Using the same pattern costs nothing and gives authors the organization freedom they need.

---

### D2: Archetype passive effects are structurally identical to `PassiveEffect` but the held-archetype condition is implicit

**Decision:** Each entry in `ArchetypeSpec.passive_effects` is the same `PassiveEffect` model currently used in `GameSpec`. When evaluating, the engine implicitly gates on archetype membership — it only evaluates an archetype's passive effects if the character currently holds that archetype. An optional `condition` field within the passive effect entry may further refine within that baseline.

**Alternatives considered:**

- Require authors to write `has_archetype: warrior` explicitly on every archetype passive effect — rejected. Repetitive and error-prone; the archetype definition is already the scope.
- A separate `ArchetypePassiveEffect` model without the `name` field — considered. The `name` field on `PassiveEffect` is informational (used only in logging). Keeping the same model means no new type, less cognitive overhead, and the `name` field remains available for debugging if authors want to provide it.

**Outcome:** `ArchetypeSpec.passive_effects: List[PassiveEffect]` — same model, implicit outer condition applied by the evaluation loop.

---

### D3: `archetype_add` / `archetype_remove` are idempotent by default; `force: bool = False` overrides this

**Decision:** `ArchetypeAddEffect` (`type: archetype_add`): if the archetype is already held, the effect is a no-op unless `force: true`. `ArchetypeRemoveEffect` (`type: archetype_remove`): if the archetype is not held, the effect is a no-op unless `force: true`. When `force: true`, lifecycle effects (`gain_effects` or `lose_effects`) are dispatched regardless of current held state; the `archetypes` set is updated accordingly.

**Rationale:** The default no-op protects against double-grants from adventure branching or multi-path content. The `force` option supports authored use cases where re-triggering lifecycle effects is intentional (e.g., a "renew guild oath" adventure that re-fires guild initiation effects even for existing members). Adventure authors who want to guard against accidental no-ops can use `not: {type: has_archetype, name: warrior}` on the step condition.

---

### D4: `skill_revoke` is included in this change

**Decision:** Add `SkillRevokeEffect` (`type: skill_revoke`, field `skill: str`) to the `Effect` union. It removes the named skill from `CharacterState.known_skills`; if the skill is not present, it is a no-op (no error).

**Rationale:** `lose_effects` without `skill_revoke` is incomplete for the archetypal use case: an archetype that grants a skill on gain should be able to revoke it on removal. The mechanic is simple (~5 lines to implement), and the symmetry with `skill_grant` is obvious. Deferring it to a separate change would require deprecating `lose_effects` as under-powered and re-visiting the design.

**Scope:** `skill_revoke` is valid anywhere effects are accepted, not only in `lose_effects`. Content authors may use it in adventure steps, quest completion effects, or any other effect context.

---

### D5: All archetype cross-references are hard load errors

**Decision:** Any condition predicate or effect that references an archetype name not present in the loaded `Archetype` manifests produces a `LoadError` and prevents the package from loading. This applies to: `has_archetype.name`, `has_all_archetypes.names` (each entry), `has_any_archetype.names` (each entry), `archetype_ticks_elapsed.name`, `archetype_add.name`, `archetype_remove.name`.

**Alternatives considered:**

- Load warning (non-fatal) — rejected. The design philosophy already uses this for item labels (undeclared label is likely a styling typo, game logic not affected). For archetype references, an unknown archetype name is always a runtime logic error — the condition will never be true or the effect will never grant the intended archetype. Silent failures mislead authors. A hard error forces correction.
- Runtime error when evaluated — rejected. Fails at play time, not load time; harder to diagnose.

**Implementation:** Follows the identical pattern as `_collect_quest_stage_conditions_in_condition` / `_collect_quest_stage_conditions_from_manifest` / `_validate_quest_stage_condition_refs` in `loader.py`. Two collector functions (one for condition trees, one for effect lists) and one validator that builds the known-archetype name set and emits `LoadError` for mismatches.

---

### D6: `archetypes: Dict[str, GrantRecord]` in CharacterState persisted as a nested dict

**Decision:** `CharacterState` gains `archetypes: Dict[str, GrantRecord] = field(default_factory=dict)`, reusing the same `GrantRecord` model (fields: `tick: int`, `timestamp: int`). When `archetype_add` fires, the engine records `GrantRecord(tick=player.internal_ticks, timestamp=int(time.time()))` under the archetype name — capturing the exact tick and wall-clock time the archetype was granted. `to_dict()` serializes as `{name: {"tick": r.tick, "timestamp": r.timestamp} for name, r in self.archetypes.items()}`. `from_dict()` supports the same two-format migration as milestones: a legacy list falls back to `GrantRecord(tick=0, timestamp=0)` per entry; the current nested-dict format is read directly. Unknown archetype names in persisted state are silently dropped during deserialization (content-drift resilience).

**Rationale:** `GrantRecord` is the generic name for this model — it records when something was granted (tick + timestamp) and is reused for both milestones and archetypes. The grant tick is immediately available for `archetype_ticks_elapsed` conditions without a follow-on refactor. The structure is consistent with milestones — authors and developers only need to learn one pattern. Existing `character_class: str | None` field on `CharacterState` is retained as-is for backward-compatible persistence; it is never written by the new archetype system but may exist in old saves. → No migration needed for saves.

---

### D7: Rename `MilestoneRecord` → `GrantRecord`

**Decision:** Rename the Pydantic model in `oscilla/engine/models/base.py` from `MilestoneRecord` to `GrantRecord`. Update all references in `character.py`, `tests/engine/test_character.py`, and `docs/dev/game-engine.md`. No backward-compatible alias is kept.

**Rationale:** `MilestoneRecord` implies the model is milestone-specific, but it is now shared by both `CharacterState.milestones` and `CharacterState.archetypes`. `GrantRecord` names what the model actually does — records the tick and timestamp at which something was granted — without coupling it to a single use site. The rename is clean; there are no external consumers of this symbol outside the repo.

---

## Architecture

```
Archetype YAML files
  kind: Archetype
  name: warrior
  spec:
    displayName: "Warrior"
    gain_effects: [...]
    lose_effects: [...]
    passive_effects: [...]

       │ loader parses & validates
       ▼
ContentRegistry.archetypes: KindRegistry[ArchetypeManifest]

       │
       ├── archetype_add effect ──► CharacterState.archetypes[name] = GrantRecord(tick, ts)
       │                            dispatch gain_effects
       │
       ├── archetype_remove effect ► CharacterState.archetypes.discard(name)
       │                             dispatch lose_effects
       │
       ├── has_archetype condition ─► name in player.archetypes
       │
       ├── effective_stats(registry) ─► loop archetypes → archetype.passive_effects
       │
       └── available_skills(registry) ► loop archetypes → archetype.passive_effects
```

---

## File-Level Changes

### New file: `oscilla/engine/models/archetype.py`

```python
class ArchetypeSpec(BaseModel):
    displayName: str
    description: str = ""
    gain_effects: List[Effect] = []
    lose_effects: List[Effect] = []
    passive_effects: List[PassiveEffect] = []

class ArchetypeManifest(ManifestEnvelope):
    kind: Literal["Archetype"]
    spec: ArchetypeSpec
```

`PassiveEffect` and `Effect` are forward-references; `ArchetypeSpec` must follow them in import order or use `TYPE_CHECKING` guards. The `PassiveEffect` type is imported from `oscilla.engine.models.game`; `Effect` from `oscilla.engine.models.adventure`.

### Deleted: `oscilla/engine/models/game_class.py`

All three symbols (`ClassSpec`, `ClassManifest`, and `ClassCondition` in `models/base.py`) are removed. `ClassCondition` is removed from the `Condition` union in `models/base.py`.

### `oscilla/engine/models/base.py` — rename + condition union

Rename `MilestoneRecord` to `GrantRecord`; update all references in `character.py`, tests, and docs.

Remove `ClassCondition`. Add five new condition models:

```python
class HasArchetypeCondition(BaseModel):
    type: Literal["has_archetype"]
    name: str  # archetype manifest name

class HasAllArchetypesCondition(BaseModel):
    type: Literal["has_all_archetypes"]
    names: List[str]

class HasAnyArchetypeCondition(BaseModel):
    type: Literal["has_any_archetypes"]
    names: List[str]

class ArchetypeCountCondition(BaseModel):
    type: Literal["archetype_count"]
    # Numeric comparison — same pattern as PrestigeCountCondition
    gte: int | None = None
    lte: int | None = None
    eq: int | None = None

class ArchetypeTicksElapsedCondition(BaseModel):
    """True when internal_ticks elapsed since the named archetype was granted satisfies the comparator.

    elapsed = player.internal_ticks - player.archetypes[name].tick  (from GrantRecord)
    Returns False if the archetype is not held.
    At least one of gte / lte must be set.
    """
    type: Literal["archetype_ticks_elapsed"]
    name: str  # archetype manifest name
    gte: int | None = None
    lte: int | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "ArchetypeTicksElapsedCondition":
        if self.gte is None and self.lte is None:
            raise ValueError("archetype_ticks_elapsed condition must specify at least one of: gte, lte")
        return self
```

Add all five to the `Condition` union.

### `oscilla/engine/models/adventure.py` — effect union

Add three new effect models. `ArchetypeAddEffect` and `ArchetypeRemoveEffect` both carry `force: bool = False`:

```python
class ArchetypeAddEffect(BaseModel):
    type: Literal["archetype_add"]
    name: str
    force: bool = False

class ArchetypeRemoveEffect(BaseModel):
    type: Literal["archetype_remove"]
    name: str
    force: bool = False

class SkillRevokeEffect(BaseModel):
    type: Literal["skill_revoke"]
    skill: str
```

Add all three to the `Effect` union.

### `oscilla/engine/character.py`

- Add `archetypes: Dict[str, GrantRecord] = field(default_factory=dict)` to `CharacterState`; import `GrantRecord` from `oscilla.engine.models.base`.
- `to_dict()`: add `"archetypes": {name: {"tick": r.tick, "timestamp": r.timestamp} for name, r in self.archetypes.items()}`.
- `from_dict()`: deserialize archetypes using the same two-format migration as milestones: legacy list (`["warrior"]`) → `GrantRecord(tick=0, timestamp=0)` per entry; current nested-dict (`{"warrior": {"tick": 42, "timestamp": ...}}`) → `GrantRecord` directly. Silently drop any name not present in `registry.archetypes` when registry is provided (content-drift resilience).
- `effective_stats()`: after the global `passive_effects` loop, add a loop over `self.archetypes` → look up `ArchetypeManifest` in registry → evaluate each `passive_effect.condition` → apply `stat_modifiers`.
- `available_skills()`: same pattern for `skill_grants`.

### `oscilla/engine/conditions.py`

Remove `ClassCondition` import and `case ClassCondition()` branch. Add five new `case` branches:

```python
case HasArchetypeCondition(name=n):
    return n in player.archetypes
case HasAllArchetypesCondition(names=ns):
    return all(n in player.archetypes for n in ns)
case HasAnyArchetypeCondition(names=ns):
    return any(n in player.archetypes for n in ns)
case ArchetypeCountCondition() as c:
    return _numeric_compare(len(player.archetypes), c)
case ArchetypeTicksElapsedCondition() as c:
    record = player.archetypes.get(c.name)
    if record is None:
        return False
    elapsed = player.internal_ticks - record.tick
    if c.gte is not None and elapsed < c.gte:
        return False
    if c.lte is not None and elapsed > c.lte:
        return False
    return True
```

### `oscilla/engine/steps/effects.py`

Add three new `case` branches:

- `ArchetypeAddEffect`: if not held (or `force=True`): look up manifest in registry, dispatch `gain_effects`, set `player.archetypes[name] = GrantRecord(tick=player.internal_ticks, timestamp=int(time.time()))`.
- `ArchetypeRemoveEffect`: if held (or `force=True`): look up manifest in registry, dispatch `lose_effects`, call `player.archetypes.pop(name, None)`.
- `SkillRevokeEffect`: `player.known_skills.discard(effect.skill)`.

### `oscilla/engine/registry.py`

Remove `self.classes: KindRegistry[ClassManifest]` and its registration branch. Add `self.archetypes: KindRegistry[ArchetypeManifest]` and registration.

### `oscilla/engine/kinds.py`

Remove `ManifestKind("class", ...)`. Add:

```python
ManifestKind("archetype", "archetypes", "archetypes", "Archetype", ArchetypeManifest, creatable=True)
```

### `oscilla/engine/models/__init__.py`

Replace `ClassManifest` import and registry entry with `ArchetypeManifest`. Remove `game_class` import.

### `oscilla/engine/schema_export.py`

Replace `ClassManifest` with `ArchetypeManifest` in `AnyManifest` union.

### `oscilla/engine/loader.py`

Remove class loading (the `"Class"` branch in `register_manifests`). Add:

1. `_collect_archetype_refs_in_condition(condition) → Set[str]` — recursive tree walker collecting archetype name strings from `HasArchetypeCondition`, `HasAllArchetypesCondition`, `HasAnyArchetypeCondition`, and `ArchetypeTicksElapsedCondition` leaves, recursing into `AllCondition`, `AnyCondition`, `NotCondition`.

2. `_collect_archetype_refs_in_effects(effects) → Set[str]` — collects `name` from `ArchetypeAddEffect` and `ArchetypeRemoveEffect` instances.

3. `_collect_archetype_refs_from_manifest(m) → Set[str]` — covers all condition and effect sites across all manifest kinds:
   - Adventures: step conditions (`NarrativeStep.condition?`, `PassiveStep.bypass`), step effects (all step types), `adv.spec.requires`, choice option `requires`
   - Locations/Regions: `unlock`, `effective_unlock`, adventure entry `requires`
   - Skills: `use_effects`
   - Items: `use_effects`, equip `requires`
   - Archetype manifests themselves: `gain_effects`, `lose_effects`, `passive_effects[*].condition`
   - Game: `passive_effects[*].condition`

4. `_validate_archetype_refs(manifests) → List[LoadError]` — builds `archetype_names = {m.metadata.name for m in manifests if m.kind == "Archetype"}`, collects refs from all manifests, emits `LoadError` for any ref not in `archetype_names`.

---

## Migration Plan

This is a breaking removal of a never-functional stub. No content package shipped with real `Class` mechanics (the condition always returned `True`, the manifest had no engine effect). Migration steps:

1. Any content YAML with `kind: Class` → rename to `kind: Archetype` and add a full `ArchetypeSpec`.
2. Any condition `type: class` → replace with `type: has_archetype` (with a `name` field).
3. Code using `registry.classes` → replace with `registry.archetypes`.
4. Code importing `ClassManifest`, `ClassCondition`, `ClassSpec` → update imports.

The loader's hard error on unknown archetype refs will immediately identify any missed references after migration.

---

## Risks / Trade-offs

- **Circular import risk in `archetype.py`**: `ArchetypeSpec` depends on `Effect` (from `adventure.py`) and `PassiveEffect` (from `game.py`). Both of those already import from `base.py`. Python circular imports are managed by using `TYPE_CHECKING` blocks and string forward references where needed. The same pattern is already used in `game.py` (its `Effect` references are deferred). → Follow the existing deferred-import pattern.

- **`effective_stats()` performance**: The archetype passive-effects loop adds another registry lookup per held archetype per `effective_stats()` call. For typical play (2–5 archetypes, called infrequently), this is negligible. No caching is needed at this scale. → No mitigation required.

- **Old saves with `character_class` field**: `CharacterState.character_class: str | None` will remain in `from_dict()` as a read-ignored legacy field; it is never written by the new archetype system but tolerated in old save data. → No migration needed for saves.

---

## Open Questions

None. All design decisions resolved through the exploration conversation.
