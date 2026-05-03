# Design: Custom Effects

## Context

Content packages frequently repeat the same effect sequences across multiple manifests. A "heal to 50%" pattern might appear in five different items, three skills, and two archetypes — each with the same template expression, the same `stat_change` effect, and the same boilerplate. When the healing logic changes, every copy must be found and updated.

The Custom Conditions system (`kind: CustomCondition`, `type: custom` condition leaf) already solved this problem for condition trees. Effects need the same macro layer: name a sequence of effects once, parameterize it, reference it by name.

The engine's effect system has two layers:

- **Model layer** (`oscilla/engine/models/adventure.py`) — the `Effect` discriminated union of 21 effect types
- **Dispatch layer** (`oscilla/engine/steps/effects.py`) — `run_effect()` with template resolution and a `match` statement routing to handlers

Template expressions in effect fields (like `StatChangeEffect.amount`) are resolved via `ExpressionContext` which currently exposes: `player`, `combat`, `game`, `ingame_time`, `this`. A new `params` field on that context is the natural injection point for custom effect parameters.

The change surface mirrors Custom Conditions:

```
oscilla/engine/models/custom_effect.py    ← new: CustomEffectParameter, CustomEffectSpec, CustomEffectManifest
oscilla/engine/models/base.py             ← add CustomEffectRef to Effect union
oscilla/engine/models/__init__.py         ← register CustomEffectManifest
oscilla/engine/registry.py                ← add custom_effects KindRegistry
oscilla/engine/steps/effects.py           ← add CustomEffectRef case arm to run_effect()
oscilla/engine/templates.py               ← ExpressionContext gains params field
oscilla/engine/loader.py                  ← dangling-ref, cycle, param validation
```

---

## Goals / Non-Goals

**Goals:**

- Allow authors to declare a named, parameterized effect body in a `kind: CustomEffect` manifest.
- Allow any manifest field that accepts an `Effect` to reference a `CustomEffect` by name via `type: custom` with a `params:` dict.
- Custom effects can compose custom effects (a body may contain `type: custom` effects).
- Parameter schema with typed parameters (`int`, `float`, `str`, `bool`) and optional defaults.
- Call-site `params:` dict merges with manifest defaults (call-site overrides defaults).
- `params` variable available in template expressions within body effects (e.g., `{{ params.percent / 100 * player.stats['max_hp'] }}`).
- Load-time validation: dangling refs, circular chains, unknown parameters, type mismatches — all raise `ContentLoadError`.
- Opt-in: content packages with no `CustomEffect` manifests experience zero behavior change.

**Non-Goals:**

- Cross-package `CustomEffect` references (names are scoped to the content package).
- Template expressions in `params:` values — params are literal scalar values only. Authors needing derived values should declare an intermediate parameter.
- `CustomEffect` in passive effects (`PassiveEffect` in `game.yaml`) — passive effects use `PassiveStatChange` / `PassiveSkillGrant` which are not typed as `Effect`. This can be a future extension.
- Any UI surface for browsing or visualizing `CustomEffect` manifests.

---

## Decisions

### D1: `CustomEffectRef` in the `Effect` union, not a separate type

The `Effect` discriminated union in `adventure.py` is the single type used everywhere effects appear. Adding `CustomEffectRef` as another arm means it works in all existing effect-accepting fields: `OutcomeBranch.effects`, `SkillSpec.use_effects`, `ItemSpec.use_effects`, `ArchetypeSpec.gain_effects`/`lose_effects`, `BuffSpec.per_turn_effects`, `AdventureSpec.steps[*].effects`.

**Decision:** `CustomEffectRef` is a new arm in the `Effect` union with `type: Literal["custom_effect"]`. The discriminator value is `"custom_effect"` (not `"custom"`) to avoid collision with `CustomConditionRef.type` which is `"custom"` — the two unions (`Condition` vs `Effect`) are distinct but using different discriminator values prevents any ambiguity if they ever appear in the same YAML document during parsing.

```python
class CustomEffectRef(BaseModel):
    """Reference to a named CustomEffect manifest declared in the same content package.

    Resolved at evaluation time against registry.custom_effects.
    Validated at load time: dangling references, circular dependency chains,
    unknown parameters, and type mismatches all raise ContentLoadError.
    """

    type: Literal["custom_effect"]
    name: str = Field(description="CustomEffect manifest name to invoke.")
    params: Dict[str, int | float | str | bool] = Field(
        default_factory=dict,
        description="Per-call parameter overrides. Merged on top of the CustomEffect's declared defaults.",
    )
```

### D2: `CustomEffect` manifest with typed parameter schema

The parameter schema follows the `BuffSpec.variables` pattern: named parameters with declared types and optional defaults. At load time, the schema is used to validate call-site `params:` dicts. At runtime, defaults are merged with overrides.

```python
class CustomEffectParameter(BaseModel):
    """A typed parameter for a CustomEffect manifest."""

    name: str = Field(description="Parameter name, used as key in params dict and 'params' template variable.")
    type: Literal["int", "float", "str", "bool"] = Field(description="Parameter type for validation.")
    default: int | float | str | bool | None = Field(
        default=None,
        description="Default value. If None, the caller must supply this parameter.",
    )


class CustomEffectSpec(BaseSpec):
    """Spec block for a CustomEffect manifest.

    Custom effects are named, parameterized sequences of standard effects.
    Authors declare a parameter schema and an effect body. At call sites,
    `type: custom_effect` references the manifest by name and supplies
    per-call parameter overrides.
    """

    displayName: str | None = None
    description: str = ""
    parameters: List[CustomEffectParameter] = Field(
        default_factory=list,
        description="Typed parameter schema for this custom effect.",
    )
    effects: List[Effect] = Field(
        min_length=1,
        description="Effect body. Standard effects and nested custom effects are both allowed.",
    )

    @model_validator(mode="after")
    def validate_unique_param_names(self) -> "CustomEffectSpec":
        names = [p.name for p in self.parameters]
        if len(names) != len(set(names)):
            dupes = {n for n in names if names.count(n) > 1}
            raise ValueError(f"CustomEffect parameters must have unique names, duplicates: {dupes}")
        return self


class CustomEffectManifest(ManifestEnvelope):
    kind: Literal["CustomEffect"]
    spec: CustomEffectSpec
```

The `CustomEffectSpec` inherits from `BaseSpec` (like all spec models after the inheritance change), giving it the `properties` field. This is forward-compatible but not actively used — `params` is the parameterization mechanism, not `properties`.

### D3: `params` as a new field on `ExpressionContext`

`ExpressionContext` already has `this` for manifest-level properties (from the inheritance system). `params` serves the same role but is scoped to custom effect call sites. Both are `Dict[str, int | float | str | bool]`.

**Before (`oscilla/engine/templates.py`):**

```python
@dataclass
class ExpressionContext:
    player: PlayerContext
    combat: CombatContextView | None = None
    game: GameContext = field(default_factory=GameContext)
    ingame_time: "InGameTimeView | None" = None
    this: Dict[str, int | float | str | bool] = field(default_factory=dict)
```

**After:**

