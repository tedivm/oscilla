## Context

The engine currently hardcodes four progression primitives as first-class fields on `CharacterState`: `level`, `xp`, `hp`, and `max_hp`. These are coupled to hardcoded engine mechanics: `add_xp()` auto-increments `level` when XP crosses thresholds declared in `game.yaml`, and simultaneously mutates `max_hp` by `hp_per_level` from `game.yaml`. The `xp_grant` effect is the only way to apply XP, and the `HpFormula` struct in `game.yaml` is the only way to configure HP per level. None of these are configurable beyond fixed integers.

This violates the engine's core design principle. A game without levels (milestone-based, stress-based, or purely narrative) still inherits all of this machinery. A game with randomized HP gains (D20 HD roll + constitution modifier per level) cannot express that. A game whose progression currency is called "reputation" instead of "xp" must fight the engine's naming.

The fix is to treat `level`, `xp`, `hp`, and `max_hp` as ordinary author-declared stats — no different from `strength` or `gold`. The trigger and effect systems already provide everything needed for procedural progression. The only genuinely new capability required is **derived stats**: stats whose value is always computed from other stats, never stored directly.

**Key files affected:**

| File                                        | Change                                                                                                                  |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `oscilla/engine/models/character_config.py` | Add `derived: str \| None` to `StatDefinition`                                                                          |
| `oscilla/engine/models/game.py`             | Remove `HpFormula`, remove `xp_thresholds` from `GameSpec`                                                              |
| `oscilla/engine/models/adventure.py`        | Remove `XpGrantEffect` from the `Effect` union                                                                          |
| `oscilla/engine/character.py`               | Remove `level`, `xp`, `hp`, `max_hp` fields; remove `add_xp()`; add `_derived_shadows: Dict[str, int \| bool \| None]`  |
| `oscilla/engine/templates.py`               | Remove `player.level`, `player.hp`, `player.max_hp` from `PlayerContext`; add new `SAFE_GLOBALS` functions              |
| `oscilla/engine/steps/effects.py`           | Remove `XpGrantEffect` handler; add `_recompute_derived_stats()` call after every stat mutation                         |
| `oscilla/engine/loader.py`                  | Remove `on_level_up` built-in; validate derived stat write targets; extend `on_stat_threshold` to support derived stats |
| `oscilla/engine/tui.py`                     | Remove hardcoded `player.level`, `player.xp`, `player.hp`, `player.max_hp` reads                                        |
| `db/versions/`                              | Migration to remove DB columns `level`, `xp`, `hp`, `max_hp` from `character_iterations`                                |
| `content/testlandia/`                       | Rebuild `character_config.yaml` and `game.yaml` to use stat-based progression                                           |

---

## Goals / Non-Goals

**Goals:**

- Remove `level`, `xp`, `hp`, `max_hp` as hardcoded `CharacterState` fields; declare them as stats in `character_config.yaml`
- Remove `HpFormula` and `xp_thresholds` from `game.yaml`
- Remove `xp_grant` effect; use `stat_change` everywhere
- Remove `on_level_up` built-in trigger; use `on_stat_threshold` on the `level` stat
- Add `StatDefinition.derived: str | None` — a Jinja2 formula evaluated on read, never stored
- Derived stats participate in `on_stat_threshold` trigger detection via shadow values
- `on_stat_threshold` fires once per threshold crossed when multiple thresholds are crossed in a single stat change (multi-cross)
- Add dice pool functions and ergonomic aliases to `SAFE_GLOBALS`
- Add `Extended Template Primitives` roadmap item for deferred additions

**Non-Goals:**

- Dependency tracking between derived stats (which stored stats does each derived stat read) — change detection uses a simpler model: re-evaluate all derived stats after any stored stat mutation
- Circular derived stat dependencies — forbidden at load time; non-circular chains are fully supported
- `level` as a built-in concept anywhere in the engine after this change — it is fully author-controlled
- TUI panel customization for displaying stats — the TUI will read `public_stats` for display; a full TUI overhaul is a separate roadmap item
- Pool-based dice functions beyond the set specified here (`lerp`, `average`, etc.) — deferred to the Extended Template Primitives roadmap item

---

## Decisions

### Decision 1: Hard removal of level/xp/hp/max_hp as engine primitives

Rather than a soft deprecation path, these four fields are removed from `CharacterState` and `PlayerContext` entirely. Games that want them declare them in `character_config.yaml` as regular stats. `player.stats["level"]` replaces `player.level` in templates.

**Rationale:** The project is pre-alpha with no published content packages. The tech debt cost of a compatibility shim outweighs the zero-user migration cost. A soft path leaves two competing representations in the codebase indefinitely.

**TUI impact:** The TUI currently hardcodes reads of `player.level`, `player.xp`, etc. for the header bar and XP progress display. After this change, the TUI reads these from `player.stats` by looking up stats declared as `public` in `CharacterConfig`. Specific display logic (e.g. the XP progress bar) is stripped — the TUI shows public stats as a list until the Full TUI Upgrade roadmap item addresses customizable panels.

---

### Decision 2: Derived stats use shadow values for change detection, not dependency tracking

After every `stat_change` or `stat_set` effect, the engine calls `_recompute_derived_stats(player, registry, template_engine)`. This re-evaluates every derived stat formula and compares the result to the stat's last known computed value (stored in `player._derived_shadows`). Stats whose computed value changed are collected; then `on_stat_threshold` detection runs for each changed stat.

**Rationale:** True dependency tracking (knowing which stored stats feed into each derived formula) requires parsing the Jinja2 AST to find variable accesses — fragile and complex. Re-evaluating all derived stats after any mutation is simpler and correct. The number of derived stats in any realistic game is small (< 20), so the cost is negligible.

**Alternative considered:** Lazy evaluation only (compute on read, no proactive re-evaluation). Rejected because it misses the change detection window needed to fire `on_stat_threshold` triggers for derived stats.

---

### Decision 3: Derived stats may reference other derived stats; circular dependencies are a load error

The loader builds a dependency graph from derived stat formulas and performs a topological sort at load time. Non-circular chains (A derives from B, B derives from C) are fully supported and evaluated in dependency order. A cycle (A → B → A, or A → A) is a fatal load error.

