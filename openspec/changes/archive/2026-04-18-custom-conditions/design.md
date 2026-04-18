# Design: Custom Conditions

## Context

The condition evaluator is the engine's most reusable primitive. Every subsystem — adventure pool gating, step branching, item requirements, passive effects, location locks — accepts a `Condition` tree. Authors write these trees in YAML, and the engine evaluates them against live character state.

Currently the condition vocabulary is entirely structural: every site that needs the same gate must repeat the full YAML block. There is no mechanism to declare a named condition once and reference it from multiple manifests. Large content packages end up duplicating complex gate logic — event windows, archetype requirements, multi-prerequisite quest guards — across dozens of manifests. When the logic changes, every copy must be found and updated.

This change adds a macro layer: a `CustomCondition` manifest kind that gives a condition body a name, and a `type: custom` condition leaf that resolves that name at evaluation time. No new runtime semantics are introduced — a `type: custom` condition evaluates identically to inlining the body at that site.

This change also fixes a long-standing gap in passive effect condition support. Passive effects have always evaluated their conditions with `registry=None` as a blanket recursion guard against the two condition types that re-enter `effective_stats()` or `available_skills()`. That guard was overly broad: it also silenced `item_held_label`, `any_item_equipped`, all `game_calendar_*` conditions, and (once added) `type: custom`, even though none of those are re-entrant. The fix passes `registry` through to passive condition evaluation and promotes the two genuinely recursive types to hard load-time errors, which eliminates the recursion risk while unlocking the full rest of the condition vocabulary for passive use.

The change surface is well-contained:

```
oscilla/engine/models/base.py          ← add CustomConditionRef to Condition union
oscilla/engine/models/custom_condition.py  ← new: CustomConditionSpec, CustomConditionManifest
oscilla/engine/models/__init__.py      ← register CustomConditionManifest
oscilla/engine/registry.py             ← add custom_conditions KindRegistry field
oscilla/engine/conditions.py           ← add case arm for CustomConditionRef
oscilla/engine/character.py            ← pass registry through to passive condition evaluation
oscilla/engine/loader.py               ← dangling-ref + cycle validation; passive condition errors
```

---

## Goals / Non-Goals

**Goals:**

- Allow authors to declare a named condition body in a `kind: CustomCondition` manifest.
- Allow any manifest field typed as `Condition` to reference a `CustomCondition` by name via `type: custom`.
- Custom conditions can reference other custom conditions (composition).
- Dangling `name:` references raise a `ContentLoadError` at content load time with a clear error message.
- Circular references raise a `ContentLoadError` at content load time with the full cycle path in the message.
- `type: custom` is valid in passive effect conditions when its body (transitively) does not contain a re-entrant type.
- `item_held_label`, `any_item_equipped`, and all `game_calendar_*` conditions become fully functional in passive effects.
- `character_stat` with `stat_source: effective` and `skill` become hard load-time errors in passive effects (they caused silent infinite recursion before).

**Non-Goals:**

- Cross-package `CustomCondition` references (names are scoped to the content package they are declared in).
- `CustomCondition` manifests that accept parameters or template expressions — bodies are static YAML condition trees only.
- Any UI surface for browsing or visualizing `CustomCondition` manifests.

---

## Decisions

### D1: Resolution at evaluation time, not load time

`CustomConditionRef` stores only the `name` string. The body is looked up in `registry.custom_conditions` at the moment `evaluate()` processes the node. This is intentional: it means forward references within a package work naturally — a `CustomCondition` declared later in the file scan order can still be referenced in an `Adventure` that was parsed earlier.

The trade-off is a small per-evaluation dict lookup. At content load time the registry is fully populated before any evaluation occurs, so there are no partial-population issues in practice.

### D2: Strict circular-reference detection at load time

A depth-first search over the `CustomCondition` dependency graph is run during `validate_references()`. Any back-edge (a node currently on the DFS stack) is flagged as a cycle and raises a `ContentLoadError`. The error message includes the full cycle path so authors can identify the problem immediately.

Detection happens only among `CustomCondition` manifests, not across the full condition graph — it is scoped to the nodes that can form cycles (only `CustomConditionRef` leaves create edges in this graph). Standard condition leaves (`level`, `milestone`, etc.) are not nodes in the dependency graph.

### D3: Error message pattern matches existing validators

All existing cross-reference errors follow the pattern `LoadError(file=Path(f"<{manifest_name}>"), message="...")`. The new validators match this pattern exactly:

- Dangling ref: `"type: custom condition references unknown CustomCondition: 'bad-name'"`
- Cycle: `"circular reference in CustomCondition 'a': a → b → a"`

### D4: `displayName` is optional