```python
@dataclass
class ExpressionContext:
    player: PlayerContext
    combat: CombatContextView | None = None
    game: GameContext = field(default_factory=GameContext)
    ingame_time: "InGameTimeView | None" = None
    # Properties from the current manifest (adventure, item, etc.). Empty when not applicable.
    this: Dict[str, int | float | str | bool] = field(default_factory=dict)
    # Parameters from the current CustomEffect call site. Empty when not in a custom effect body.
    params: Dict[str, int | float | str | bool] = field(default_factory=dict)
```

The `GameTemplateEngine.render()` method gains one line to expose `params` in the Jinja2 render context:

**Before (`oscilla/engine/templates.py` — `GameTemplateEngine.render()`):**

```python
render_ctx["player"] = ctx.player
render_ctx["combat"] = ctx.combat
render_ctx["game"] = ctx.game
render_ctx["this"] = ctx.this
```

**After:**

```python
render_ctx["player"] = ctx.player
render_ctx["combat"] = ctx.combat
render_ctx["game"] = ctx.game
render_ctx["this"] = ctx.this
render_ctx["params"] = ctx.params
```

### D4: Runtime resolution in `run_effect()` — merge defaults, inject params, recurse

The `CustomEffectRef` case arm in `run_effect()` does three things:

1. Looks up the `CustomEffect` manifest in the registry
2. Merges manifest parameter defaults with call-site overrides
3. Injects `params` into `ExpressionContext` and iterates body effects

**New code added to `oscilla/engine/steps/effects.py` (after the `SkillRevokeEffect` case, before the final closing of the `match`):**

```python
        case CustomEffectRef(name=ce_name, params=call_params):
            ce_manifest = registry.custom_effects.get(ce_name)
            if ce_manifest is None:
                logger.error("custom_effect: %r not found in registry — skipping.", ce_name)
                await tui.show_text(f"[red]Error: custom effect {ce_name!r} not found.[/red]")
                return

            # Build merged params: manifest defaults overridden by call-site values.
            defaults: Dict[str, int | float | str | bool] = {
                p.name: p.default for p in ce_manifest.spec.parameters if p.default is not None
            }
            merged_params: Dict[str, int | float | str | bool] = {**defaults, **call_params}

            # Inject params into the ExpressionContext for body effect template resolution.
            if ctx is None:
                game_spec = registry.game.spec if registry.game is not None else None
                hemisphere = game_spec.season_hemisphere if game_spec is not None else "northern"
                timezone = game_spec.timezone if game_spec is not None else None
                combat_view: CombatContextView | None = None
                if combat is not None:
                    enemy_ref = getattr(combat, "enemy_ref", "")
                    enemy_manifest = registry.enemies.get(enemy_ref)
                    enemy_name = enemy_manifest.spec.displayName if enemy_manifest is not None else enemy_ref
                    combat_view = CombatContextView(
                        enemy_stats=dict(combat.enemy_stats),
                        enemy_name=enemy_name,
                        turn=combat.turn_number,
                        combat_stats=dict(combat.combat_stats),
                    )
                ctx = ExpressionContext(
                    player=PlayerContext.from_character(player),
                    game=GameContext(season_hemisphere=hemisphere, timezone=timezone),
                    combat=combat_view,
                    params=merged_params,
                )
            else:
                # Copy the context with params injected, preserving all other fields.
                ctx = ExpressionContext(
                    player=ctx.player,
                    combat=ctx.combat,
                    game=ctx.game,
                    ingame_time=ctx.ingame_time,
                    this=ctx.this,
                    params=merged_params,
                )

            # Execute each effect in the body sequentially.
            for body_effect in ce_manifest.spec.effects:
                await run_effect(
                    effect=body_effect,
                    player=player,
                    registry=registry,
                    tui=tui,
                    combat=combat,
                    ctx=ctx,
                )
```

Key design choice: `ctx` is copied with `params` injected, preserving `this`, `player`, `combat`, etc. This means nested custom effects each get their own `params` frame while inheriting the outer context. If body effect A modifies player state, body effect B sees the modified state — this is the expected sequential semantics.

### D5: Load-time validation — three passes, mirroring CustomConditions

A new `_validate_custom_effect_refs()` function in `loader.py` runs three validation passes:

1. **Dangling reference check** — every `CustomEffectRef.name` must resolve to a registered `CustomEffect`
2. **Circular reference detection** — DFS over the `CustomEffect` dependency graph (same algorithm as `_validate_custom_condition_refs`)
3. **Parameter validation** — for every `CustomEffectRef.params`, check that each key is declared in the target's parameter schema, and that the value's Python type matches the declared type

**New helper functions in `oscilla/engine/loader.py`:**

```python
def _collect_custom_effect_refs_in_effect(effect: Effect) -> List[Tuple[str, Dict[str, Any]]]:
    """Recursively collect all CustomEffectRef (name, params) pairs from an effect tree.

    Returns list of (name, params) tuples. Handles nested effects inside
    OutcomeBranch, step effects, etc.
    """
    from oscilla.engine.models.adventure import CustomEffectRef

    results: List[Tuple[str, Dict[str, Any]]] = []
    if isinstance(effect, CustomEffectRef):
        results.append((effect.name, dict(effect.params)))
    return results


def _collect_custom_effect_refs_from_effects(effects: List[Effect]) -> List[Tuple[str, Dict[str, Any]]]:
    """Collect all CustomEffectRef (name, params) pairs from a list of effects."""
    results: List[Tuple[str, Dict[str, Any]]] = []
    for effect in effects:
        results.extend(_collect_custom_effect_refs_in_effect(effect))
    return results


def _collect_custom_effect_refs_from_manifest(m: ManifestEnvelope) -> List[Tuple[str, Dict[str, Any]]]:
    """Collect all CustomEffectRef (name, params) pairs from a manifest's effect fields."""
    from oscilla.engine.models.adventure import (
        AdventureManifest,
        ChoiceStep,
        CombatStep,
        NarrativeStep,
        PassiveStep,
        StatCheckStep,
    )
    from oscilla.engine.models.archetype import ArchetypeManifest
    from oscilla.engine.models.buff import BuffManifest
    from oscilla.engine.models.custom_effect import CustomEffectManifest
    from oscilla.engine.models.item import ItemManifest
    from oscilla.engine.models.skill import SkillManifest

    results: List[Tuple[str, Dict[str, Any]]] = []

    def _add(effects: List[Effect]) -> None:
        results.extend(_collect_custom_effect_refs_from_effects(effects))

    match m.kind:
        case "CustomEffect":
            ce = cast(CustomEffectManifest, m)
            _add(ce.spec.effects)
        case "Adventure":
            adv = cast(AdventureManifest, m)
            for step in adv.spec.steps:
                match step:
                    case NarrativeStep(effects=effects):
                        _add(effects)
                    case ChoiceStep():
                        _add(step.effects)
                        for opt in step.options:
                            _add(opt.effects)
                    case PassiveStep(effects=effects):
                        _add(effects)
                    case StatCheckStep():
                        _add(step.on_pass)
                        _add(step.on_fail)
                    case CombatStep():
                        _add(step.effects)
        case "Item":
            item = cast(ItemManifest, m)
            _add(item.spec.use_effects)
        case "Skill":
            skill = cast(SkillManifest, m)
            _add(skill.spec.use_effects)
        case "Archetype":
            arch = cast(ArchetypeManifest, m)
            _add(arch.spec.gain_effects)
            _add(arch.spec.lose_effects)
        case "Buff":
            buff = cast(BuffManifest, m)
            _add(buff.spec.per_turn_effects)
        case _:
            pass

    return results
```

