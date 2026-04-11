# Design: Combat Refinement

## Context

Buffs are currently encounter-scoped ephemeral objects. `CombatContext` is constructed at `run_combat()` entry and torn down on exit; `ActiveCombatEffect` entries live only in `CombatContext.active_effects` and are never serialized. `BuffSpec.duration_turns: int` is the single lifetime control. There is no mechanism to prevent weaker duplicates of the same buff from stacking alongside a stronger one, and no way to carry buff state across combat encounters or adventures.

This change adds two orthogonal capabilities that share the same model touchpoints:

1. **Buff Blocking** — `exclusion_group` and `priority` on `BuffSpec` gate `apply_buff` applications, rejecting weaker duplicates.
2. **Buff Persistence** — replacing `duration_turns: int` with a `BuffDuration` object that expresses both the per-combat turn count and optional cross-combat expiry using the existing tick/second vocabulary. Persistent buffs are stored on `CharacterState`, re-injected into each `CombatContext`, and written back after combat.

The two features are independent. Blocking works entirely within `CombatContext` and requires no state persistence. Persistence adds `CharacterState.active_buffs`, a new DB table, and writeback logic. They are shipped in one change because both touch `BuffSpec` and `ActiveCombatEffect`.

---

## Goals / Non-Goals

**Goals:**

- `BuffSpec` gains `exclusion_group` and `priority`; `apply_buff` skips application when a same-group, same-target, equal-or-higher-priority effect is already active.
- `BuffSpec.duration_turns: int` replaced by `BuffSpec.duration: BuffDuration` (breaking change; `turns` required, time-based fields optional).
- Buffs without any time-based expiry field retain current encounter-scope behavior.
- Buffs with at least one time-based expiry field (`ticks`, `game_ticks`, or `seconds`) are persistent: stored in `CharacterState.active_buffs`, re-injected at future combat starts, and trimmed when expiry conditions are met.
- Persistent buffs carry their `remaining_turns` across combats — within an adventure the remaining count accumulated from the previous encounter is preserved.
- `DispelEffect` gains `permanent: bool = False`; when `True`, the effect is also removed from `CharacterState.active_buffs` so it does not re-enter future combats.
- Persistent buffs are persisted to the database following the existing skill-cooldowns table pattern.
- Author documentation updated.

**Non-Goals:**

- Persistent buffs on `target: "enemy"` — enemies are re-created each `run_combat()` call; persistent enemy buffs provide no meaningful cross-combat effect. Persistent buffs are only valid for `target: "player"`.
- Condition predicates for checking active buff state (e.g. `has_active_buff: curse-of-weakness`) — deferred.

---

## Decisions

### D1: `BuffDuration` is a new model, not the existing `Cooldown`

**Decision:** Introduce `BuffDuration` in `oscilla/engine/models/buff.py`. It looks like `Cooldown` but has `turns: int | str` as a required field with no `scope` field and no `game_ticks`-is-unsupported restriction.

| Field        | Type                 | Meaning                                                                                     |
| ------------ | -------------------- | ------------------------------------------------------------------------------------------- |
| `turns`      | `int \| str`         | _Required._ Number of combat turns per engagement. Template strings accepted (precompiled). |
| `ticks`      | `int \| str \| None` | `internal_ticks` that must elapse before the buff expires. Nil = no tick expiry.            |
| `game_ticks` | `int \| str \| None` | `game_ticks` that must elapse before expiry. Nil = no game-tick expiry.                     |
| `seconds`    | `int \| str \| None` | Real-world seconds before expiry. Nil = no wall-clock expiry.                               |

Encounter scope = only `turns` set. Persistent = any time-based field set. Multiple time-based fields are AND-ed (all must expire before the buff is removed).

**Alternatives considered:**

- Reuse `Cooldown` from `models/adventure.py` directly — rejected. `Cooldown` has a `scope: "turn" | None` that carries meaning for skills (per-combat vs adventure reset). Reusing it here would require either `scope: None` meaning something completely different in just the buff context, or adding a new scope value. `BuffDuration` keeps semantics unambiguous.
- Keep `duration_turns: int` and add `persistence: Cooldown | None` — rejected by the developer. Single parameter is preferred.

---

### D2: Encounter scope buffs remain entirely in `CombatContext`; persistent buffs live in `CharacterState.active_buffs`

**Decision:**

```
CharacterState.active_buffs: List[StoredBuff]
```

`StoredBuff` (a Pydantic `BaseModel` for clean serialization) holds:

| Field              | Type             | Purpose                                            |
| ------------------ | ---------------- | -------------------------------------------------- |
| `buff_ref`         | `str`            | Buff manifest name                                 |
| `remaining_turns`  | `int`            | Turns remaining at last combat-exit writeback      |
| `variables`        | `Dict[str, int]` | Merged resolved variables from original apply call |
| `tick_expiry`      | `int \| None`    | `internal_ticks` value at which this buff expires  |
| `game_tick_expiry` | `int \| None`    | `game_ticks` value at which this buff expires      |
| `real_ts_expiry`   | `int \| None`    | Unix timestamp at which this buff expires          |

At `run_combat()` entry: all non-expired `StoredBuff` entries for `target="player"` are injected into `CombatContext.active_effects` alongside combat-start item and skill buffs. The `ActiveCombatEffect` gets `is_persistent=True` to flag that it should be written back. At combat exit: persisted effects with `remaining_turns > 0` are written back; those with `remaining_turns == 0` are removed from `active_buffs`. Adventure end call (in the pipeline) sweeps `active_buffs` for entries whose expiry conditions are now satisfied.

**Alternatives considered:**

- Store persistent buffs in `active_adventure.step_state` — rejected. `step_state` is step-indexed; buffs should span the whole adventure regardless of which step issued them. Merging adventure-end cleanup with the step-state model is confusing.

---

### D3: `DispelEffect.permanent` removes from both `CombatContext` and `CharacterState.active_buffs`

**Decision:** `DispelEffect` gains `permanent: bool = False`. When `True`, after removing matching entries from `CombatContext.active_effects`, the handler also removes any `StoredBuff` in `CharacterState.active_buffs` with the same `buff_ref` and label. When `False` (default), only the in-combat entry is removed — the stored buff re-enters at the next combat.

**Alternatives considered:**