`CustomConditionSpec.display_name` is `str | None = None`, matching the convention used by `BuffSpec`, `SkillSpec`, and other spec types with optional display names. Packages that want to generate human-readable condition documentation can set it; packages that use `CustomCondition` purely for structural DRY do not need to.

### D5: `CustomConditionManifest` is a `KindRegistry` member, not a singleton

`CustomCondition` manifests follow the same registration pattern as `BuffManifest`, `SkillManifest`, etc. — each is registered by name in a `KindRegistry[CustomConditionManifest]` on `ContentRegistry`. This is consistent with the existing architecture and requires no special-case handling.

### D6: Pass `registry` through to passive evaluation; hard-error the two re-entrant types

Passive effects currently call `evaluate(condition, player, registry=None)` to break a potential recursion cycle. The two types that actually cause recursion are:

- `character_stat` with `stat_source: effective` → calls `player.effective_stats(registry)` → re-enters passive evaluation
- `skill` → calls `player.available_skills(registry)` → re-enters passive evaluation

All other condition types that require the registry — `item_held_label`, `any_item_equipped`, `game_calendar_*`, and `type: custom` — perform a simple dict or resolver lookup with no re-entrant call path.

The fix: change all four `registry=None` call sites in `character.py` to `registry=registry`, then move the recursion-dangerous checks from `_validate_passive_effects()` (warnings path) into a new `_validate_passive_effect_conditions()` helper (errors path) called from `validate_references()`. The two dangerous types become `LoadError`s. The existing `LoadWarning`s for `item_held_label` and `any_item_equipped` are removed because those conditions now work correctly.

`type: custom` in a passive effect is valid only if its body (transitively, following all `CustomConditionRef` chains) contains none of the re-entrant types. The `_validate_passive_effect_conditions()` helper resolves `CustomConditionRef` nodes by looking them up in the manifests list and recursively checking their bodies, emitting a `LoadError` if a banned type is found anywhere in the chain.

---

## Implementation

### New file: `oscilla/engine/models/custom_condition.py`

```python
"""Pydantic models for the CustomCondition manifest kind."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from oscilla.engine.models.base import ManifestEnvelope

if TYPE_CHECKING:
    from oscilla.engine.models.base import Condition


class CustomConditionSpec(BaseModel):
    display_name: str | None = None
    # The stored condition body. Typed as Condition but imported lazily to avoid
    # a circular import at module load time (base.py imports this module indirectly
    # through the Condition union once CustomConditionRef is added to it).
    condition: "Condition"


class CustomConditionManifest(ManifestEnvelope):
    kind: Literal["CustomCondition"]
    spec: CustomConditionSpec
```

### `oscilla/engine/models/base.py` — add `CustomConditionRef` to the `Condition` union

The new leaf model is appended to the `Condition` union. No existing member changes.

**Before (the `Condition` union, last ~5 lines):**

```python
        ZodiacIsCondition, ChineseZodiacIsCondition,
        MonthIsCondition, DayOfWeekIsCondition, DateIsCondition, DateBetweenCondition,
        TimeBetweenCondition,
    ],
    Field(discriminator="type"),
]
```

**After:**

```python
        ZodiacIsCondition, ChineseZodiacIsCondition,
        MonthIsCondition, DayOfWeekIsCondition, DateIsCondition, DateBetweenCondition,
        TimeBetweenCondition,
        CustomConditionRef,
    ],
    Field(discriminator="type"),
]
```

The new class, added just before the `Condition` union definition:

```python
class CustomConditionRef(BaseModel):
    """Reference to a named CustomCondition manifest declared in the same content package.

    Resolved at evaluation time against registry.custom_conditions.
    Validated at load time: dangling references and circular dependency chains
    both raise ContentLoadError.
    """

    type: Literal["custom"]
    name: str
```

The import of `CustomConditionRef` in `conditions.py` is added alongside the other leaf imports (see below).

### `oscilla/engine/models/__init__.py` — register `CustomConditionManifest`

**Before:**

```python
from oscilla.engine.models.skill import SkillManifest

MANIFEST_REGISTRY: Dict[str, Type[ManifestEnvelope]] = {
    ...
    "Buff": BuffManifest,
    "LootTable": LootTableManifest,
}

__all__ = [
    "MANIFEST_REGISTRY",
    ...
    "BuffManifest",
```

**After:**

```python
from oscilla.engine.models.custom_condition import CustomConditionManifest
from oscilla.engine.models.skill import SkillManifest

MANIFEST_REGISTRY: Dict[str, Type[ManifestEnvelope]] = {
    ...
    "Buff": BuffManifest,
    "LootTable": LootTableManifest,
    "CustomCondition": CustomConditionManifest,
}

__all__ = [
    "MANIFEST_REGISTRY",
    ...
    "BuffManifest",
    "CustomConditionManifest",
```