```python
def _validate_custom_effect_refs(manifests: List[ManifestEnvelope]) -> List[LoadError]:
    """Validate all CustomEffectRef usages across manifests.

    Three checks:
    1. Every referenced name must exist as a declared CustomEffect manifest.
    2. No CustomEffect body may form a circular reference chain.
    3. All call-site params must be declared in the target's parameter schema
       and must match the declared type.
    """
    errors: List[LoadError] = []

    from oscilla.engine.models.custom_effect import CustomEffectManifest

    known_names: Set[str] = {m.metadata.name for m in manifests if m.kind == "CustomEffect"}

    # Build name → manifest map for parameter validation.
    ce_map: Dict[str, CustomEffectManifest] = {
        m.metadata.name: cast(CustomEffectManifest, m)
        for m in manifests
        if m.kind == "CustomEffect"
    }

    # --- Pass 1: dangling reference check ---
    for m in manifests:
        refs = _collect_custom_effect_refs_from_manifest(m)
        for ref_name, _ in refs:
            if ref_name not in known_names:
                errors.append(
                    LoadError(
                        file=Path(f"<{m.metadata.name}>"),
                        message=f"type: custom_effect references unknown CustomEffect: {ref_name!r}",
                    )
                )

    # --- Pass 2: circular reference detection (DFS over CustomEffect bodies) ---
    # Build adjacency: name → set of CustomEffectRef names in its body.
    adjacency: Dict[str, Set[str]] = {}
    for m in manifests:
        if m.kind == "CustomEffect":
            ce = cast(CustomEffectManifest, m)
            body_refs = _collect_custom_effect_refs_from_effects(ce.spec.effects)
            # Only names that are themselves declared CustomEffects form edges.
            adjacency[m.metadata.name] = {ref_name for ref_name, _ in body_refs if ref_name in known_names}

    visited: Set[str] = set()
    in_stack: Set[str] = set()

    def _dfs(node: str, path: List[str]) -> None:
        in_stack.add(node)
        for neighbour in sorted(adjacency.get(node, set())):
            if neighbour in in_stack:
                cycle_start = path.index(neighbour)
                cycle_path = " \u2192 ".join(path[cycle_start:] + [neighbour])
                errors.append(
                    LoadError(
                        file=Path(f"<{node}>"),
                        message=f"circular reference in CustomEffect {node!r}: {cycle_path}",
                    )
                )
            elif neighbour not in visited:
                _dfs(neighbour, path + [neighbour])
        in_stack.discard(node)
        visited.add(node)

    for name in sorted(adjacency):
        if name not in visited:
            _dfs(name, [name])

    # --- Pass 3: parameter validation (unknown keys + type mismatch) ---
    type_map: Dict[str, type] = {
        "int": int,
        "float": (int, float),  # int is acceptable where float is declared
        "str": str,
        "bool": bool,
    }

    for m in manifests:
        refs = _collect_custom_effect_refs_from_manifest(m)
        for ref_name, call_params in refs:
            if ref_name not in ce_map:
                continue  # Already reported as dangling in pass 1.
            target = ce_map[ref_name]
            param_schema: Dict[str, str] = {p.name: p.type for p in target.spec.parameters}
            for param_name, param_value in call_params.items():
                if param_name not in param_schema:
                    errors.append(
                        LoadError(
                            file=Path(f"<{m.metadata.name}>"),
                            message=(
                                f"custom_effect {ref_name!r} called from {m.kind} {m.metadata.name!r}: "
                                f"unknown parameter {param_name!r} "
                                f"(declared: {list(param_schema.keys())})"
                            ),
                        )
                    )
                else:
                    expected_type_name = param_schema[param_name]
                    expected_types = type_map[expected_type_name]
                    # bool is a subclass of int in Python; explicit check to prevent
                    # bool values from being accepted as int.
                    if expected_type_name == "int" and isinstance(param_value, bool):
                        errors.append(
                            LoadError(
                                file=Path(f"<{m.metadata.name}>"),
                                message=(
                                    f"custom_effect {ref_name!r} called from {m.kind} {m.metadata.name!r}: "
                                    f"parameter {param_name!r} expects {expected_type_name}, got bool"
                                ),
                            )
                        )
                    elif not isinstance(param_value, expected_types):
                        errors.append(
                            LoadError(
                                file=Path(f"<{m.metadata.name}>"),
                                message=(
                                    f"custom_effect {ref_name!r} called from {m.kind} {m.metadata.name!r}: "
                                    f"parameter {param_name!r} expects {expected_type_name}, "
                                    f"got {type(param_value).__name__}"
                                ),
                            )
                        )

    return errors
```

The validator is called from `validate_references()` in the loader pipeline, alongside `_validate_custom_condition_refs()`.

### D6: Registry and manifest registration

**`oscilla/engine/registry.py` — add `custom_effects` field and registration arm:**

**Before (`ContentRegistry.__init__`):**

```python
self.custom_conditions: KindRegistry[CustomConditionManifest] = KindRegistry()
self.combat_systems: KindRegistry[CombatSystemManifest] = KindRegistry()
```

**After:**

```python
self.custom_conditions: KindRegistry[CustomConditionManifest] = KindRegistry()
self.custom_effects: KindRegistry[CustomEffectManifest] = KindRegistry()
self.combat_systems: KindRegistry[CombatSystemManifest] = KindRegistry()
```

**Before (`ContentRegistry.build()`):**

```python
case "CustomCondition":
    registry.custom_conditions.register(cast(CustomConditionManifest, m))
case "CombatSystem":
```

**After:**

```python
case "CustomCondition":
    registry.custom_conditions.register(cast(CustomConditionManifest, m))
case "CustomEffect":
    registry.custom_effects.register(cast(CustomEffectManifest, m))
case "CombatSystem":
```

### D7: `Effect` union update in `adventure.py`

**Before:**

```python
Effect = Annotated[
    Union[
        ItemDropEffect,
        MilestoneGrantEffect,
        EndAdventureEffect,
        HealEffect,
        StatChangeEffect,
        StatSetEffect,
        UseItemEffect,
        SkillGrantEffect,
        DispelEffect,
        ApplyBuffEffect,
        SetPronounsEffect,
        QuestActivateEffect,
        QuestFailEffect,
        AdjustGameTicksEffect,
        EmitTriggerEffect,
        PrestigeEffect,
        SetNameEffect,
        ArchetypeAddEffect,
        ArchetypeRemoveEffect,
        SkillRevokeEffect,
    ],
    Field(discriminator="type"),
]
```

**After:**