**Rationale:** Chaining derived stats is genuinely useful — `constitution_bonus` derives from `constitution`, and `max_hp_cap` might derive from `constitution_bonus`. Forbidding this forces authors to duplicate formula logic or collapse everything into one large expression. The topological sort required to support chaining is straightforward (Kahn's algorithm on the dependency graph).

**Evaluation order:** `_recompute_derived_stats()` evaluates stats in topological order (dependencies before dependents). When building `PlayerContext`, the same sorted order is used so earlier derived stats are available in `player.stats` when later ones are evaluated.

**Edge case:** Self-reference (`derived: "{{ player.stats['level'] }}"` on the `level` stat itself) produces a cycle of length 1 and is caught as a circular dependency load error. The error message identifies all stats involved in the cycle.

---

### Decision 4: on_stat_threshold supports `fire_mode` — `each` (default) or `highest`

Each `on_stat_threshold` entry declares a `fire_mode` field (default `each`):

- **`each`** — fires once per threshold crossed in a single mutation; a jump from 0 → 700 with thresholds at 100, 300, 600 enqueues all three triggers in ascending order.
- **`highest`** — fires only the single highest threshold crossed; the same 0 → 700 jump enqueues only the `600` threshold trigger, suppressing the lower ones entirely.

`each` and `highest` entries for the same stat operate independently: `each` entries all fire, then the highest `highest` entry fires (if any). Authors may mix modes on a single stat without ambiguity.

**Rationale:** `each` preserves backward-compatible XP leveling behavior (each level-up adventure fires individually). `highest` enables prestige tiers, title systems, and other contexts where only the final rank matters and intermediate ranks are noise. Without this knob, authors must work around the firing order with `repeatable: false` on adventures — but that suppresses the adventure entirely after first completion, which is the wrong tool.

**Downward crossings:** `on_stat_threshold` currently only fires on upward crossings. This change does not add downward crossing support. Authors who want level-down behavior (rare) can use the `stat_set` effect in a trigger adventure to explicitly reset the `level` stat.

---

### Decision 5: xp_grant effect is removed; stat_change is sufficient

The `XpGrantEffect` Pydantic model and its dispatch case in `run_effect()` are removed. Authors use `stat_change` targeting their XP stat.

**Rationale:** `xp_grant` was special-cased solely because it needed to trigger level detection. With the derived stats + threshold system, that logic moves to `_recompute_derived_stats()` which runs after every `stat_change`. There is no longer any reason for a named `xp_grant` effect.

---

### Decision 6: Derived stat formulas choose their stat context — `stored` (default) or `effective`

`StatDefinition` gains a `stat_context: Literal["stored", "effective"]` field (default `"stored"`).

- **`stored`** — the formula sees `player.stats` (raw stored values only; no equipment bonuses, no passive effects). Safe, simple, and requires no additional recomputation triggers beyond stat mutations.
- **`effective`** — the formula sees `effective_stats(registry)` (stored stats + equipped item modifiers + passive effects). Captures the full character state, including "The Helm of Hardening boosts constitution" scenarios.

**Why this needs a flag rather than always using `effective_stats()`:** derived stat shadows are recomputed after every stored stat mutation via `_recompute_derived_stats()`. If derived formulas used `effective_stats()`, they would also need recomputation whenever equipment changes (equip/unequip) or passive effect conditions change — not just stat mutations. Those recomputation triggers are additional call sites (TUI equip path, engine item-use auto-equip). By making `stat_context: effective` an explicit opt-in, the engine can check whether _any_ derived stat uses `effective` context and conditionally add the equipment recomputation hook. Authors who don't need equipment-aware derived stats pay no cost.

**Equipment recomputation hook:** When content is loaded and one or more derived stats declare `stat_context: effective`, the engine enables recomputation of those stats after equipment changes. The `GameSession` / TUI equip/unequip code paths call `_recompute_derived_stats()` in addition to the post-stat-mutation call sites.

**Rationale:** Forbidding `effective_stats()` entirely prevents the Helm of Hardening → HP scenario, which is a legitimate and common authoring need. Making it always active would silently break content that expected base stats and would add unexpected recomputation overhead. The opt-in field threads the needle: explicit, backward-compatible, and efficient.

---

## Schema Changes

### `StatDefinition` — add `derived` and `stat_context` fields

```python
# Before (oscilla/engine/models/character_config.py)
class StatDefinition(BaseModel):
    name: str
    type: StatType
    default: int | bool | None = None
    description: str = ""
    bounds: StatBounds | None = None

    @model_validator(mode="after")
    def validate_bounds_not_on_bool(self) -> "StatDefinition":
        if self.type == "bool" and self.bounds is not None:
            raise ValueError(f"StatBounds cannot be set on a bool stat (stat name: {self.name!r})")
        return self
```

```python
# After
from typing import Literal

StatContext = Literal["stored", "effective"]

class StatDefinition(BaseModel):
    name: str
    type: StatType
    default: int | bool | None = None
    description: str = ""
    bounds: StatBounds | None = None
    # Template string evaluated on read. If set, this stat is never written directly;
    # effects targeting it are rejected at load time.
    derived: str | None = None
    # Controls which stat dict the derived formula sees:
    #   "stored"    — player.stats (raw stored values, no equipment/passive bonuses)
    #   "effective" — effective_stats(registry) (includes equipment + passive effects)
    # Ignored when derived is None. Default "stored" is backward-compatible.
    stat_context: StatContext = "stored"

    @model_validator(mode="after")
    def validate_bounds_not_on_bool(self) -> "StatDefinition":
        if self.type == "bool" and self.bounds is not None:
            raise ValueError(f"StatBounds cannot be set on a bool stat (stat name: {self.name!r})")
        return self

    @model_validator(mode="after")
    def validate_derived_not_on_bool(self) -> "StatDefinition":
        # Derived formulas always produce int; bool derived stats are not useful.
        if self.type == "bool" and self.derived is not None:
            raise ValueError(f"Derived formula cannot be set on a bool stat (stat name: {self.name!r})")
        return self

    @model_validator(mode="after")
    def validate_derived_has_no_default(self) -> "StatDefinition":
        # Derived stats are never stored, so a default value is meaningless and misleading.
        if self.derived is not None and self.default is not None:
            raise ValueError(
                f"Derived stat {self.name!r} must not declare a default value — "
                "derived stats are never stored and have no initial value."
            )
        return self
```

### `StatThresholdTrigger` — add `fire_mode` field

```python
# Before (oscilla/engine/models/game.py)
class StatThresholdTrigger(BaseModel):
    """A stat threshold that fires a named trigger when crossed upward."""
    stat: str
    threshold: int
    name: str
```

```python
# After
from typing import Literal

StatThresholdFireMode = Literal["each", "highest"]

class StatThresholdTrigger(BaseModel):
    """A stat threshold that fires a named trigger when crossed upward."""
    stat: str
    threshold: int
    name: str
    # Controls how multi-cross firing behaves when multiple thresholds are
    # crossed in a single stat mutation:
    #   "each"    — fire once per threshold crossed (ascending order)
    #   "highest" — fire only the single highest threshold crossed
    # Default: "each" (backward-compatible with existing threshold entries).
    fire_mode: StatThresholdFireMode = "each"
```

---

### `GameSpec` — remove `HpFormula` and `xp_thresholds`

```python
# Before (oscilla/engine/models/game.py)
class HpFormula(BaseModel):
    base_hp: int = Field(ge=1)
    hp_per_level: int = Field(ge=0)

class GameSpec(BaseModel):
    displayName: str
    description: str = ""
    xp_thresholds: List[int] = Field(min_length=1)
    hp_formula: HpFormula
    # ... rest unchanged
```

```python
# After — HpFormula class is deleted entirely
class GameSpec(BaseModel):
    displayName: str
    description: str = ""
    # xp_thresholds and hp_formula are removed.
    # XP thresholds are now declared as on_stat_threshold entries in triggers.
    # HP initialization is done via on_character_create trigger adventures.
    item_labels: List[ItemLabelDef] = []
    # ... rest unchanged
```

### Remove `XpGrantEffect` from adventure models

```python
# Before (oscilla/engine/models/adventure.py)
class XpGrantEffect(BaseModel):
    type: Literal["xp_grant"]
    amount: int | str = Field(description="XP amount or template string resolving to int.")

Effect = Annotated[
    XpGrantEffect | StatChangeEffect | StatSetEffect | ...,
    Field(discriminator="type"),
]
```

```python
# After — XpGrantEffect class and its entry in Effect union are deleted
Effect = Annotated[
    StatChangeEffect | StatSetEffect | ...,  # xp_grant removed
    Field(discriminator="type"),
]
```

---

## CharacterState Changes

The four hardcoded fields are removed. A new `_derived_shadows` dict tracks the last computed value of each derived stat for change detection. This field is ephemeral (never serialized).

```python
# Before — CharacterState (oscilla/engine/character.py), relevant fields
@dataclass
class CharacterState:
    character_id: UUID
    name: str
    character_class: str | None
    level: int
    xp: int
    hp: int
    max_hp: int
    prestige_count: int
    # ...
    stats: Dict[str, int | bool | None] = field(default_factory=dict)
```

```python
# After
@dataclass
class CharacterState:
    character_id: UUID
    name: str
    character_class: str | None
    # level, xp, hp, max_hp removed — authors declare these in character_config.yaml
    prestige_count: int
    current_location: str | None
    # ...
    stats: Dict[str, int | bool | None] = field(default_factory=dict)
    # Shadow values for derived stat change detection. Keyed by stat name.
    # Populated during content load / character creation and updated by
    # _recompute_derived_stats(). Never serialized to or read from DB.
    _derived_shadows: Dict[str, int | None] = field(default_factory=dict)
```

### `new_character()` — remove hp_formula dependency

```python
# Before
@classmethod
def new_character(
    cls,
    name: str,
    game_manifest: "GameManifest",
    character_config: "CharacterConfigManifest",
) -> "CharacterState":
    all_stats = character_config.spec.public_stats + character_config.spec.hidden_stats
    initial_stats: Dict[str, int | bool | None] = {s.name: s.default for s in all_stats}
    base_hp = game_manifest.spec.hp_formula.base_hp
    # ...
    return cls(
        character_id=uuid4(),
        name=name,
        character_class=None,
        level=1,
        xp=0,
        hp=base_hp,
        max_hp=base_hp,
        # ...
        stats=initial_stats,
    )
```

```python
# After
@classmethod
def new_character(
    cls,
    name: str,
    game_manifest: "GameManifest",
    character_config: "CharacterConfigManifest",
) -> "CharacterState":
    all_stats = character_config.spec.public_stats + character_config.spec.hidden_stats
    # Derived stats are not stored; only non-derived stats get initial values.
    initial_stats: Dict[str, int | bool | None] = {
        s.name: s.default for s in all_stats if s.derived is None
    }
    # Initial creation config (name/pronouns) still applies.
    initial_pronouns: PronounSet = DEFAULT_PRONOUN_SET
    creation_cfg = game_manifest.spec.character_creation
    if creation_cfg is not None and creation_cfg.default_pronouns is not None:
        resolved = PRONOUN_SETS.get(creation_cfg.default_pronouns)
        if resolved is not None:
            initial_pronouns = resolved

    return cls(
        character_id=uuid4(),
        name=name,
        character_class=None,
        prestige_count=0,
        pronouns=initial_pronouns,
        current_location=None,
        stats=initial_stats,
    )
```

### Remove `add_xp()`

The entire `add_xp()` method is deleted. There is no replacement — stat progression is managed by `stat_change` + trigger adventures.

### `to_dict()` and `from_dict()` — remove level/xp/hp/max_hp

```python
# Before — to_dict() excerpt
return {
    "character_id": str(self.character_id),
    "prestige_count": self.prestige_count,
    "name": self.name,
    "character_class": self.character_class,
    "level": self.level,
    "xp": self.xp,
    "hp": self.hp,
    "max_hp": self.max_hp,
    # ...
}
```

```python
# After
return {
    "character_id": str(self.character_id),
    "prestige_count": self.prestige_count,
    "name": self.name,
    "character_class": self.character_class,
    # level, xp, hp, max_hp removed — they live in stats dict
    # _derived_shadows is ephemeral and intentionally excluded
    # ...
}
```

---

## Derived Stat Evaluation

### `_recompute_derived_stats()` — new function in `effects.py`

This function is called after every `stat_change` and `stat_set` effect. It evaluates derived stat formulas **in topological order** (computed once at load time and stored in the registry), detects changes against shadow values, and enqueues threshold triggers for any changed derived stats.

```python
async def _recompute_derived_stats(
    player: "CharacterState",
    registry: "ContentRegistry",
    template_engine: "TemplateEngine",
    tui: "TUICallbacks",
) -> None:
    """Re-evaluate all derived stats and fire on_stat_threshold triggers for any that changed.

    Called after every stat_change or stat_set that modifies a stored stat.
    Derived stats are never written directly — their computed values exist only
    in the shadow dict. The shadow dict is compared to the new computed value;
    when they differ, on_stat_threshold entries for that stat are evaluated.

    Multi-cross behavior: if a derived stat's value jumps past multiple threshold
    values in a single recomputation, all crossed thresholds fire in ascending order.
    """
    char_config = registry.character_config
    if char_config is None:
        return
    game = registry.game
    if game is None:
        return

    # derived_eval_order is the topological sort computed at load time by the loader.
    # Stats with no derived dependencies come first; dependents come after.
    derived_stats = registry.derived_eval_order
    if not derived_stats:
        return

    # Build a mutable stats dict seeded from stored stats (or effective stats for
    # stat_context: effective stats). As each derived stat is computed, its value is
    # added so subsequent derived stats can reference it.
    # This is the mechanism that supports derived-from-derived chains.
    #
    # Base dict: start with stored stats. Effective-context stats will call
    # effective_stats() per-stat inside the loop rather than paying the cost up front
    # for all stats — most games will only have a handful of effective-context derived stats.
    working_stats: Dict[str, int | bool | None] = dict(player.stats)
    # Precompute effective stats once if any derived stat needs them, to avoid
    # repeated effective_stats() calls inside the loop.
    effective: Dict[str, int | bool | None] | None = None
    if any(s.stat_context == "effective" for s in derived_stats):
        effective = player.effective_stats(registry=registry)

    for stat_def in derived_stats:
        assert stat_def.derived is not None  # narrowing for type checker
        try:
            # Choose the stat dict for this formula based on stat_context.
            formula_stats = effective if stat_def.stat_context == "effective" and effective is not None else working_stats
            # Merge any already-computed derived values into the formula context
            # so derived-from-derived chains work regardless of stat_context.
            formula_ctx_stats: Dict[str, int | bool | None] = {
                **formula_stats,
                **{k: v for k, v in working_stats.items() if k not in formula_stats},
            }
            ctx = template_engine.build_context_from_stats(stats=formula_ctx_stats, player=player)
            new_value_raw = template_engine.render_raw(
                f"__derived_{stat_def.name}",
                ctx,
            )
            new_value: int | None = int(new_value_raw) if new_value_raw is not None else None
        except Exception:
            logger.exception(
                "Failed to evaluate derived stat %r formula at runtime — skipping.",
                stat_def.name,
            )
            continue

        # Apply bounds clamping to derived values, same as stored stats.
        if new_value is not None and stat_def.bounds is not None:
            lo = stat_def.bounds.min if stat_def.bounds.min is not None else _INT64_MIN
            hi = stat_def.bounds.max if stat_def.bounds.max is not None else _INT64_MAX
            new_value = max(lo, min(hi, new_value))

        old_value = player._derived_shadows.get(stat_def.name)
        player._derived_shadows[stat_def.name] = new_value
        # Add this derived value to working_stats so downstream derived stats can see it.
        working_stats[stat_def.name] = new_value

        if old_value == new_value:
            continue  # No change — nothing to trigger.

        # Fire on_stat_threshold triggers for this derived stat.
        # Multi-cross: collect all thresholds crossed in this transition and fire each.
        await _fire_threshold_triggers(
            stat_name=stat_def.name,
            old_value=old_value if isinstance(old_value, int) else None,
            new_value=new_value if isinstance(new_value, int) else None,
            player=player,
            registry=registry,
        )
```

### `_fire_threshold_triggers()` — new shared helper

```python
async def _fire_threshold_triggers(
    stat_name: str,
    old_value: int | None,
    new_value: int | None,
    player: "CharacterState",
    registry: "ContentRegistry",
) -> None:
    """Enqueue on_stat_threshold triggers for a stat transition.

    Handles two firing modes per entry:
      - "each"    — every threshold crossed in one mutation enqueues separately
                    (sorted ascending so lower thresholds fire first)
      - "highest" — only the single highest crossed threshold enqueues;
                    lower-threshold entries are suppressed

    "each" and "highest" entries operate independently: all "each" entries fire
    first (ascending), then the highest-threshold "highest" entry fires (if any).

    Downward crossings are not supported — only upward crossings fire.
    """
    game = registry.game
    if game is None:
        return

    thresholds = game.spec.triggers.on_stat_threshold
    if not thresholds:
        return

    if old_value is None or new_value is None:
        return

    # Collect all threshold entries for this stat that were crossed upward.
    crossed: List[StatThresholdTrigger] = [
        t for t in thresholds
        if t.stat == stat_name and old_value < t.threshold <= new_value
    ]

    # --- fire_mode: each --- fire every crossed entry in ascending order.
    each_entries = sorted(
        (t for t in crossed if t.fire_mode == "each"),
        key=lambda t: t.threshold,
    )
    for threshold_entry in each_entries:
        if threshold_entry.name in registry.trigger_index:
            player.enqueue_trigger(
                threshold_entry.name,
                max_depth=game.spec.triggers.max_trigger_queue_depth,
            )

    # --- fire_mode: highest --- fire only the single highest crossed entry.
    highest_entries = [t for t in crossed if t.fire_mode == "highest"]
    if highest_entries:
        top = max(highest_entries, key=lambda t: t.threshold)
        if top.name in registry.trigger_index:
            player.enqueue_trigger(
                top.name,
                max_depth=game.spec.triggers.max_trigger_queue_depth,
            )
```

### Integration point in `run_effect()`

After every `StatChangeEffect` and `StatSetEffect` dispatch, call `_recompute_derived_stats()`:

```python
# In run_effect() — after StatChangeEffect case
case StatChangeEffect(stat=stat, amount=amount):
    assert isinstance(amount, int)
    lo, hi = _resolve_stat_bounds(stat, registry)
    current = player.stats.get(stat, 0)
    assert isinstance(current, int) and not isinstance(current, bool)
    new_val = max(lo, min(hi, current + amount))
    if new_val != current + amount:
        await tui.show_text(f"[dim](stat {stat} clamped to bounds)[/dim]")
    player.set_stat(stat, new_val)
    # Re-evaluate derived stats after every stored stat mutation.
    await _recompute_derived_stats(player=player, registry=registry,
                                   template_engine=engine, tui=tui)
    # Also fire on_stat_threshold for the stored stat itself (existing behavior).
    await _fire_threshold_triggers(
        stat_name=stat,
        old_value=current,
        new_value=new_val,
        player=player,
        registry=registry,
    )
```

---

## PlayerContext Changes

```python
# Before (oscilla/engine/templates.py)
@dataclass(frozen=True)
class PlayerContext:
    name: str
    level: int
    prestige_count: int
    hp: int
    max_hp: int
    stats: Dict[str, int | bool | None]
    milestones: PlayerMilestoneView
    pronouns: PlayerPronounView

    @classmethod
    def from_character(cls, char: "CharacterState") -> "PlayerContext":
        return cls(
            name=char.name,
            level=char.level,
            prestige_count=char.prestige_count,
            hp=char.hp,
            max_hp=char.max_hp,
            stats=dict(char.stats),
            milestones=PlayerMilestoneView(_milestones=char.milestones),
            pronouns=PlayerPronounView.from_set(char.pronouns),
        )
```

```python
# After
@dataclass(frozen=True)
class PlayerContext:
    name: str
    prestige_count: int
    # level, hp, max_hp removed — these are now in stats if the game declares them.
    # Templates use player.stats["level"] etc.
    stats: Dict[str, int | bool | None]
    milestones: PlayerMilestoneView
    pronouns: PlayerPronounView

    @classmethod
    def from_character(
        cls,
        char: "CharacterState",
        registry: "ContentRegistry | None" = None,
    ) -> "PlayerContext":
        # Merge stored stats with current derived stat shadow values so templates
        # see derived stats via player.stats["name"] like any other stat.
        merged_stats: Dict[str, int | bool | None] = dict(char.stats)
        merged_stats.update(char._derived_shadows)
        return cls(
            name=char.name,
            prestige_count=char.prestige_count,
            stats=merged_stats,
            milestones=PlayerMilestoneView(_milestones=char.milestones),
            pronouns=PlayerPronounView.from_set(char.pronouns),
        )
```

---

## New Template Functions

All additions go into `SAFE_GLOBALS` in `oscilla/engine/templates.py`.

### Dice pool functions

```python
def _safe_roll_pool(n: int, sides: int) -> List[int]:
    """Roll n dice each with the given number of sides. Returns the individual results.

    Example: roll_pool(3, 6) might return [2, 5, 1] for 3d6.
    Raises ValueError for invalid inputs.
    """
    if not isinstance(n, int) or not isinstance(sides, int):
        raise ValueError("roll_pool() requires int arguments")
    if n < 1:
        raise ValueError(f"roll_pool(): n must be >= 1, got {n}")
    if sides < 2:
        raise ValueError(f"roll_pool(): sides must be >= 2, got {sides}")
    return [random.randint(1, sides) for _ in range(n)]


def _safe_keep_highest(pool: List[int], n: int) -> List[int]:
    """Return the n highest values from pool (sorted descending).

    Example: keep_highest([1, 5, 3, 4], 2) returns [5, 4].
    Used for advantage mechanics (keep_highest(roll_pool(2, 20), 1)).
    """
    if not isinstance(pool, list):
        raise ValueError("keep_highest(): first argument must be a list")
    if not isinstance(n, int) or n < 1:
        raise ValueError(f"keep_highest(): n must be a positive int, got {n!r}")
    if n > len(pool):
        raise ValueError(f"keep_highest(): n={n} exceeds pool length {len(pool)}")
    return sorted(pool, reverse=True)[:n]


def _safe_keep_lowest(pool: List[int], n: int) -> List[int]:
    """Return the n lowest values from pool (sorted ascending).

    Example: keep_lowest([1, 5, 3, 4], 2) returns [1, 3].
    Used for disadvantage mechanics (keep_lowest(roll_pool(2, 20), 1)).
    """
    if not isinstance(pool, list):
        raise ValueError("keep_lowest(): first argument must be a list")
    if not isinstance(n, int) or n < 1:
        raise ValueError(f"keep_lowest(): n must be a positive int, got {n!r}")
    if n > len(pool):
        raise ValueError(f"keep_lowest(): n={n} exceeds pool length {len(pool)}")
    return sorted(pool)[:n]


def _safe_count_successes(pool: List[int], threshold: int) -> int:
    """Count the number of dice in pool that are >= threshold.

    Example: count_successes([3, 5, 2, 6], 5) returns 2.
    Used for pool-based success-counting systems (World of Darkness, Year Zero).
    """
    if not isinstance(pool, list):
        raise ValueError("count_successes(): first argument must be a list")
    if not isinstance(threshold, int):
        raise ValueError("count_successes(): threshold must be an int")
    return sum(1 for die in pool if die >= threshold)


def _safe_explode(pool: List[int], sides: int, on: int | None = None, max_explosions: int = 10) -> List[int]:
    """Re-roll dice that land on the explode value (default: sides) and add new results.

    Each die that lands on the explode value is kept AND an additional die is rolled.
    The new die can also explode, up to max_explosions total extra rolls.

    Example: explode([6, 3, 6], 6) might return [6, 3, 6, 4, 6, 2]
    (the two 6s each generated another roll; the second new roll also exploded).

    Used for Shadowrun, Savage Worlds, and other exploding-dice systems.
    """
    if not isinstance(pool, list):
        raise ValueError("explode(): pool must be a list")
    explode_on = on if on is not None else sides
    if not isinstance(explode_on, int) or explode_on < 1 or explode_on > sides:
        raise ValueError(f"explode(): on value {explode_on!r} must be between 1 and {sides}")
    result = list(pool)
    extra_rolls = 0
    i = 0
    while i < len(result) and extra_rolls < max_explosions:
        if result[i] == explode_on:
            new_die = random.randint(1, sides)
            result.append(new_die)
            extra_rolls += 1
        i += 1
    return result


def _safe_roll_fudge(n: int) -> List[int]:
    """Roll n FATE/Fudge dice. Each die returns -1, 0, or 1 with equal probability.

    Example: roll_fudge(4) might return [-1, 0, 1, 1].
    Sum the result for the final FATE roll: sum(roll_fudge(4)).
    """
    if not isinstance(n, int) or n < 1:
        raise ValueError(f"roll_fudge(): n must be a positive int, got {n!r}")
    return [random.choice([-1, 0, 1]) for _ in range(n)]


def _safe_weighted_roll(options: List[Any], weights: List[int | float]) -> Any:  # noqa: ANN401
    """Return one element from options selected by the given weights.

    Example: weighted_roll(['miss', 'hit', 'crit'], [50, 40, 10])
    Returns 'miss' ~50% of the time, 'hit' ~40%, 'crit' ~10%.

    Unlike choice() which assumes equal probability, this accepts explicit weights.
    """
    if not isinstance(options, list) or not isinstance(weights, list):
        raise ValueError("weighted_roll(): both arguments must be lists")
    if not options:
        raise ValueError("weighted_roll(): options list must not be empty")
    if len(options) != len(weights):
        raise ValueError(
            f"weighted_roll(): options length {len(options)} != weights length {len(weights)}"
        )
    return random.choices(options, weights=weights, k=1)[0]
```

### Die-shorthand aliases

```python
# Ergonomic aliases for common die types. These cover the vast majority of TTRPG use cases.
# Naming convention: d<sides>() — matches universal tabletop shorthand.
def _d4() -> int:    return random.randint(1, 4)
def _d6() -> int:    return random.randint(1, 6)
def _d8() -> int:    return random.randint(1, 8)
def _d10() -> int:   return random.randint(1, 10)
def _d12() -> int:   return random.randint(1, 12)
def _d20() -> int:   return random.randint(1, 20)
def _d100() -> int:  return random.randint(1, 100)
```

### Display and numeric helpers

```python
def _ordinal(n: int) -> str:
    """Return the ordinal string representation of n.

    Examples: ordinal(1) → '1st', ordinal(2) → '2nd', ordinal(13) → '13th'.
    Useful for prestige display: 'Your {{ ordinal(player.prestige_count + 1) }} run'.
    """
    if not isinstance(n, int):
        raise ValueError(f"ordinal(): argument must be an int, got {type(n).__name__}")
    # Special cases for 11th, 12th, 13th (teen numbers always use 'th').
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _signed(n: int | float) -> str:
    """Return n as a signed string: +3, -2, 0.

    Useful for displaying stat changes in narrative: 'You gained {{ signed(amount) }} strength.'
    Unlike the stat_modifier filter (which applies D&D (value-10)//2 math),
    signed() is the general-purpose signed display for any numeric value.
    """
    if not isinstance(n, (int, float)):
        raise ValueError(f"signed(): argument must be numeric, got {type(n).__name__}")
    return f"+{n}" if n > 0 else str(n)


def _stat_mod(value: int) -> int:
    """Return the D&D-style ability score modifier: floor((value - 10) / 2).

    Example: stat_mod(14) → 2, stat_mod(8) → -1, stat_mod(10) → 0.
    Available as a function in addition to the existing | stat_modifier filter,
    for use in formula expressions: roll(1, 20) + stat_mod(player.stats.strength).
    """
    if not isinstance(value, int):
        raise ValueError(f"stat_mod(): argument must be an int, got {type(value).__name__}")
    return (value - 10) // 2
```

### Updated `SAFE_GLOBALS`

```python
SAFE_GLOBALS: Dict[str, Any] = {
    # Existing functions (unchanged)
    "roll": _safe_roll,
    "choice": _safe_choice,
    "random": _safe_random,
    "sample": _safe_sample,
    "now": _now,
    "today": _today,
    "clamp": _clamp,
    "max": max,
    "min": min,
    "round": round,
    "sum": sum,
    "floor": math.floor,
    "ceil": math.ceil,
    "abs": abs,
    "range": range,
    "len": len,
    "int": int,
    "str": str,
    "bool": bool,
    "season": calendar_utils.season,
    "month_name": calendar_utils.month_name,
    "day_name": calendar_utils.day_name,
    "week_number": calendar_utils.week_number,
    "mean": calendar_utils.mean,
    "zodiac_sign": calendar_utils.zodiac_sign,
    "chinese_zodiac": calendar_utils.chinese_zodiac,
    "moon_phase": calendar_utils.moon_phase,
    "SECONDS_PER_MINUTE": SECONDS_PER_MINUTE,
    "SECONDS_PER_HOUR": SECONDS_PER_HOUR,
    "SECONDS_PER_DAY": SECONDS_PER_DAY,
    "SECONDS_PER_WEEK": SECONDS_PER_WEEK,
    # Dice pools (new)
    "roll_pool": _safe_roll_pool,
    "keep_highest": _safe_keep_highest,
    "keep_lowest": _safe_keep_lowest,
    "count_successes": _safe_count_successes,
    "explode": _safe_explode,
    "roll_fudge": _safe_roll_fudge,
    "weighted_roll": _safe_weighted_roll,
    # Die shorthand aliases (new)
    "d4": _d4,
    "d6": _d6,
    "d8": _d8,
    "d10": _d10,
    "d12": _d12,
    "d20": _d20,
    "d100": _d100,
    # Display helpers (new)
    "ordinal": _ordinal,
    "signed": _signed,
    "stat_mod": _stat_mod,
}
```

---

## Loader Validation Changes

### Reject writes to derived stats

The loader must collect all derived stat names from `CharacterConfig` and walk every effect list in every adventure manifest to reject `stat_change` and `stat_set` effects targeting them.

```python
def _validate_no_derived_stat_writes(
    registry: "ContentRegistry",
    warnings: "List[LoadWarning]",
    errors: "List[LoadError]",
) -> None:
    """Reject stat_change and stat_set effects that target a derived stat."""
    char_config = registry.character_config
    if char_config is None:
        return
    all_stats = char_config.spec.public_stats + char_config.spec.hidden_stats
    derived_names: Set[str] = {s.name for s in all_stats if s.derived is not None}
    if not derived_names:
        return

    for adventure_ref, manifest in registry.adventures.items():
        for step in manifest.spec.steps:
            _check_step_for_derived_writes(
                step=step,
                derived_names=derived_names,
                adventure_ref=adventure_ref,
                errors=errors,
            )
```

### Remove `on_level_up` from allowed trigger keys

```python
# Before
allowed_keys: Set[str] = {"on_character_create", "on_level_up"}

# After
allowed_keys: Set[str] = {"on_character_create"}
```

### Validate derived stat formulas at load time

Derived stat formulas are precompiled and mock-rendered during content load, the same as adventure template strings. The mock player context must include all non-derived stats with representative values, plus mock values for all derived stats below the current one in topological order so that derived-from-derived references pass mock render without errors.

### Topological sort for derived stat evaluation order

The loader builds a dependency graph and sorts derived stats so dependencies are evaluated before dependents. The sorted list is stored on `ContentRegistry.derived_eval_order`. Any cycle (including self-reference) is a fatal load error.

```python
def _build_derived_eval_order(
    char_config: "CharacterConfigManifest",
    errors: "List[LoadError]",
) -> List["StatDefinition"]:
    """Topologically sort derived stats so dependencies are evaluated before dependents.

    Uses a DFS-based cycle detection (Tarjan-style). Any cycle (including self-reference)
    is appended to errors and an empty list is returned to halt derived stat processing.
    Non-derived stats are excluded; the result contains only derived stats in safe order.
    """
    all_stats = char_config.spec.public_stats + char_config.spec.hidden_stats
    derived_map: Dict[str, StatDefinition] = {
        s.name: s for s in all_stats if s.derived is not None
    }
    if not derived_map:
        return []

    # Build adjacency: for each derived stat, which other derived stats does it mention?
    def _deps(stat_def: StatDefinition) -> Set[str]:
        assert stat_def.derived is not None
        return {
            name for name in derived_map
            if f'player.stats["{name}"]' in stat_def.derived
            or f"player.stats['{name}']" in stat_def.derived
        }

    sorted_stats: List[StatDefinition] = []
    visited: Set[str] = set()
    in_stack: Set[str] = set()  # tracks the current DFS path for cycle detection

    def visit(name: str) -> bool:
        if name in in_stack:
            errors.append(LoadError(
                f"Circular dependency detected in derived stats involving {name!r}. "
                "Derived stat formulas must not form cycles."
            ))
            return False  # cycle found
        if name in visited:
            return True  # already processed
        in_stack.add(name)
        stat_def = derived_map[name]
        for dep in _deps(stat_def):
            if not visit(dep):
                return False
        in_stack.discard(name)
        visited.add(name)
        sorted_stats.append(stat_def)
        return True

    for name in derived_map:
        if name not in visited:
            if not visit(name):
                return []  # errors already appended; halt

    return sorted_stats
```

---

## Database Migration

A new Alembic migration removes `level`, `xp`, `hp`, `max_hp` from `character_iterations`. These values are already stored in the `stats` JSON column for games that declare them as stats.

```python
# db/versions/<hash>_remove_hardcoded_progression_fields.py
def upgrade() -> None:
    op.drop_column("character_iterations", "level")
    op.drop_column("character_iterations", "xp")
    op.drop_column("character_iterations", "hp")
    op.drop_column("character_iterations", "max_hp")

def downgrade() -> None:
    # Downgrade re-adds the columns as nullable so existing data isn't destroyed.
    # Values are not backfilled — they exist in the stats JSON if the game declared them.
    op.add_column("character_iterations", sa.Column("level", sa.Integer(), nullable=True))
    op.add_column("character_iterations", sa.Column("xp", sa.Integer(), nullable=True))
    op.add_column("character_iterations", sa.Column("hp", sa.Integer(), nullable=True))
    op.add_column("character_iterations", sa.Column("max_hp", sa.Integer(), nullable=True))
```

---

## TUI Changes

The TUI header, status bar, and XP progress display currently hardcode `player.level`, `player.xp`, `player.hp`, `player.max_hp`. After this change, the TUI looks these up from `player.stats` using the stat names declared as `public` in `CharacterConfig`. Stats declared as `hidden` are not shown.

The XP progress bar logic (which reads `xp_thresholds`) is removed. The specific visual treatment for level/XP progress is deferred to the Full TUI Upgrade roadmap item. The TUI header shows public stats as a flat list of `<name>: <value>` pairs.

---

## Edge Cases

| Case                                                              | Handling                                                                                                                                                                     |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `stat_change` targeting a derived stat                            | Load error with clear message identifying the adventure and stat name                                                                                                        |
| Derived stat formula throws at runtime                            | Log exception, skip re-evaluation for that stat, continue processing                                                                                                         |
| Derived stat formula produces non-int output                      | Log error, skip shadow update for that stat                                                                                                                                  |
| Multi-cross: derived stat jumps 3 levels                          | All 3 threshold entries fire in ascending threshold order                                                                                                                    |
| `on_stat_threshold` entry referencing a derived stat              | Allowed — loader validates the stat exists but does not distinguish stored vs derived                                                                                        |
| Game declares no `level` or `xp` stat                             | Fully supported — `player.stats["level"]` would fail at template render time but only if a template references it. Authors who don't use levels simply don't reference them. |
| `on_character_create` adventure missing in a game with no hp stat | No error — there is no required stat. Authors who want HP declare it and wire it up.                                                                                         |
| Derived shadow dict empty on newly loaded character               | Initial shadow populate pass runs in `_recompute_derived_stats()` after `on_character_create` effects fire                                                                   |

---

## Migration Plan

1. Create the Alembic migration (remove 4 columns).
2. Update `CharacterState`, `new_character()`, `to_dict()`, `from_dict()`.
3. Update `GameSpec` (remove `HpFormula`, `xp_thresholds`).
4. Remove `XpGrantEffect` from adventure models and effect dispatch.
5. Add `derived` field to `StatDefinition`; add loader validators.
6. Add `_recompute_derived_stats()` and `_fire_threshold_triggers()` to `effects.py`.
7. Update `PlayerContext` (remove `level`, `hp`, `max_hp`).
8. Add new `SAFE_GLOBALS` functions in `templates.py`.
9. Update loader: remove `on_level_up`, add derived stat write validation.
10. Update TUI to read stats from `public_stats` list instead of hardcoded fields.
11. Rebuild testlandia `character_config.yaml` and `game.yaml`.
12. Update all tests; verify full test suite passes.
13. Run `make chores` to confirm formatting compliance.

**Rollback:** The Alembic downgrade migration adds the columns back as nullable. All application code changes are in a single PR; reverting the PR restores prior behavior. No data is lost because any game that had `level` etc. as meaningful values will have them in the `stats` JSON column going forward.

---

## Testing Philosophy

Tests are split into three tiers:

### Tier 1: Unit — derived stat evaluation

No YAML loading, no registry. Construct `CharacterState`, `CharacterConfigManifest`, and `TemplateEngine` directly in Python.

```python
# tests/engine/test_derived_stats.py

from oscilla.engine.character import CharacterState
from oscilla.engine.models.character_config import (
    CharacterConfigManifest, CharacterConfigSpec, StatDefinition
)
from oscilla.engine.steps.effects import _recompute_derived_stats

# Fixture: minimal character with a stored stat and one derived stat
def _make_char_with_derived() -> tuple[CharacterState, CharacterConfigManifest]:
    char = CharacterState(
        character_id=uuid4(),
        name="Test",
        character_class=None,
        prestige_count=0,
        current_location=None,
        stats={"constitution": 14},
    )
    config = CharacterConfigManifest(
        apiVersion="oscilla/v1",
        kind="CharacterConfig",
        metadata={"name": "test-config"},
        spec=CharacterConfigSpec(
            public_stats=[
                StatDefinition(name="constitution", type="int", default=10),
                StatDefinition(
                    name="constitution_bonus",
                    type="int",
                    derived='{{ floor((player.stats["constitution"] - 10) / 2) }}',
                ),
            ]
        ),
    )
    return char, config


async def test_derived_stat_initial_computation():
    char, config = _make_char_with_derived()
    # Before recompute, shadow is empty
    assert "constitution_bonus" not in char._derived_shadows
    # After recompute, shadow has the computed value
    await _recompute_derived_stats(char, mock_registry(config), mock_template_engine(), mock_tui())
    assert char._derived_shadows["constitution_bonus"] == 2  # (14-10)//2


async def test_derived_stat_updates_on_stored_stat_change():
    char, config = _make_char_with_derived()
    char.stats["constitution"] = 18
    await _recompute_derived_stats(char, mock_registry(config), mock_template_engine(), mock_tui())
    assert char._derived_shadows["constitution_bonus"] == 4  # (18-10)//2


async def test_derived_stat_not_in_stored_stats():
    char, config = _make_char_with_derived()
    # Derived stat must NOT appear in char.stats
    assert "constitution_bonus" not in char.stats
```

### Tier 2: Integration — multi-cross threshold detection

Uses fixture-based content loading with minimal manifests (no reference to `content/testlandia/`).

```python
# tests/engine/test_stat_threshold_multicross.py
# Fixture: tests/fixtures/content/multicross/
# Contains: game.yaml with on_stat_threshold for xp at 100, 300, 600
#           character_config.yaml with xp and level stats

async def test_three_thresholds_crossed_in_one_stat_change(loaded_multicross_registry):
    char = CharacterState.new_character("Hero", loaded_multicross_registry.game, loaded_multicross_registry.character_config)
    char.stats["xp"] = 0
    # Simulate a large xp gain that crosses all three thresholds at once
    char.stats["xp"] = 700
    await _fire_threshold_triggers("xp", old_value=0, new_value=700, player=char, registry=loaded_multicross_registry)
    # Should enqueue 3 triggers (one per threshold: 100, 300, 600)
    assert len(char.pending_triggers) == 3
    # Triggers should be enqueued in threshold-ascending order
    assert char.pending_triggers == ["level-2-trigger", "level-3-trigger", "level-4-trigger"]
```

### Tier 3: Load-time validation — derived stat write rejection

```python
# tests/engine/test_derived_stat_validation.py

async def test_stat_change_targeting_derived_stat_is_load_error(bad_adventure_fixture_path):
    """Adventure with stat_change targeting a derived stat must fail load."""
    from oscilla.engine.loader import load
    with pytest.raises(ContentLoadError, match="derived stat"):
        await load(bad_adventure_fixture_path)

async def test_circular_derived_reference_is_load_error(circular_derived_fixture_path):
    with pytest.raises(ContentLoadError, match="references derived stat"):
        await load(circular_derived_fixture_path)
```

### Tier 3: Unit — new template functions

```python
# tests/engine/test_template_functions.py

def test_roll_pool_returns_correct_count():
    result = _safe_roll_pool(4, 6)
    assert len(result) == 4
    assert all(1 <= v <= 6 for v in result)

def test_keep_highest_returns_n_largest():
    assert _safe_keep_highest([1, 5, 3, 4], 2) == [5, 4]

def test_keep_lowest_returns_n_smallest():
    assert _safe_keep_lowest([1, 5, 3, 4], 2) == [1, 3]

def test_count_successes():
    assert _safe_count_successes([3, 5, 2, 6], 5) == 2

def test_ordinal_handles_teens():
    assert _ordinal(11) == "11th"
    assert _ordinal(12) == "12th"
    assert _ordinal(13) == "13th"
    assert _ordinal(21) == "21st"

def test_signed():
    assert _signed(3) == "+3"
    assert _signed(-2) == "-2"
    assert _signed(0) == "0"

def test_stat_mod():
    assert _stat_mod(10) == 0
    assert _stat_mod(14) == 2
    assert _stat_mod(8) == -1
```

---

## Documentation Plan

| Document                                | Audience          | Topics to Cover                                                                                                                                                                                                                                                          |
| --------------------------------------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/authors/game-configuration.md`    | Content authors   | Remove `hp_formula` and `xp_thresholds` docs; add `on_stat_threshold` examples for XP-based level advancement; show derived stat pattern in `character_config.yaml`; show `on_character_create` for HP initialization                                                    |
| `docs/authors/conditions.md`            | Content authors   | Note that `player.level`, `player.hp`, `player.max_hp` are now `player.stats["level"]` etc.; update all condition examples that reference these                                                                                                                          |
| `docs/authors/effects.md` (new section) | Content authors   | Document removal of `xp_grant`; document `stat_change` as the replacement; full authoring example of an XP stat + level derived stat + threshold trigger                                                                                                                 |
| `docs/authors/skills.md`                | Content authors   | Update any examples using `player.level` in skill formulas                                                                                                                                                                                                               |
| `docs/authors/templates.md`             | Content authors   | Add full reference table for all new functions: `roll_pool`, `keep_highest`, `keep_lowest`, `count_successes`, `explode`, `roll_fudge`, `weighted_roll`, `d4`–`d100`, `ordinal`, `signed`, `stat_mod`; add example showing D20-style HP gain on level-up using roll_pool |
| `docs/dev/game-engine.md`               | Engine developers | Update architecture diagram to remove level/xp/hp/max_hp as special fields; document derived stat shadow mechanism; document `_recompute_derived_stats()` and `_fire_threshold_triggers()` call points                                                                   |

---

## Testlandia Integration

All testlandia files are in `content/testlandia/`.

### `character_config.yaml` (update)

Declare `xp`, `level` (derived), `hp`, `max_hp`, `constitution`, and `constitution_bonus` (derived):

```yaml
spec:
  public_stats:
    - name: hp
      type: int
      default: 0
      bounds:
        min: 0
      description: "Current hit points."
    - name: max_hp
      type: int
      default: 0
      description: "Maximum hit points."
    - name: constitution
      type: int
      default: 10
      description: "Constitution score. Affects HP gains."
    - name: constitution_bonus
      type: int
      derived: '{{ floor((player.stats["constitution"] - 10) / 2) }}'
      description: "D&D-style constitution modifier, derived from constitution score."
    - name: xp
      type: int
      default: 0
      bounds:
        min: 0
      description: "Experience points accumulated."
    - name: level
      type: int
      derived: '{{ 1 + sum([1 for t in [100, 300, 600, 1000, 1500] if player.stats["xp"] >= t]) }}'
      description: "Current level, derived from XP thresholds."
```

### `game.yaml` (update)

Remove `hp_formula` and `xp_thresholds`. Add `on_stat_threshold` entries for XP thresholds and wire trigger adventures:

```yaml
triggers:
  on_stat_threshold:
    - stat: xp
      threshold: 100
      name: level-2-reached
    - stat: xp
      threshold: 300
      name: level-3-reached
    - stat: xp
      threshold: 600
      name: level-4-reached
    - stat: xp
      threshold: 1000
      name: level-5-reached
    - stat: xp
      threshold: 1500
      name: level-6-reached

trigger_adventures:
  on_character_create:
    - testlandia-character-creation
  level-2-reached:
    - testlandia-level-up
  level-3-reached:
    - testlandia-level-up
  level-4-reached:
    - testlandia-level-up
  level-5-reached:
    - testlandia-level-up
  level-6-reached:
    - testlandia-level-up
```

### New adventure: `testlandia-character-creation` (update existing or create)

Sets initial `hp` and `max_hp`:

```yaml
steps:
  - type: effects
    effects:
      - type: stat_set
        stat: hp
        value: 10
      - type: stat_set
        stat: max_hp
        value: 10
```

### New adventure: `testlandia-level-up`

Uses `roll_pool`, `keep_highest`, `d8()` and displays results — this is the primary QA target for the dice pool functions:

```yaml
steps:
  - type: narrative
    text: |
      You have reached level {{ player.stats["level"] }}!

      {% set roll_results = roll_pool(1, 8) %}
      {% set hp_gain = roll_results[0] + player.stats["constitution_bonus"] %}
      You rolled {{ roll_results[0] }} on your Hit Die (d8) and gain
      {{ signed(hp_gain) }} max HP ({{ hp_gain }} = {{ roll_results[0] }}
      + {{ signed(player.stats["constitution_bonus"]) }} constitution bonus).

      You are now at {{ player.stats["hp"] }}/{{ player.stats["max_hp"] + hp_gain }} HP.

    effects:
      - type: stat_change
        stat: max_hp
        amount: "{{ roll_pool(1, 8)[0] + player.stats['constitution_bonus'] }}"
      - type: stat_change
        stat: hp
        amount: "{{ roll_pool(1, 8)[0] + player.stats['constitution_bonus'] }}"
```

### New adventure: `testlandia-stat-formula-showcase`

Demonstrates all new template functions with visible output for manual QA:

```yaml
steps:
  - type: narrative
    text: |
      === Dice Pool Showcase ===

      3d6 pool: {{ roll_pool(3, 6) }}
      4d6 keep highest 3: {{ keep_highest(roll_pool(4, 6), 3) }}
      D20 advantage: {{ keep_highest(roll_pool(2, 20), 1)[0] }}
      Successes (threshold 5) on 5d6: {{ count_successes(roll_pool(5, 6), 5) }}
      FATE dice (4dF): {{ roll_fudge(4) }} → sum: {{ sum(roll_fudge(4)) }}
      Weighted roll (miss/hit/crit 50/40/10): {{ weighted_roll(['miss','hit','crit'], [50, 40, 10]) }}

      === Die Aliases ===
      d4={{ d4() }}, d6={{ d6() }}, d8={{ d8() }}, d10={{ d10() }},
      d12={{ d12() }}, d20={{ d20() }}, d100={{ d100() }}

      === Display Helpers ===
      ordinal(1)={{ ordinal(1) }}, ordinal(2)={{ ordinal(2) }}, ordinal(13)={{ ordinal(13) }}
      signed(+5)={{ signed(5) }}, signed(-3)={{ signed(-3) }}, signed(0)={{ signed(0) }}
      stat_mod(15)={{ stat_mod(15) }}, stat_mod(8)={{ stat_mod(8) }}

      === Your Stats ===
      Level: {{ player.stats["level"] }} (derived from {{ player.stats["xp"] }} XP)
      Constitution: {{ player.stats["constitution"] }} → bonus {{ signed(player.stats["constitution_bonus"]) }}
      HP: {{ player.stats["hp"] }}/{{ player.stats["max_hp"] }}
      This is your {{ ordinal(player.prestige_count + 1) }} run.
```

This adventure is available from any location in testlandia and covers every new function in one play-through.

---

## Open Questions

None — all design decisions have been resolved in the exploration session preceding this document.