- Single `permanent` behavior always — rejected. Authors may want to temporarily cancel a buff in combat (e.g. an encounter that "suppresses" the player's bless effect for one fight) without clearing the persistent state.

---

### D4: Exclusion behavior is author-controlled — "block" or "replace"

**Decision:** `BuffSpec` gains `exclusion_mode: Literal["block", "replace"] = "block"`. Both modes share the same gate: any existing same-group same-target entry with `priority >= incoming_priority` blocks the new application (DEBUG log).

When **all** existing entries have `priority < incoming_priority`:

- `"block"` mode — the new application proceeds without touching the existing lower-priority entries; they expire naturally.
- `"replace"` mode — all existing same-group same-target entries are evicted from `CombatContext.active_effects` before the new application is inserted. Use this for buffs where only the strongest active version should be present (e.g. a thorns buff parameterized by strength).

`priority` on `BuffSpec` accepts `int | str`, following the same pattern as `CombatModifier.percent`: when it is a string, it is a variable name that must be declared in `BuffSpec.variables` and is looked up in the merged `resolved_vars` dict at apply time, yielding an `int`. This allows a single buff manifest (e.g. `thorns`) to carry different effective priorities depending on which variable values were passed at apply time (`{strength: 50}` vs `{strength: 30}`). `ActiveCombatEffect.priority` is always a resolved `int`. Load-time validation (extending `validate_variable_refs`) MUST reject a string `priority` that references an undeclared variable.

Equal-priority always blocks in both modes — "my version is neither weaker nor stronger, so don't replace or re-apply."

**Alternatives considered:**

- Static `int` only for priority — rejected when the user required variable-driven priority so that the same parameterized buff manifest can express stronger vs weaker variants. The `int | str` variable-name pattern is already established for `percent` fields and applies cleanly here.
- Automatic replacement whenever incoming priority is strictly higher — rejected in favor of explicit author opt-in through `exclusion_mode`, since some buff families have meaningful stacking semantics for lower-priority survivors.

---

### D5: DB table follows existing `character_iteration_skill_cooldowns` pattern

**Decision:** New table `character_iteration_active_buffs` with columns:

| Column             | Type      | Notes                                |
| ------------------ | --------- | ------------------------------------ |
| `iteration_id`     | `UUID FK` | References `character_iterations.id` |
| `buff_ref`         | `TEXT`    | Buff manifest name                   |
| `remaining_turns`  | `INT`     | Current remaining turns              |
| `variables_json`   | `TEXT`    | JSON-encoded `Dict[str, int]`        |
| `tick_expiry`      | `INT`     | Nullable `internal_ticks` expiry     |
| `game_tick_expiry` | `INT`     | Nullable `game_ticks` expiry         |
| `real_ts_expiry`   | `INT`     | Nullable Unix timestamp expiry       |

Composite PK `(iteration_id, buff_ref)` — one stored entry per buff name per iteration. If multiple instances of the same buff could be active simultaneously (which exclusion groups prevent for well-authored content but cannot guarantee without explicit validation), only one row is written per `buff_ref`. This is an acceptable simplification for the current scope.

**Alternatives considered:**

- JSON column on `character_iterations` — rejected. Project conventions use dedicated tables over JSON columns.

---

## Data Model Changes

### `oscilla/engine/models/buff.py`

**`BuffDuration` (new model):**

```python
class BuffDuration(BaseModel):
    """Duration control for a buff manifest.

    turns is required — the number of combat turns the buff fires per engagement.
    Template strings are accepted and precompiled at load time.

    If none of ticks, game_ticks, or seconds are set, the buff is encounter-scoped
    and is discarded when combat ends (current default behavior).

    If any time-based field is set, the buff is persistent: stored on the player
    and re-injected into each subsequent combat until the expiry conditions are met.
    Multiple time-based fields are AND-ed.
    """

    turns: int | str = Field(ge=1, description="Combat turns the buff persists per encounter.")
    ticks: int | str | None = Field(default=None, description="internal_ticks elapsed before expiry.")
    game_ticks: int | str | None = Field(default=None, description="game_ticks elapsed before expiry.")
    seconds: int | str | None = Field(default=None, description="Real-world seconds before expiry.")

    @property
    def is_persistent(self) -> bool:
        return any(v is not None for v in (self.ticks, self.game_ticks, self.seconds))
```

**`BuffSpec` changes:**

- Remove `duration_turns: int`
- Add `duration: BuffDuration`
- Add `exclusion_group: str | None = None`
- Add `priority: int | str = 0` — when a string, treated as a variable name resolved against the merged `resolved_vars` dict at apply time (same pattern as `CombatModifier.percent`); `ActiveCombatEffect.priority` always stores the resolved `int`; load-time `validate_variable_refs` extended to cover string `priority`
- Add `exclusion_mode: Literal["block", "replace"] = "block"`
- Load-time warning when `priority != 0` and `exclusion_group is None`

**`StoredBuff` (new model, same file):**

```python
class StoredBuff(BaseModel):
    buff_ref: str
    remaining_turns: int
    variables: Dict[str, int] = Field(default_factory=dict)
    tick_expiry: int | None = None
    game_tick_expiry: int | None = None
    real_ts_expiry: int | None = None
```

### `oscilla/engine/combat_context.py`

**`ActiveCombatEffect` additions:**

```python
exclusion_group: str = ""
priority: int = 0             # always the resolved int, even when BuffSpec.priority is a template string
exclusion_mode: str = "block" # mirrors BuffSpec.exclusion_mode; carried for eviction logic
is_persistent: bool = False   # set True when loaded from CharacterState.active_buffs
```

### `oscilla/engine/character.py`

```python
# New field on CharacterState
active_buffs: List[StoredBuff] = field(default_factory=list)
```

New helper: `sweep_expired_buffs(now_tick: int, now_game_tick: int, now_ts: int) -> None` — removes any `StoredBuff` whose expiry conditions are met.

`to_dict()` and `from_dict()` updated to include `active_buffs` (serialized as a list of dicts).

---

## Effect Handler Changes

### `apply_buff` in `oscilla/engine/steps/effects.py`

After the existing buff lookup and variable resolution, before constructing `ActiveCombatEffect`:

1. **Resolve priority** — if `spec.priority` is a template string, evaluate it against the merged variables dict and cast to `int`. This is the `resolved_priority`.
2. **Exclusion check** — if `spec.exclusion_group` is not None, scan `combat.active_effects` for entries with `ae.exclusion_group == spec.exclusion_group and ae.target == buff_target`. If any `ae.priority >= resolved_priority`, log DEBUG and return early (blocked).
3. **Eviction (replace mode only)** — if `spec.exclusion_mode == "replace"` and the exclusion check was not blocked, remove all same-group same-target entries from `combat.active_effects` before proceeding.
4. **Construct `ActiveCombatEffect`** — set `exclusion_group`, `priority` (resolved int), `exclusion_mode`, and `is_persistent = spec.duration.is_persistent`.

### `dispel` in `oscilla/engine/steps/effects.py`

After removing matching entries from `combat.active_effects`, when `effect.permanent is True`:

```python
player.active_buffs = [
    sb for sb in player.active_buffs if sb.buff_ref != label
]
```

---

## `run_combat()` Changes

**Entry:** after building `CombatContext` and before applying item buffs, inject `CharacterState.active_buffs`:

```python
now_ts = int(time.time())
player.sweep_expired_buffs(
    now_tick=player.internal_ticks,
    now_game_tick=player.game_ticks,
    now_ts=now_ts,
)
for stored in player.active_buffs:
    buff_manifest = registry.buffs.get(stored.buff_ref)
    if buff_manifest is None:
        logger.warning("stored buff %r not found in registry — skipping.", stored.buff_ref)
        continue
    spec = buff_manifest.spec
    ae = _build_active_combat_effect(spec, stored.buff_ref, "player", stored.variables, stored.remaining_turns)
    ae.is_persistent = True
    ctx.active_effects.append(ae)
```

**Exit (after combat ends for any reason):** write back persistent effects:

```python
player.active_buffs = [
    sb for sb in player.active_buffs if sb.buff_ref not in {ae.label for ae in ctx.active_effects if ae.is_persistent}
]
for ae in ctx.active_effects:
    if ae.is_persistent and ae.remaining_turns > 0:
        existing = next((sb for sb in player.active_buffs if sb.buff_ref == ae.label), None)
        if existing is not None:
            existing.remaining_turns = ae.remaining_turns
        else:
            player.active_buffs.append(
                StoredBuff(
                    buff_ref=ae.label,
                    remaining_turns=ae.remaining_turns,
                    variables=...,  # preserved from original application
                )
            )
```

This requires `ActiveCombatEffect` to carry the original `variables` dict for writeback.

---

## Adventure-End Sweep

In `oscilla/engine/pipeline.py`, the point where `internal_ticks` is incremented at adventure completion, call:

```python
player.sweep_expired_buffs(
    now_tick=player.internal_ticks,
    now_game_tick=player.game_ticks,
    now_ts=int(time.time()),
)
```

---

## Migration Plan

- The `duration_turns → duration` rename is breaking. The only content is `testlandia/` (internal test content). All buff manifests in `testlandia/` must be updated from `duration_turns: N` to `duration: {turns: N}`.
- New Alembic migration: purely additive (`character_iteration_active_buffs` table creation). No existing rows affected.
- `from_dict()` defaults `active_buffs` to `[]` when the key is absent — backward compatible with existing saves.

---

## Testing Philosophy

- **Unit tests** for exclusion-group blocking logic: construct `ActiveCombatEffect` entries directly, call `apply_buff` handler, assert early exit.
- **Unit tests** for `BuffDuration.is_persistent` property.
- **Unit tests** for `StoredBuff` serialization roundtrip.
- **Integration tests** using `tests/fixtures/content/` minimal fixture set for: persistent buff writeback after combat, re-injection into second combat, `sweep_expired_buffs` removing expired entries, `permanent=True` dispel clearing stored state.
- No tests may reference `content/` (testlandia). All fixture manifests use `test-` prefixed names.
- `mock_tui` fixture used for all pipeline tests.

---

## Documentation Plan

| Document                  | Audience        | Changes                                                                                            |
| ------------------------- | --------------- | -------------------------------------------------------------------------------------------------- |
| `docs/authors/skills.md`  | Content authors | `BuffSpec` fields table updated; new "Buff Blocking" section; new "Buff Persistence" section       |
| `docs/authors/effects.md` | Content authors | `apply_buff` entry unchanged; `dispel` entry gains `permanent` field description                   |
| `docs/dev/game-engine.md` | Developers      | `BuffSpec` fields; `ActiveCombatEffect` new fields; `StoredBuff`; `CombatContext` lifecycle update |

---

## Risks / Trade-offs

| Risk                                                                                                                                                                                              | Mitigation                                                                                          |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `buff_ref` in `StoredBuff` references a buff that is later removed from content                                                                                                                   | `run_combat()` entry logs a warning and skips the stored buff — no crash                            |
| Composite PK `(iteration_id, buff_ref)` means two concurrent active instances of the same buff (e.g. applied twice in one combat) collapse to one stored row                                      | Exclusion groups naturally prevent this for well-authored content; documented as a known limitation |
| Template strings in `BuffDuration.turns` are precompiled at load time but `remaining_turns` is stored as a resolved int — subsequent games with different stats will not re-evaluate the template | This matches existing skillcooldown behavior; `remaining_turns` is always written as a concrete int |