```python
Effect = Annotated[
    Union[
        ItemDropEffect,
        MilestoneGrantEffect,
        EndAdventureEffect,
        HealEffect,
        StatChangeEffect,
        StatSetEffect,
        UseItemEffect,
        SkillGrantEffect,
        DispelEffect,
        ApplyBuffEffect,
        SetPronounsEffect,
        QuestActivateEffect,
        QuestFailEffect,
        AdjustGameTicksEffect,
        EmitTriggerEffect,
        PrestigeEffect,
        SetNameEffect,
        ArchetypeAddEffect,
        ArchetypeRemoveEffect,
        SkillRevokeEffect,
        CustomEffectRef,
    ],
    Field(discriminator="type"),
]
```

`CustomEffectRef` is imported from `custom_effect.py` at the top of `adventure.py` (using `TYPE_CHECKING` guard to avoid circular import, same pattern as `DamageFormulaEntry`).

### D8: `oscilla/engine/models/__init__.py` — register the manifest kind

**Before:**

```python
from oscilla.engine.models.custom_condition import CustomConditionManifest
# ...
    "CustomCondition": CustomConditionManifest,
```

**After:**

```python
from oscilla.engine.models.custom_condition import CustomConditionManifest
from oscilla.engine.models.custom_effect import CustomEffectManifest
# ...
    "CustomCondition": CustomConditionManifest,
    "CustomEffect": CustomEffectManifest,
```

And add `"CustomEffectManifest"` to `__all__`.

### D9: `oscilla/engine/steps/effects.py` — import `CustomEffectRef`

**Before (top of file):**

```python
from oscilla.engine.models.adventure import (
    AdjustGameTicksEffect,
    ApplyBuffEffect,
    ArchetypeAddEffect,
    # ... all effect types ...
    SkillRevokeEffect,
    StatChangeEffect,
    StatSetEffect,
    UseItemEffect,
)
```

**After (add `CustomEffectRef` to the import):**

```python
from oscilla.engine.models.adventure import (
    AdjustGameTicksEffect,
    ApplyBuffEffect,
    ArchetypeAddEffect,
    # ... all effect types ...
    CustomEffectRef,
    SkillRevokeEffect,
    StatChangeEffect,
    StatSetEffect,
    UseItemEffect,
)
```

### D10: Required parameter handling

When a parameter has `default: null` (not set), it is required. The load-time validator checks that every call site supplies all required parameters. A call site that omits a required parameter gets a `ContentLoadError`.

This check is part of pass 3 in `_validate_custom_effect_refs()`:

```python
# In pass 3, after type checking:
required_params = {p.name for p in target.spec.parameters if p.default is None}
missing = required_params - set(call_params.keys())
if missing:
    errors.append(
        LoadError(
            file=Path(f"<{m.metadata.name}>"),
            message=(
                f"custom_effect {ref_name!r} called from {m.kind} {m.metadata.name!r}: "
                f"missing required parameter(s): {sorted(missing)}"
            ),
        )
    )
```

---

## Custom Effect Patterns

This section catalogs common custom effect patterns that content authors will build. Each example is a complete, valid YAML manifest.

### Pattern 1: Percentage Heal

The canonical use case — a reusable heal that takes a percentage parameter, clamped to max HP.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: heal_percentage
spec:
  displayName: "Heal Percentage"
  description: "Heals the player for a percentage of their max HP, clamped to max."
  parameters:
    - name: percent
      type: float
      default: 25
  effects:
    - type: stat_change
      stat: hp
      amount: "{{ min(player.stats['max_hp'] - player.stats['hp'], floor(player.stats['max_hp'] * params.percent / 100)) }}"
      target: player
```

Call site in an item:

```yaml
# In a potion item's use_effects
use_effects:
  - type: custom_effect
    name: heal_percentage
    params:
      percent: 75
```

Call site in a skill:

```yaml
# In a healing skill's use_effects
use_effects:
  - type: custom_effect
    name: heal_percentage
    params:
      percent: 30
```

### Pattern 2: Stat Bonus with Optional Milestone Grant

A multi-effect custom effect that grants a stat bonus and optionally records progress via a milestone. Useful for quest rewards, level-up bonuses, or achievement unlocks.

**Optional parameter convention:** A parameter with `default: null` is optional — when omitted at the call site, its value is `null` in the template context. A parameter with no `default` is required and must be provided at every call site. This distinguishes "absent" (`null`) from "explicitly empty" (`""`). Since custom effect bodies do not support conditional effect execution, optional parameters that control _whether_ an effect runs require the author to split into two custom effects (shown below).

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: grant_stat_bonus
spec:
  displayName: "Grant Stat Bonus"
  description: "Increases a named stat."
  parameters:
    - name: stat
      type: str
    - name: amount
      type: int
  effects:
    - type: stat_change
      stat: "{{ params.stat }}"
      amount: "{{ params.amount }}"
      target: player
```

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: grant_stat_bonus_with_milestone
spec:
  displayName: "Grant Stat Bonus With Milestone"
  description: "Increases a named stat and grants a milestone."
  parameters:
    - name: stat
      type: str
    - name: amount
      type: int
    - name: milestone
      type: str
  effects:
    - type: stat_change
      stat: "{{ params.stat }}"
      amount: "{{ params.amount }}"
      target: player
    - type: milestone_grant
      milestone: "{{ params.milestone }}"
```

Call site — stat bonus only (no milestone):

```yaml
effects:
  - type: custom_effect
    name: grant_stat_bonus
    params:
      stat: strength
      amount: 5
```

Call site — stat bonus with milestone:

```yaml
effects:
  - type: custom_effect
    name: grant_stat_bonus_with_milestone
    params:
      stat: strength
      amount: 5
      milestone: strength_boost_earned
```

### Pattern 3: Experience Grant

A reusable XP system. The game declares an `experience` stat in `character_config.yaml`, and this custom effect handles the grant plus threshold-based level-up logic via milestones.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: grant_xp
spec:
  displayName: "Grant Experience"
  parameters:
    - name: amount
      type: int
    - name: source
      type: str
      default: unknown
  effects:
    - type: stat_change
      stat: experience
      amount: "{{ params.amount }}"
      target: player
    - type: milestone_grant
      milestone: "xp_{{ params.source }}"
```

Call site from an adventure completion:

```yaml
effects:
  - type: custom_effect
    name: grant_xp
    params:
      amount: 100
      source: goblin_cave
```

### Pattern 4: Multi-Item Loot Package

Authors often need to grant a curated set of items together (e.g., a "starter kit", a "boss loot", a "quest reward bundle"). Instead of repeating `item_drop` effects, a custom effect encapsulates the bundle.

**Important:** The default loot group `method` is `"weighted"` (draws with replacement) and `count` is `1` (draws one entry). To guarantee all items in a group drop, use `method: "unique"` with `count` set to the number of entries.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: starter_kit
spec:
  displayName: "Starter Kit"
  description: "Grants the player their starting equipment and supplies."
  parameters: []
  effects:
    - type: item_drop
      groups:
        - method: unique
          count: 3
          items:
            - item: iron_sword
            - item: leather_armor
            - item: health_potion
```

Call site — no params needed:

```yaml
effects:
  - type: custom_effect
    name: starter_kit