### `oscilla/engine/registry.py` — add `custom_conditions` field and `build()` arm

**Before (`ContentRegistry.__init__`, skills/buffs lines):**

```python
        self.skills: KindRegistry[SkillManifest] = KindRegistry()
        self.buffs: KindRegistry[BuffManifest] = KindRegistry()
        self.game: GameManifest | None = None
```

**After:**

```python
        self.skills: KindRegistry[SkillManifest] = KindRegistry()
        self.buffs: KindRegistry[BuffManifest] = KindRegistry()
        self.custom_conditions: KindRegistry[CustomConditionManifest] = KindRegistry()
        self.game: GameManifest | None = None
```

**Before (`build()`, the Buff arm):**

```python
                case "Buff":
                    registry.buffs.register(cast(BuffManifest, m))
                case "Game":
```

**After:**

```python
                case "Buff":
                    registry.buffs.register(cast(BuffManifest, m))
                case "CustomCondition":
                    registry.custom_conditions.register(cast(CustomConditionManifest, m))
                case "Game":
```

The import of `CustomConditionManifest` is added to the imports block in `registry.py`.

### `oscilla/engine/conditions.py` — add `CustomConditionRef` case arm

**Before (imports from `base.py`):**

```python
from oscilla.engine.models.base import (
    AdventuresCompletedCondition,
    AllCondition,
    ...
    TimeBetweenCondition,
    ZodiacIsCondition,
)
```

**After:**

```python
from oscilla.engine.models.base import (
    AdventuresCompletedCondition,
    AllCondition,
    ...
    CustomConditionRef,
    TimeBetweenCondition,
    ZodiacIsCondition,
)
```

**Before (end of `evaluate()` match block):**

```python
        case _:
            logger.warning("Unhandled condition type: %r — evaluating False.", condition)
            return False
```

**After (new arm inserted before the wildcard):**

```python
        case CustomConditionRef(name=n):
            if registry is None:
                # Registry is required to resolve custom condition names.
                # This should not occur in production paths; all callers supply the registry.
                logger.warning(
                    "type: custom condition %r requires registry — evaluating False.", n
                )
                return False
            defn = registry.custom_conditions.get(n)
            if defn is None:
                # Dangling reference that slipped past load-time validation, or the
                # registry was built from a subset of manifests. Fail safe.
                logger.warning(
                    "type: custom condition %r not found in registry — evaluating False.", n
                )
                return False
            return evaluate(defn.spec.condition, player, registry, exclude_item)

        case _:
            logger.warning("Unhandled condition type: %r — evaluating False.", condition)
            return False
```

### `oscilla/engine/character.py` — pass registry through to passive evaluation

Four call sites are updated — two in `effective_stats()` and two in `available_skills()`. In each case the pattern is identical: `registry=None` becomes `registry=registry`.

**Before (representative, repeated four times across the two methods):**

```python
            for passive in registry.game.spec.passive_effects:
                # Passive effects are evaluated without registry to avoid recursion.
                if evaluate(condition=passive.condition, player=self, registry=None):
```

**After:**

```python
            for passive in registry.game.spec.passive_effects:
                # Registry is now passed through. Re-entrant types (character_stat with
                # stat_source: effective, skill) are blocked at load time by
                # _validate_passive_effect_conditions() rather than at runtime here.
                if evaluate(condition=passive.condition, player=self, registry=registry):
```

The same change applies to the archetype passive effect loops in both methods.

### `oscilla/engine/loader.py` — validation helpers and wiring

Three new private functions are added for `CustomCondition` cross-reference validation, following the established pattern of `_collect_*` and `_validate_*` helpers. Additionally, `_validate_passive_effects()` is updated and a new `_validate_passive_effect_conditions()` helper is added to `validate_references()`.

**`_collect_custom_condition_refs_in_condition()`** — recursively walks a condition tree and yields every `CustomConditionRef.name` encountered.

```python
def _collect_custom_condition_refs_in_condition(condition: Condition) -> Set[str]:
    """Recursively collect all CustomConditionRef name strings from a condition tree."""
    refs: Set[str] = set()
    match condition:
        case CustomConditionRef(name=n):
            refs.add(n)
        case AllCondition(conditions=children):
            for child in children:
                refs.update(_collect_custom_condition_refs_in_condition(child))
        case AnyCondition(conditions=children):
            for child in children:
                refs.update(_collect_custom_condition_refs_in_condition(child))
        case NotCondition(condition=child):
            refs.update(_collect_custom_condition_refs_in_condition(child))
        case _:
            pass
    return refs
```