```

### Pattern 5: Resource Conversion

Trade one resource for another. Useful for alchemy systems, currency exchange, or stat rebalancing.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: convert_resource
spec:
  displayName: "Convert Resource"
  description: "Decreases one stat and increases another by the same amount."
  parameters:
    - name: from_stat
      type: str
    - name: to_stat
      type: str
    - name: amount
      type: int
  effects:
    - type: stat_change
      stat: "{{ params.from_stat }}"
      amount: "{{ -params.amount }}"
      target: player
    - type: stat_change
      stat: "{{ params.to_stat }}"
      amount: "{{ params.amount }}"
      target: player
```

Call site — convert 50 gold to 10 mana potions (if `mana_potions` is a stat):

```yaml
effects:
  - type: custom_effect
    name: convert_resource
    params:
      from_stat: gold
      to_stat: mana_potions
      amount: 10
```

### Pattern 6: Archetype Transformation

A common RPG pattern: remove the old class/archetype and grant a new one, with associated stat changes. This encapsulates a full class-change sequence.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: change_archetype
spec:
  displayName: "Change Archetype"
  description: "Removes one archetype and grants another."
  parameters:
    - name: remove
      type: str
    - name: add
      type: str
  effects:
    - type: archetype_remove
      archetype: "{{ params.remove }}"
    - type: archetype_add
      archetype: "{{ params.add }}"
```

Call site from a class-change adventure:

```yaml
effects:
  - type: custom_effect
    name: change_archetype
    params:
      remove: warrior
      add: paladin
```

### Pattern 7: Debuff Application

Apply a debuff to the enemy during combat. This pattern is useful for skills that apply poison, slow, or armor-piercing effects.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: apply_enemy_debuff
spec:
  displayName: "Apply Enemy Debuff"
  description: "Applies a named buff to the enemy target."
  parameters:
    - name: buff
      type: str
    - name: turns
      type: int
      default: 3
  effects:
    - type: apply_buff
      buff_ref: "{{ params.buff }}"
      target: enemy
      variables:
        duration_turns: "{{ params.turns }}"
```

Call site from a poison skill:

```yaml
use_effects:
  - type: custom_effect
    name: apply_enemy_debuff
    params:
      buff: poison
      turns: 5
```

### Pattern 8: Chain Composition (A → B → C)

Demonstrates nested custom effects where one custom effect calls another, which calls a third. Each level has its own parameters and effects.

Level 3 — the leaf:

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: record_milestone
spec:
  displayName: "Record Milestone"
  parameters:
    - name: milestone
      type: str
  effects:
    - type: milestone_grant
      milestone: "{{ params.milestone }}"
```

Level 2 — calls level 3:

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: grant_stat_and_record
spec:
  displayName: "Grant Stat And Record"
  parameters:
    - name: stat
      type: str
    - name: amount
      type: int
    - name: milestone
      type: str
  effects:
    - type: stat_change
      stat: "{{ params.stat }}"
      amount: "{{ params.amount }}"
      target: player
    - type: custom_effect
      name: record_milestone
      params:
        milestone: "{{ params.milestone }}"
```

Wait — `params` values must be literal scalars. The line `milestone: "{{ params.milestone }}"` is a template string, which violates the non-goal. Here is the correct pattern:

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: grant_stat_and_record
spec:
  displayName: "Grant Stat And Record"
  parameters:
    - name: stat
      type: str
    - name: amount
      type: int
    - name: milestone
      type: str
  effects:
    - type: stat_change
      stat: "{{ params.stat }}"
      amount: "{{ params.amount }}"
      target: player
    - type: custom_effect
      name: record_milestone
      params:
        milestone: quest_stat_boost
```

The caller passes the milestone name at the call site, not through template interpolation. If the author needs dynamic milestone names, they should inline the `milestone_grant` effect instead of going through `record_milestone`.

Level 1 — calls level 2, used at the call site:

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: boss_reward
spec:
  displayName: "Boss Reward"
  parameters:
    - name: stat
      type: str
      default: strength
    - name: amount
      type: int
      default: 10
  effects:
    - type: custom_effect
      name: grant_stat_and_record
      params:
        stat: "{{ params.stat }}"
        amount: "{{ params.amount }}"
        milestone: boss_defeated
    - type: item_drop
      groups:
        - items:
            - item: gold_coins
              weight: 1
              count: 50
```

Again, template strings in `params:` values are not allowed. Corrected:

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: boss_reward
spec:
  displayName: "Boss Reward"
  parameters:
    - name: stat
      type: str
      default: strength
    - name: amount
      type: int
      default: 10
  effects:
    - type: custom_effect
      name: grant_stat_and_record
      params:
        stat: strength
        amount: 10
        milestone: boss_defeated
    - type: item_drop
      groups:
        - items:
            - item: gold_coins
              weight: 1
              count: 50
```

Call site in an adventure's combat `on_win` branch:

```yaml
on_win:
  effects:
    - type: custom_effect
      name: boss_reward
      params:
        stat: strength
        amount: 15
```

This demonstrates the full chain: adventure → `boss_reward` → `grant_stat_and_record` → `record_milestone`, plus the item drop at the `boss_reward` level.

### Pattern 9: Quest Stage Advancement

A custom effect that advances quest progress by checking the current stage and granting the appropriate milestone. This is useful when multiple adventures contribute to the same quest.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: advance_quest
spec:
  displayName: "Advance Quest"
  parameters:
    - name: quest
      type: str
    - name: milestone
      type: str
  effects:
    - type: milestone_grant
      milestone: "{{ params.milestone }}"
```

Call site from multiple adventures contributing to one quest:

```yaml
# In adventure "find_the_key"
effects:
  - type: custom_effect
    name: advance_quest
    params:
      quest: the_long_journey
      milestone: quest_key_found

# In adventure "cross_the_bridge"
effects:
  - type: custom_effect
    name: advance_quest
    params:
      quest: the_long_journey
      milestone: quest_bridge_crossed
```

### Pattern 10: Combat Skill with Self-Buff

A skill that deals damage, applies a buff to the player, and grants XP. Split into two variants (with/without buff) since custom effect bodies do not support conditional effect execution.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: combat_skill_with_buff
spec:
  displayName: "Combat Skill With Buff"
  description: "Deals damage, self-buffs, and grants XP."
  parameters:
    - name: damage
      type: int
    - name: self_buff
      type: str
    - name: xp
      type: int
      default: 10
  effects:
    - type: stat_change
      stat: hp
      amount: "{{ -params.damage }}"
      target: enemy
    - type: apply_buff
      buff_ref: "{{ params.self_buff }}"
      target: player
    - type: stat_change
      stat: experience
      amount: "{{ params.xp }}"
      target: player
```

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: combat_skill_no_buff
spec:
  displayName: "Combat Skill No Buff"
  description: "Deals damage and grants XP — no self-buff."
  parameters:
    - name: damage
      type: int
    - name: xp
      type: int
      default: 10
  effects:
    - type: stat_change
      stat: hp
      amount: "{{ -params.damage }}"
      target: enemy
    - type: stat_change
      stat: experience
      amount: "{{ params.xp }}"
      target: player
```

Call site from a fireball skill:

```yaml
use_effects:
  - type: custom_effect
    name: combat_skill_with_buff
    params:
      damage: 25
      self_buff: heat_resistance
      xp: 15
```

Call site from a basic attack skill:

```yaml
use_effects:
  - type: custom_effect
    name: combat_skill_no_buff
    params:
      damage: 10
      xp: 5
```

### Pattern 11: No-Parameter Effects

Not all custom effects need parameters. Some are simply named sequences of fixed effects — essentially named effect blocks.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: end_adventure_with_completion
spec:
  displayName: "Complete Adventure"
  description: "Grants a completion milestone and ends the adventure."
  parameters:
    - name: milestone
      type: str
  effects:
    - type: milestone_grant
      milestone: "{{ params.milestone }}"
    - type: end_adventure
      outcome: completed
```

Call site from multiple adventure endings:

```yaml
# In adventure "the_test"
effects:
  - type: custom_effect
    name: end_adventure_with_completion
    params:
      milestone: the_test_passed

# In adventure "the_challenge"
effects:
  - type: custom_effect
    name: end_adventure_with_completion
    params:
      milestone: the_challenge_passed
```

### Pattern 12: Combat Lifecycle Hooks

Custom effects can be wired into `CombatSystem` lifecycle hooks (`on_combat_start`, `on_round_end`, `on_combat_victory`, `on_combat_defeat`, `on_combat_end`). This lets authors define reusable combat behaviors without hardcoding them into individual combat systems.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: combat_start_arena_effects
spec:
  displayName: "Arena Combat Start"
  description: "Sets arena-specific combat stats and milestones when combat begins."
  parameters: []
  effects:
    - type: stat_set
      stat: arena_round
      value: 1
      target: combat
    - type: milestone_grant
      milestone: arena_combat_started
```

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: combat_victory_rewards
spec:
  displayName: "Combat Victory Rewards"
  description: "Grants XP and gold on any combat win."
  parameters:
    - name: xp
      type: int
      default: 50
    - name: gold
      type: int
      default: 20
  effects:
    - type: stat_change
      stat: experience
      amount: "{{ params.xp }}"
      target: player
    - type: stat_change
      stat: gold
      amount: "{{ params.gold }}"
      target: player
    - type: milestone_grant
      milestone: combat_victory
```

Usage in a `CombatSystem` manifest:

```yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: arena_combat
spec:
  player_defeat_condition:
    stat: hp
    operator: le
    value: 0
  enemy_defeat_condition:
    stat: hp
    operator: le
    value: 0
  on_combat_start:
    - type: custom_effect
      name: combat_start_arena_effects
  on_combat_victory:
    - type: custom_effect
      name: combat_victory_rewards
      params:
        xp: 100
        gold: 50
  on_round_end:
    - type: stat_change
      stat: arena_round
      amount: 1
      target: combat
```

### Pattern 13: Threshold Effects in Damage Formulas

Damage formula `threshold_effects` fire based on the formula result range. Custom effects can be used as threshold effect entries, enabling reusable post-damage behaviors.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: critical_hit_effects
spec:
  displayName: "Critical Hit Effects"
  description: "Fires when a critical hit lands — extra damage and a milestone."
  parameters:
    - name: bonus_damage
      type: int
      default: 10
  effects:
    - type: stat_change
      stat: hp
      amount: "{{ -params.bonus_damage }}"
      target: enemy
    - type: milestone_grant
      milestone: critical_hit_landed
```

Usage in a `CombatSystem` damage formula:

```yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: critical_combat
spec:
  player_defeat_condition:
    stat: hp
    operator: le
    value: 0
  enemy_defeat_condition:
    stat: hp
    operator: le
    value: 0
  player_damage_formulas:
    - target_stat: hp
      target: enemy
      formula: "{{ player.stats.strength }} + random(1, 20)"
      threshold_effects:
        - min: 25
          effects:
            - type: custom_effect
              name: critical_hit_effects
              params:
                bonus_damage: 15
```

In this example, when the player's damage roll is 25 or higher, the `critical_hit_effects` custom effect fires — dealing bonus damage and recording a milestone.

### Pattern 14: Combat Stat Manipulation with Ephemeral Stats

Combat systems support `combat_stats` — ephemeral integer stats scoped to a single combat instance. Custom effects can manipulate these for round-based mechanics, rage meters, combo counters, etc.

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: build_rage
spec:
  displayName: "Build Rage"
  description: "Increases the combat-scoped rage meter and checks for threshold."
  parameters:
    - name: amount
      type: int
      default: 5
  effects:
    - type: stat_change
      stat: rage
      amount: "{{ params.amount }}"
      target: combat
```

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: unleash_rage
spec:
  displayName: "Unleash Rage"
  description: "Drains rage meter and deals damage proportional to rage spent."
  parameters: []
  effects:
    - type: stat_change
      stat: hp
      amount: "{{ -combat_stats.rage }}"
      target: enemy
    - type: stat_set
      stat: rage
      value: 0
      target: combat
```

Usage in a `CombatSystem` manifest:

```yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: rage_combat
spec:
  player_defeat_condition:
    stat: hp
    operator: le
    value: 0
  enemy_defeat_condition:
    stat: hp
    operator: le
    value: 0
  combat_stats:
    - name: rage
      default: 0
  player_turn_mode: choice
  system_skills:
    - skill: basic_attack
    - skill: rage_attack
  on_round_end:
    - type: custom_effect
      name: build_rage
      params:
        amount: 3
```

A `rage_attack` skill could use `unleash_rage`:

```yaml
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: rage_attack
spec:
  displayName: "Rage Attack"
  use_effects:
    - type: custom_effect
      name: unleash_rage
```

---

## Edge Cases

1. **Custom effect body contains `end_adventure`** — The `_EndSignal` raised by `EndAdventureEffect` propagates up through the `run_effect` call for the body effect, through the `CustomEffectRef` handler's loop, and is caught by the existing exception handler in the step runner. This is the correct behavior: a custom effect can end the adventure.

2. **Custom effect with empty `params:` at call site** — All defaults are used. If any parameter is required (no default), this is caught by the load-time validator as a missing required parameter.

3. **Nested custom effect: A → B → C** — Each level gets its own `params` frame. A's `params` are visible in A's body effects. When B is invoked from A's body, B's `params` replace A's in the context. When C is invoked from B's body, C's `params` replace B's. After C returns, B's remaining body effects see B's `params` again. After B returns, A's remaining body effects see A's `params`.

4. **Custom effect body modifies player state** — Sequential effects in the body see each other's mutations. A `stat_change` followed by a `milestone_grant` — the milestone grant sees the updated stat. This is the expected and documented behavior.

5. **Custom effect called from within another custom effect with same `params` key** — Each custom effect has its own parameter schema and merged params dict. If both A and B declare a `percent` parameter, they are independent — A's `params.percent` does not leak into B's context.

6. **`bool` value passed where `int` is expected** — Python's `bool` is a subclass of `int`. The validator explicitly checks for this: `isinstance(param_value, bool)` when `expected_type_name == "int"`. This prevents `true` from being silently accepted as `1`.

7. **`int` value passed where `float` is expected** — Accepted. The `type_map` for `"float"` is `(int, float)`. This matches Python's numeric tower convention.