**`_collect_custom_condition_refs_from_manifest()`** — collects all `CustomConditionRef` names from every condition field in a manifest, including `CustomCondition` manifests themselves (their bodies may reference other custom conditions).

```python
def _collect_custom_condition_refs_from_manifest(m: ManifestEnvelope) -> Set[str]:
    """Collect all CustomConditionRef names referenced in a manifest's condition fields."""
    refs: Set[str] = set()

    def _add(cond: Condition | None) -> None:
        if cond is not None:
            refs.update(_collect_custom_condition_refs_in_condition(cond))

    match m.kind:
        case "CustomCondition":
            cc = cast(CustomConditionManifest, m)
            _add(cc.spec.condition)
        case "Location":
            loc = cast(LocationManifest, m)
            _add(loc.spec.unlock)
            _add(loc.spec.effective_unlock)
            for adv_entry in loc.spec.adventures:
                _add(adv_entry.requires)
        case "Region":
            region = cast(RegionManifest, m)
            _add(region.spec.unlock)
            _add(region.spec.effective_unlock)
        case "Adventure":
            adv = cast(AdventureManifest, m)
            _add(adv.spec.requires)
            for step in adv.spec.steps:
                match step:
                    case ChoiceStep():
                        for opt in step.options:
                            _add(opt.requires)
                    case PassiveStep():
                        _add(step.bypass)
                    case StatCheckStep():
                        _add(step.condition)
        case "Item":
            item = cast(ItemManifest, m)
            if item.spec.equip is not None:
                _add(item.spec.equip.requires)
        case "Skill":
            skill = cast(SkillManifest, m)
            _add(skill.spec.requires)
        case "Game":
            game = cast(GameManifest, m)
            for pe in game.spec.passive_effects:
                _add(pe.condition)

    return refs
```

**`_validate_custom_condition_refs()`** — performs two passes: (1) dangling reference check, (2) circular reference detection via DFS.

```python
def _validate_custom_condition_refs(manifests: List[ManifestEnvelope]) -> List[LoadError]:
    """Validate all CustomConditionRef usages across manifests.

    Two checks:
    1. Every referenced name must exist as a declared CustomCondition manifest.
    2. No CustomCondition body may form a circular dependency chain (direct or indirect).
    """
    errors: List[LoadError] = []
    known_names: Set[str] = {m.metadata.name for m in manifests if m.kind == "CustomCondition"}

    # --- Pass 1: dangling reference check ---
    for m in manifests:
        refs = _collect_custom_condition_refs_from_manifest(m)
        for ref in sorted(refs):
            if ref not in known_names:
                errors.append(
                    LoadError(
                        file=Path(f"<{m.metadata.name}>"),
                        message=f"type: custom condition references unknown CustomCondition: {ref!r}",
                    )
                )

    # --- Pass 2: circular reference detection (DFS over CustomCondition bodies only) ---
    # Build adjacency: name → set of CustomConditionRef names in its body.
    # Only names that are themselves declared CustomConditions form edges; dangling
    # refs are already reported in pass 1 and excluded here to avoid false cycles.
    adjacency: Dict[str, Set[str]] = {}
    for m in manifests:
        if m.kind == "CustomCondition":
            cc = cast(CustomConditionManifest, m)
            body_refs = _collect_custom_condition_refs_in_condition(cc.spec.condition)
            adjacency[m.metadata.name] = body_refs & known_names

    # Standard iterative DFS cycle detection.
    # visited: nodes whose full subtree has been explored (no cycle found below them).
    # in_stack: nodes currently on the active DFS path (cycle if we see one again).
    visited: Set[str] = set()
    in_stack: Set[str] = set()

    def _dfs(node: str, path: List[str]) -> None:
        in_stack.add(node)
        for neighbour in sorted(adjacency.get(node, set())):
            if neighbour in in_stack:
                # Cycle found — build the human-readable path.
                cycle_start = path.index(neighbour)
                cycle_path = " → ".join(path[cycle_start:] + [neighbour])
                errors.append(
                    LoadError(
                        file=Path(f"<{node}>"),
                        message=f"circular reference in CustomCondition {node!r}: {cycle_path}",
                    )
                )
            elif neighbour not in visited:
                _dfs(neighbour, path + [neighbour])
        in_stack.discard(node)
        visited.add(node)

    for name in sorted(adjacency):
        if name not in visited:
            _dfs(name, [name])

    return errors
```

**Wiring into `validate_references()`:**

**Before (end of `validate_references`):**

```python
    errors.extend(_validate_archetype_refs(manifests))
    errors.extend(_validate_loot_condition_refs(manifests))

    return errors
```

**After:**

```python
    errors.extend(_validate_archetype_refs(manifests))
    errors.extend(_validate_loot_condition_refs(manifests))
    errors.extend(_validate_custom_condition_refs(manifests))
    errors.extend(_validate_passive_effect_conditions(manifests))

    return errors
```

**`_validate_passive_effect_conditions()`** — new helper called from `validate_references()` that hard-errors the two re-entrant condition types in passive effects. When a `CustomConditionRef` is found, the validator resolves its body transitively and applies the same checks to the full chain.

```python
def _validate_passive_effect_conditions(manifests: List[ManifestEnvelope]) -> List[LoadError]:
    """Hard-error on passive effect conditions that cause infinite recursion.

    Passive effects are evaluated inside effective_stats() and available_skills(),
    which are themselves called during condition evaluation. Two condition types
    re-enter those methods and will cause infinite recursion:

    - character_stat with stat_source: effective  →  calls effective_stats()
    - skill                                        →  calls available_skills()

    type: custom conditions are checked transitively: if the resolved body (or any
    body it references) contains a banned type, the error is reported on the
    passive effect that holds the CustomConditionRef.
    """
    from oscilla.engine.models.base import (
        CharacterStatCondition,
        CustomConditionRef,
        SkillCondition,
        AllCondition,
        AnyCondition,
        NotCondition,
    )

    errors: List[LoadError] = []

    game_manifest = next((m for m in manifests if m.kind == "Game"), None)
    if game_manifest is None:
        return errors
    game = cast(GameManifest, game_manifest)

    # Pre-build a name→body map for CustomCondition resolution.
    custom_condition_bodies: Dict[str, object] = {
        m.metadata.name: cast(CustomConditionManifest, m).spec.condition
        for m in manifests
        if m.kind == "CustomCondition"
    }

    def _contains_banned_type(condition: object, seen_custom: Set[str]) -> str | None:
        """Return an error description string if a banned type is found, else None.

        seen_custom guards against cycles (already caught by _validate_custom_condition_refs)
        so we do not recurse infinitely here.
        """
        if condition is None:
            return None
        if isinstance(condition, CharacterStatCondition) and condition.stat_source == "effective":
            return "character_stat with stat_source: effective (causes infinite recursion via effective_stats())"
        if isinstance(condition, SkillCondition):
            return "skill (causes infinite recursion via available_skills())"
        if isinstance(condition, CustomConditionRef):
            if condition.name in seen_custom:
                return None  # cycle already reported elsewhere
            body = custom_condition_bodies.get(condition.name)
            if body is None:
                return None  # dangling ref already reported elsewhere
            return _contains_banned_type(body, seen_custom | {condition.name})
        if isinstance(condition, AllCondition):
            for sub in condition.conditions:
                result = _contains_banned_type(sub, seen_custom)
                if result:
                    return result
        if isinstance(condition, AnyCondition):
            for sub in condition.conditions:
                result = _contains_banned_type(sub, seen_custom)
                if result:
                    return result
        if isinstance(condition, NotCondition):
            return _contains_banned_type(condition.condition, seen_custom)
        return None

    for idx, passive in enumerate(game.spec.passive_effects):
        banned = _contains_banned_type(passive.condition, set())
        if banned:
            errors.append(
                LoadError(
                    file=Path("<game>"),
                    message=f"passive_effects[{idx}] condition uses {banned}; this type cannot be used in passive effects",
                )
            )

    return errors
```

**`_validate_passive_effects()` — updated** to remove the now-fixed `LoadWarning`s for `item_held_label` and `any_item_equipped` (both work correctly once `registry` is passed through), and remove the `character_stat` warning (promoted to a hard error above).

**Before:**