8. **Custom effect with no parameters and no effects** — `effects` has `min_length=1`, so an empty body is a Pydantic validation error at parse time.

9. **Custom effect referenced before it's declared in file order** — Works. The registry is fully populated before any effect is dispatched. Load-time validation checks against the full registry, not file order.

10. **Custom effect body contains template that references `params` but `params` is empty** — `params.get('x', default)` returns the default. `params['x']` raises `KeyError` at runtime. Load-time template validation uses the merged params (defaults + empty call-site), so if a parameter has a default, the template validates. If it's required and the call site omits it, the load-time validator catches it before template validation runs.

---

## Testing Philosophy

Tests verify the custom effects contract at three levels:

1. **Unit — model parsing and validation:** Pydantic model construction for `CustomEffectParameter`, `CustomEffectSpec`, `CustomEffectManifest`, `CustomEffectRef`. Covers: valid manifest with parameters, duplicate parameter names, empty effects list, valid call site with params.

2. **Unit — `_validate_custom_effect_refs()`:** Direct function calls with synthetic manifest lists. Covers: dangling ref error, circular chain error (A → B → A), diamond dependency (A → B, A → C, B → D, C → D — no error), unknown parameter error, type mismatch error (`int` where `str` expected, `bool` where `int` expected), missing required parameter, `int` accepted where `float` declared.

3. **Integration — `load_from_text()`:** Full loader with multi-document YAML strings. Covers: simple custom effect invocation, parameter override merge, template resolution with `params`, nested custom effect composition (A → B), custom effect in skill `use_effects`, custom effect in item `use_effects`, custom effect in archetype `gain_effects`.

4. **Integration — `run_effect()` with `CustomEffectRef`:** Mock registry + mock player + mock TUI. Covers: body effects execute sequentially, player state mutations persist across body effects, `params` injected correctly into `ExpressionContext`, nested custom effect params isolation, `end_adventure` in body propagates `_EndSignal`.

```python
def test_custom_effect_basic_execution(mock_registry, mock_player, mock_tui) -> None:
    """A custom effect with one parameter executes its body with params injected."""
    # Set up: CustomEffect "heal_pct" with parameter "percent" (default 50)
    ce = CustomEffectManifest.model_validate({
        "apiVersion": "oscilla/v1",
        "kind": "CustomEffect",
        "metadata": {"name": "heal_pct"},
        "spec": {
            "displayName": "Heal Percentage",
            "parameters": [{"name": "percent", "type": "float", "default": 50}],
            "effects": [
                {"type": "stat_change", "stat": "hp", "amount": "{{ params.percent }}", "target": "player"},
            ],
        },
    })
    mock_registry.custom_effects.register(ce)
    mock_player.stats["hp"] = 80
    mock_player.stats["max_hp"] = 100

    ref = CustomEffectRef(type="custom_effect", name="heal_pct", params={"percent": 30})
    run_effect(effect=ref, player=mock_player, registry=mock_registry, tui=mock_tui)

    assert mock_player.stats["hp"] == 110  # 80 + 30


def test_custom_effect_nested_params_isolation(mock_registry, mock_player, mock_tui) -> None:
    """Nested custom effects each get their own params frame."""
    # Inner: sets hp to params.value
    inner = CustomEffectManifest.model_validate({
        "apiVersion": "oscilla/v1",
        "kind": "CustomEffect",
        "metadata": {"name": "set_hp"},
        "spec": {
            "parameters": [{"name": "value", "type": "int", "default": 0}],
            "effects": [
                {"type": "stat_set", "stat": "hp", "value": "{{ params.value }}", "target": "player"},
            ],
        },
    })
    # Outer: calls inner with value=50, then adds 10
    outer = CustomEffectManifest.model_validate({
        "apiVersion": "oscilla/v1",
        "kind": "CustomEffect",
        "metadata": {"name": "heal_and_top_up"},
        "spec": {
            "parameters": [{"name": "bonus", "type": "int", "default": 0}],
            "effects": [
                {"type": "custom_effect", "name": "set_hp", "params": {"value": 50}},
                {"type": "stat_change", "stat": "hp", "amount": "{{ params.bonus }}", "target": "player"},
            ],
        },
    })
    mock_registry.custom_effects.register(inner)
    mock_registry.custom_effects.register(outer)
    mock_player.stats["hp"] = 100

    ref = CustomEffectRef(type="custom_effect", name="heal_and_top_up", params={"bonus": 10})
    run_effect(effect=ref, player=mock_player, registry=mock_registry, tui=mock_tui)

    assert mock_player.stats["hp"] == 60  # set to 50, then +10


def test_custom_effect_dangling_ref_raises() -> None:
    """A CustomEffectRef to an undeclared name produces a LoadError."""
    yaml = """
apiVersion: oscilla/v1
kind: Item
metadata:
  name: test-item
spec:
  category: misc
  displayName: Test
  use_effects:
    - type: custom_effect
      name: nonexistent
"""
    with pytest.raises(ContentLoadError) as exc_info:
        load_from_text(yaml, skip_references=False)
    assert "unknown CustomEffect" in str(exc_info.value)


def test_custom_effect_cycle_raises() -> None:
    """Two CustomEffects that reference each other produce a cycle LoadError."""
    yaml = """
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: effect-a
spec:
  displayName: A
  effects:
    - type: custom_effect
      name: effect-b
---
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: effect-b
spec:
  displayName: B
  effects:
    - type: custom_effect
      name: effect-a
"""
    with pytest.raises(ContentLoadError) as exc_info:
        load_from_text(yaml, skip_references=False)
    assert "circular" in str(exc_info.value).lower()


def test_custom_effect_unknown_param_raises() -> None:
    """Passing a parameter not in the schema produces a LoadError."""
    yaml = """
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: heal_pct
spec:
  displayName: Heal
  parameters:
    - name: percent
      type: float
      default: 50
  effects:
    - type: heal
      amount: full
---
apiVersion: oscilla/v1
kind: Item
metadata:
  name: test-item
spec:
  category: misc
  displayName: Test
  use_effects:
    - type: custom_effect
      name: heal_pct
      params:
        percent: 25
        nonexistent: true
"""
    with pytest.raises(ContentLoadError) as exc_info:
        load_from_text(yaml, skip_references=False)
    assert "unknown parameter" in str(exc_info.value).lower()


def test_custom_effect_type_mismatch_raises() -> None:
    """Passing a bool where int is expected produces a LoadError."""
    yaml = """
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: add_stat
spec:
  displayName: Add Stat
  parameters:
    - name: amount
      type: int
      default: 1
  effects:
    - type: stat_change
      stat: strength
      amount: "{{ params.amount }}"
      target: player
---
apiVersion: oscilla/v1
kind: Item
metadata:
  name: test-item
spec:
  category: misc
  displayName: Test
  use_effects:
    - type: custom_effect
      name: add_stat
      params:
        amount: true
"""
    with pytest.raises(ContentLoadError) as exc_info:
        load_from_text(yaml, skip_references=False)
    assert "bool" in str(exc_info.value).lower()


def test_custom_effect_int_accepted_as_float() -> None:
    """Passing an int where float is declared is accepted."""
    yaml = """
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: heal_pct
spec:
  displayName: Heal
  parameters:
    - name: percent
      type: float
      default: 50
  effects:
    - type: heal
      amount: full
---
apiVersion: oscilla/v1
kind: Item
metadata:
  name: test-item
spec:
  category: misc
  displayName: Test
  use_effects:
    - type: custom_effect
      name: heal_pct
      params:
        percent: 25
"""
    registry, warnings = load_from_text(yaml, skip_references=False)
    assert registry.items.get("test-item") is not None
```