```python
def _validate_passive_effects(manifests: List[ManifestEnvelope]) -> List[LoadWarning]:
    """Emit warnings for passive effects that use unsupported condition types.

    Passive effects are evaluated without a registry (to avoid recursion), so:
    - item_held_label and any_item_equipped conditions will always evaluate False.
    - character_stat conditions with stat_source: effective cannot access gear bonuses.
    """
    from oscilla.engine.models.base import AnyItemEquippedCondition, CharacterStatCondition, ItemHeldLabelCondition

    warnings: List[LoadWarning] = []

    game_manifest = next((m for m in manifests if m.kind == "Game"), None)
    if game_manifest is None:
        return warnings

    game = cast(GameManifest, game_manifest)

    def _check_condition(condition: object, passive_index: int) -> List[LoadWarning]:
        """Recursively check a condition tree for unsupported passive condition types."""
        from oscilla.engine.models.base import AllCondition, AnyCondition, NotCondition

        found: List[LoadWarning] = []
        if condition is None:
            return found
        if isinstance(condition, ItemHeldLabelCondition):
            found.append(
                LoadWarning(
                    file=Path("<game>"),
                    message=f"passive_effects[{passive_index}] uses item_held_label condition which requires a registry and will always evaluate False in passive context",
                    suggestion="Use a stat or milestone condition instead, or accept that this passive effect will never activate.",
                )
            )
        elif isinstance(condition, AnyItemEquippedCondition):
            found.append(
                LoadWarning(
                    file=Path("<game>"),
                    message=f"passive_effects[{passive_index}] uses any_item_equipped condition which requires a registry and will always evaluate False in passive context",
                    suggestion="Use a stat or milestone condition instead, or accept that this passive effect will never activate.",
                )
            )
        elif isinstance(condition, CharacterStatCondition) and condition.stat_source == "effective":
            found.append(
                LoadWarning(
                    file=Path("<game>"),
                    message=f"passive_effects[{passive_index}] uses character_stat with stat_source: effective which cannot access gear bonuses in passive context",
                    suggestion="Set stat_source: base to compare against raw stats, which is always available.",
                )
            )
        elif isinstance(condition, AllCondition):
            for sub in condition.conditions:
                found.extend(_check_condition(sub, passive_index))
        elif isinstance(condition, AnyCondition):
            for sub in condition.conditions:
                found.extend(_check_condition(sub, passive_index))
        elif isinstance(condition, NotCondition):
            found.extend(_check_condition(condition.condition, passive_index))
        return found

    for idx, passive in enumerate(game.spec.passive_effects):
        warnings.extend(_check_condition(passive.condition, idx))

    return warnings
```

**After** (all three problematic checks are removed — `item_held_label`/`any_item_equipped` now work, `character_stat`/`skill` moved to hard errors above; the function body may retain unrelated warning checks if any exist, otherwise becomes a stub returning `[]`):

```python
def _validate_passive_effects(manifests: List[ManifestEnvelope]) -> List[LoadWarning]:
    """Emit warnings for passive effects that use condition types with limited passive support.

    Hard errors for re-entrant types (character_stat stat_source: effective, skill) are
    handled by _validate_passive_effect_conditions() in validate_references() instead.
    """
    warnings: List[LoadWarning] = []
    # All previously-warned condition types are now either fully supported
    # (item_held_label, any_item_equipped) or hard-errored at reference validation time.
    return warnings
```

---

## Testlandia Integration

Two `CustomCondition` manifests and one adventure update are added to the testlandia content package to allow manual QA of the full feature.

**`content/testlandia/conditions/test-high-level.yaml`** — a standalone custom condition that is true when the player's level is 10 or above:

```yaml
apiVersion: oscilla/v1
kind: CustomCondition
metadata:
  name: test-high-level
spec:
  displayName: "High Level (10+)"
  condition:
    type: character_stat
    stat: level
    gte: 10
```

**`content/testlandia/conditions/test-high-level-warrior.yaml`** — a composed condition that references `test-high-level` and adds an archetype requirement, demonstrating composition:

```yaml
apiVersion: oscilla/v1
kind: CustomCondition
metadata:
  name: test-high-level-warrior
spec:
  displayName: "High Level Warrior"
  condition:
    type: all
    conditions:
      - type: custom
        name: test-high-level
      - type: has_archetype
        name: warrior
```

An existing testlandia adventure (such as the grant-title adventure) gains a `requires` block using `type: custom` to gate entry on `test-high-level`, making it immediately observable during manual QA play-through.

---

## Documentation Plan

**`docs/authors/conditions.md`** — primary audience: content authors

This document already documents all condition types. It gains:

1. A new **Custom Conditions** section explaining `kind: CustomCondition` manifest format, the `spec.condition` field, and the optional `display_name`.
2. A **`type: custom` usage** subsection with a copy-paste YAML example showing both declaration and usage.
3. A **Composition** subsection explaining that `CustomCondition` bodies can reference other `CustomCondition` manifests by name, with a two-level example.
4. A **Validation** subsection briefly describing what errors authors will see for dangling references and circular dependencies, and how to resolve them.
5. A note recommending a `conditions/` subdirectory as the conventional location for `CustomCondition` manifests, alongside `adventures/`, `items/`, etc.

**`docs/dev/game-engine.md`** — primary audience: engine contributors

The **Condition System** section (currently lines ~232–292) contains a list of leaf condition types and the `evaluate()` signature. It gains:

1. `custom` added to the **Leaf Conditions** list with a one-line description: _"References a named `CustomCondition` manifest; resolved at evaluation time via the registry."_
2. A new **Custom Conditions** paragraph after the Logical Operators subsection explaining that `CustomCondition` manifests store named condition bodies, `type: custom` resolves them at evaluation time, and load-time validation catches dangling refs and cycles. This paragraph is the contributor-facing counterpart to the author-facing section in `conditions.md` — it describes the implementation hook points rather than the authoring syntax.