---

## Testlandia Integration

Three new `CustomEffect` manifests in `content/testlandia/effects/` demonstrate the feature:

### `content/testlandia/effects/heal_percentage.yaml`

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: heal_percentage
spec:
  displayName: "Heal Percentage"
  description: "Heals the player for a percentage of their max HP."
  parameters:
    - name: percent
      type: float
      default: 25
  effects:
    - type: stat_change
      stat: hp
      amount: "{{ min(player.stats['max_hp'] - player.stats['hp'], floor(player.stats['max_hp'] * params.percent / 100)) }}"
      target: player
```

### `content/testlandia/effects/reward_and_milestone.yaml`

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: reward_and_milestone
spec:
  displayName: "Reward and Milestone"
  description: "Grants a stat bonus and a milestone, demonstrating composition."
  parameters:
    - name: stat
      type: str
      default: strength
    - name: amount
      type: int
      default: 5
    - name: milestone
      type: str
      default: test_reward
  effects:
    - type: stat_change
      stat: "{{ params.stat }}"
      amount: "{{ params.amount }}"
      target: player
    - type: milestone_grant
      milestone: "{{ params.milestone }}"
```

### `content/testlandia/effects/chain_demo.yaml`

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: chain_demo
spec:
  displayName: "Chain Demo"
  description: "Calls heal_percentage, then reward_and_milestone, demonstrating nested composition."
  parameters:
    - name: heal_pct
      type: float
      default: 50
  effects:
    - type: custom_effect
      name: heal_percentage
      params:
        percent: "{{ params.heal_pct }}"
    - type: custom_effect
      name: reward_and_milestone
      params:
        stat: strength
        amount: 3
        milestone: chain_completed
```

Wait — `params` values must be literal scalars, not template strings. The `chain_demo` example above uses `{{ params.heal_pct }}` as a param value, which violates the non-goal. Let me revise:

### Revised `content/testlandia/effects/chain_demo.yaml`

```yaml
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: chain_demo
spec:
  displayName: "Chain Demo"
  description: "Calls heal_percentage and reward_and_milestone, demonstrating nested composition."
  parameters:
    - name: heal_pct
      type: float
      default: 50
  effects:
    - type: custom_effect
      name: heal_percentage
      params:
        percent: 50
    - type: custom_effect
      name: reward_and_milestone
      params:
        stat: strength
        amount: 3
        milestone: chain_completed
```

The `heal_percentage` custom effect is also added to an existing testlandia healing item's `use_effects` to replace its inline `stat_change` effect, making the feature QA-able by comparing behavior before and after the switch.

An existing testlandia adventure is updated to include a choice step that triggers `chain_demo`, allowing the author to manually verify: heal fires, stat change fires, milestone is granted, all in sequence.

---

## Documentation Plan

- **`docs/authors/effects.md`** — updated section covering: `CustomEffect` manifest format, parameter schema (`name`, `type`, `default`), `type: custom_effect` call site syntax with `params:` dict, composition patterns (nested custom effects), parameter scoping rules (each level gets its own frame), load-time errors (dangling ref, cycle, unknown param, type mismatch, missing required param). Audience: content authors.

- **`docs/authors/README.md`** — table of contents updated to reference the new section in `effects.md`.

---

## Risks / Trade-offs

### Template string params not supported

**Risk:** Authors may want to pass derived values between nested custom effects (e.g., `percent: "{{ params.outer + 10 }}"`). With literal-only params, they must declare intermediate parameters.

**Mitigation:** This is a deliberate non-goal. The workaround is straightforward: declare a parameter in the inner effect that the outer effect sets to a literal. If this proves painful in practice, template-string params can be added as a follow-up change. The parameter validation and merge logic would need to be extended to support template resolution at call time.

### `params` in `ExpressionContext` is a new mutable field

**Risk:** Existing code that constructs `ExpressionContext` does not pass `params`. The `field(default_factory=dict)` default ensures backward compatibility — all existing callers get an empty dict. However, any code that copies or reconstructs `ExpressionContext` must include the new field.

**Mitigation:** The `params` field has a default, so existing code is unaffected. The only new construction site is in the `CustomEffectRef` case arm in `run_effect()`, which explicitly sets `params`.

### Effect union discriminator collision

**Risk:** Using `type: "custom_effect"` for effects vs `type: "custom"` for conditions could confuse authors.

**Mitigation:** The discriminator values are in different unions (`Effect` vs `Condition`), so Pydantic never confuses them. The author documentation clearly distinguishes the two. The longer `"custom_effect"` name is a feature, not a bug — it makes the YAML more readable.

### Validation completeness for effect fields

**Risk:** `_collect_custom_effect_refs_from_manifest()` must cover all manifest kinds that have effect fields. If a new manifest kind is added with effect fields, the collector must be updated.

**Mitigation:** The collector follows the same pattern as `_collect_custom_condition_refs_from_manifest()`. A code review checklist item: whenever a new manifest kind with `List[Effect]` fields is added, update both collectors. This is the same maintenance burden as the condition collector.

### Performance: nested custom effect resolution

**Risk:** Deep nesting (A → B → C → D → E) adds registry lookups and context copies at each level. Each level is O(1) for the lookup and O(N) for the context copy where N is the number of body effects.

**Mitigation:** In practice, nesting depth > 3 is rare. The overhead is negligible compared to template rendering and effect execution. If profiling shows this is a bottleneck, the context copy can be replaced with a stack-based approach where `params` is pushed/popped on a list.

---

## Pipeline diagram

```mermaid
flowchart TD
    A[Author writes CustomEffect manifest] --> B[Loader: parse YAML]
    B --> C{Pydantic validates CustomEffectSpec}
    C -->|valid| D[Register in registry.custom_effects]
    C -->|invalid| E[LoadError: schema violation]

    F[Author writes type: custom_effect in effect list] --> G[Loader: parse YAML]
    G --> H{Pydantic validates CustomEffectRef}
    H -->|valid| I[Added to Effect union]

    D & I --> J[validate_references()]
    J --> K[Pass 1: dangling ref check]
    K -->|error| L[ContentLoadError]
    K -->|ok| M[Pass 2: cycle detection]
    M -->|error| L
    M -->|ok| N[Pass 3: param validation]
    N -->|error| L
    N -->|ok| O[Content loaded successfully]

    P[Runtime: run_effect encounters CustomEffectRef] --> Q[Lookup in registry.custom_effects]
    Q --> R[Merge defaults + call-site params]
    R --> S[Build ExpressionContext with params]
    S --> T[Iterate body effects, pass ctx]
    T --> U{Body effect is CustomEffectRef?}
    U -->|yes| R
    U -->|no| V[Dispatch to standard handler]
```