**`docs/system-overview.md`** — primary audience: contributors and AI agents

The **Condition Evaluator** subsection (currently around line 499) contains a condition categories table and a pointer to `docs/authors/conditions.md`. It gains:

1. `custom` added to the condition categories table as a new **Reuse** row with example: `custom`.
2. A one-sentence note after the table: _"`CustomCondition` manifests give names to reusable condition bodies; `type: custom` references them by name at evaluation time — see [Custom Conditions](authors/conditions.md#custom-conditions)."_

**`docs/authors/passive-effects.md`** — primary audience: content authors (correctness fix)

The **Condition Restrictions** section currently lists `item_held_label`, `any_item_equipped`, and `character_stat (stat_source: effective)` as passive-effect restrictions because they relied on a registry that was not passed through. That restriction is lifted for most types as part of this change. The section requires the following updates:

1. Remove `item_held_label` and `any_item_equipped` from the restricted list — they now work in passive effects.
2. Change `character_stat (stat_source: effective)` and `skill` entries from soft advisories to hard errors: _"Using this type in a passive effect is a load-time error. Use `stat_source: base` for `character_stat`, or restructure the condition."_
3. Remove any note about `game_calendar_*` conditions being broken in passive effects (they were never documented as restricted but were silently broken — they now work).
4. Add `type: custom` as a new entry in the **Supported** subsection: _"Supported in passive effects. If the custom condition body (or any body it references) contains `character_stat (stat_source: effective)` or `skill`, a load-time error is raised."_
5. Update the section summary sentence to reflect that only two types remain prohibited: `character_stat (stat_source: effective)` and `skill`.

**`docs/authors/cli.md`** — primary audience: content authors (correctness fix)

Line 46 contains a hardcoded list of plural kind slugs valid for `content list <kind>` and related commands: `regions`, `locations`, `adventures`, etc. `custom-conditions` must be appended to this list once the kind is registered.

**`docs/authors/README.md`** — primary audience: new authors (completeness)

The **Authoring Model** table row for Conditions currently reads: _"All condition types — level, milestone, item, stat, skill, calendar/time predicates, and logical operators."_ It should append _"and reusable named conditions (`type: custom`)"_ so new authors discover the feature from the overview.

These are all the documents that require changes — this feature introduces no API surface, no database schema changes, and no TUI changes.

---

## Testing Philosophy

Tests live in `tests/engine/test_custom_conditions.py`, mirroring the file structure of the main package. No test references the `content/` directory — all fixtures are constructed directly as Pydantic models or minimal in-Python YAML strings passed to the loader.

**Tier 1 — unit tests on the condition evaluator** (`test_evaluate_custom_condition_*`):

These tests construct a `ContentRegistry` directly in Python, populate `registry.custom_conditions` with a `CustomConditionManifest`, and call `evaluate()` with a `CustomConditionRef`. They require no YAML loading.

```python
def test_evaluate_custom_condition_resolves_body() -> None:
    """A type: custom condition delegates to its stored body."""
    from oscilla.engine.models.base import CustomConditionRef, LevelCondition
    from oscilla.engine.models.custom_condition import CustomConditionManifest, CustomConditionSpec
    from oscilla.engine.models.base import ManifestMetadata
    from oscilla.engine.registry import ContentRegistry
    from oscilla.engine.conditions import evaluate

    spec = CustomConditionSpec(condition=LevelCondition(type="level", value=5))
    manifest = CustomConditionManifest(
        apiVersion="oscilla/v1",
        kind="CustomCondition",
        metadata=ManifestMetadata(name="test-gate"),
        spec=spec,
    )
    registry = ContentRegistry()
    registry.custom_conditions.register(manifest)

    low_player = make_character_state(level=3)
    high_player = make_character_state(level=7)

    assert evaluate(CustomConditionRef(type="custom", name="test-gate"), low_player, registry) is False
    assert evaluate(CustomConditionRef(type="custom", name="test-gate"), high_player, registry) is True


def test_evaluate_custom_condition_missing_registry_returns_false() -> None:
    """type: custom with no registry logs a warning and returns False."""
    from oscilla.engine.models.base import CustomConditionRef
    from oscilla.engine.conditions import evaluate

    player = make_character_state()
    result = evaluate(CustomConditionRef(type="custom", name="anything"), player, registry=None)
    assert result is False


def test_evaluate_custom_condition_unknown_name_returns_false() -> None:
    """type: custom referencing a name absent from registry returns False."""
    from oscilla.engine.models.base import CustomConditionRef
    from oscilla.engine.conditions import evaluate
    from oscilla.engine.registry import ContentRegistry

    registry = ContentRegistry()  # empty — no custom conditions registered
    player = make_character_state()
    result = evaluate(CustomConditionRef(type="custom", name="no-such-condition"), player, registry)
    assert result is False
```

**Tier 2 — unit tests on `_validate_custom_condition_refs()`** (`test_validate_custom_condition_refs_*`):

These tests call the validator directly with a list of `ManifestEnvelope` objects constructed in Python. They validate error messages and counts without a full loader pipeline.

```python
def test_validate_dangling_ref_produces_error() -> None:
    """A type: custom that references a non-existent CustomCondition raises a LoadError."""
    from oscilla.engine.loader import _validate_custom_condition_refs
    from oscilla.engine.models.base import CustomConditionRef, ManifestMetadata
    from oscilla.engine.models.adventure import AdventureManifest  # contains a step with requires
    # ... build a minimal AdventureManifest whose requires is CustomConditionRef(name="missing") ...
    errors = _validate_custom_condition_refs([adventure_manifest])
    assert len(errors) == 1
    assert "missing" in errors[0].message
    assert "unknown CustomCondition" in errors[0].message


def test_validate_direct_circular_ref_produces_error() -> None:
    """A CustomCondition whose body references itself raises a LoadError with cycle path."""
    # ... build two CustomConditionManifests: a → b → a ...
    errors = _validate_custom_condition_refs([manifest_a, manifest_b])
    assert any("circular reference" in e.message for e in errors)
    assert any("a → b → a" in e.message or "b → a → b" in e.message for e in errors)


def test_validate_valid_composition_produces_no_errors() -> None:
    """A → B where both exist and there is no cycle raises no errors."""
    # ... build two valid CustomConditionManifests where a references b ...
    errors = _validate_custom_condition_refs([manifest_a, manifest_b])
    assert errors == []
```

**Tier 3 — loader integration test** (`test_load_custom_conditions_*`):

These tests call the full `scan()`/`parse()`/`validate_references()` pipeline using a minimal fixture set at `tests/fixtures/content/custom-conditions/`. The fixture set contains only the manifests needed for that test (a `game.yaml`, a `character_config.yaml`, and the specific `CustomCondition` manifest under test), keeping the fixture set narrow.

```python
def test_loader_rejects_circular_custom_condition() -> None:
    """The full loader pipeline raises ContentLoadError on a circular CustomCondition chain."""
    from oscilla.engine.loader import load_content
    import pytest
    with pytest.raises(ContentLoadError, match="circular reference"):
        load_content(Path("tests/fixtures/content/custom-conditions-cycle/"))


def test_loader_rejects_dangling_custom_condition_ref() -> None:
    """The full loader pipeline raises ContentLoadError on a dangling type: custom reference."""
    from oscilla.engine.loader import load_content
    import pytest
    with pytest.raises(ContentLoadError, match="unknown CustomCondition"):
        load_content(Path("tests/fixtures/content/custom-conditions-dangling/"))
```

The `make_character_state()` helper used across tier 1 tests is a factory fixture in `tests/engine/conftest.py` (or defined locally in the test file) that constructs a minimal `CharacterState` with configurable stat values.

---

## Risks / Trade-offs

- **`_collect_custom_condition_refs_from_manifest()` is a snapshot of condition-bearing fields.** If a new manifest kind or a new condition-bearing field is added to an existing kind in the future, the collector must be updated. This is the same maintenance pattern as the existing `_collect_quest_stage_conditions_from_manifest()` and `_collect_archetype_refs_from_manifest()` helpers — it is an accepted cost of the architecture.
- **No cross-package composition.** `type: custom` can only reference `CustomCondition` manifests within the same loaded content package. This is correct for the current single-package-per-game model; it would need revisiting if package composition is ever introduced.
- **DFS is recursive.** For deeply nested `CustomCondition` chains the Python call stack could overflow in pathological cases. In practice, a condition chain deep enough to hit Python's default recursion limit (~1000) would be an authoring error in its own right; the risk is negligible for real content packages.
- **Promoting `character_stat (stat_source: effective)` and `skill` from `LoadWarning` to `LoadError` is a breaking change** for content packages currently using these patterns in passive effects. However, the existing warning already flagged these cases as non-functional (the conditions silently evaluated to `False`), so any well-maintained package should have zero occurrences. Any package that is broken by this change was already silently broken before.
- **`_validate_passive_effect_conditions()` is a new maintenance surface.** If additional re-entrant condition types are added in the future, the banned-type list inside this validator (and inside the transitive `CustomConditionRef` resolver) must be updated. This is documented inline in the function so future developers know where to look.
