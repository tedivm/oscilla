# Design: Content Authoring Expressiveness

## Context

Five gaps in the content authoring language prevent authors from expressing common gameplay mechanics without awkward workarounds. Each item is small in isolation; together they represent a coherent authoring-language improvement with no TUI or architectural changes required.

**Current state before this change:**

| Feature                       | Problem                                                                                                                                     |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Passive effects in adventures | No dedicated step type — authors must fake a single-option combat or choice step to apply automatic effects                                 |
| Repeat controls               | Adventures are implicitly always repeatable; there is no way to mark an adventure as one-shot, add a cooldown, or cap completions           |
| Custom outcome names          | `end_adventure` is locked to `Literal["completed", "defeated", "fled"]`; custom outcome types are impossible; no per-outcome count tracking |
| Quest stage condition         | No condition type can check what stage an active quest is on — authors use milestone proxies which break in multi-path quests               |
| Quest failure                 | Quests can only advance forward; there is no fail condition, no `failed_quests` state, and no way to manually fail a quest via an effect    |

---

## Goals / Non-Goals

**Goals:**

- Add `type: passive` adventure step with optional bypass condition and bypass text
- Add `repeatable`, `max_completions`, `cooldown_days`, `cooldown_adventures` to `AdventureSpec`; enforce in TUI pool selection
- Allow `game.yaml` to declare custom outcome names usable in `end_adventure`; track per-adventure per-outcome counts in player state and DB
- Add `type: quest_stage` condition that evaluates to true when a named quest is active at a specific stage
- Add `fail_condition`, `fail_effects` to `QuestStage`; add `failed_quests` to player state; add `quest_fail` effect type; extend `set_quest` to persist status `"failed"`

**Non-Goals:**

- Quest Progress Panel (TUI change — separate roadmap item)
- In-game time system (calendar is separate roadmap item)
- Adventure-scoped variables (separate roadmap item)
- Database normalization of outcome counts (use existing stats delta pattern)
- Any TUI presentation changes beyond persisting new state

---

## Decisions

### Decision 1 — Passive Event Step

#### Model: `PassiveStep` in `oscilla/engine/models/adventure.py`

```python
class PassiveStep(BaseModel):
    type: Literal["passive"]
    label: str | None = None
    text: str | None = Field(default=None, description="Narrative text shown when the step fires normally.")
    effects: List[Effect] = Field(default_factory=list, description="Effects applied when the step is not bypassed.")
    bypass: Condition | None = Field(default=None, description="If met, skip the normal text and effects entirely.")
    bypass_text: str | None = Field(default=None, description="Shown when bypass condition is met. Omit for silent bypass.")
```

Add `PassiveStep` to the `Step` union alongside existing step types.

#### Handler: new file `oscilla/engine/steps/passive.py`

```python
"""Passive step handler — auto-applies effects with optional bypass."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Awaitable, Callable

from oscilla.engine.conditions import evaluate
from oscilla.engine.models.adventure import AdventureOutcome, PassiveStep
from oscilla.engine.steps.effects import run_effect

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.pipeline import AdventureOutcome, TUICallbacks
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)


async def run_passive(
    step: PassiveStep,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: "TUICallbacks",
    run_outcome_branch: Callable[..., Awaitable["AdventureOutcome"]],
) -> "AdventureOutcome":
    """Execute a passive step.

    1. Evaluate bypass condition (if any).
    2a. If bypassed and bypass_text is set — show bypass_text, skip effects.
    2b. If bypassed and no bypass_text — skip silently.
    3. If not bypassed — show text (if any), then apply all effects in order.
    """
    if step.bypass is not None and evaluate(
        condition=step.bypass, player=player, registry=registry
    ):
        if step.bypass_text:
            await tui.show_text(step.bypass_text)
        return AdventureOutcome.COMPLETED

    if step.text:
        await tui.show_text(step.text)

    for effect in step.effects:
        await run_effect(effect=effect, player=player, registry=registry, tui=tui)

    return AdventureOutcome.COMPLETED
```

#### Register in `oscilla/engine/pipeline.py`

Add a `case PassiveStep(...)` branch in `AdventurePipeline._run_step()` that calls `run_passive()`.

---

### Decision 2 — Adventure Repeat Controls

#### Model changes: `AdventureSpec` in `oscilla/engine/models/adventure.py`

**New fields on `AdventureSpec`:**

```python
class AdventureSpec(BaseModel):
    displayName: str
    description: str = ""
    requires: Condition | None = None
    steps: List[Step]
    # Repeat controls — all optional, all default to unrestricted behavior.
    repeatable: bool = Field(default=True, description="Set False to make this a one-shot adventure.")
    max_completions: int | None = Field(default=None, description="Hard cap on total completions this iteration.")
    cooldown_days: int | None = Field(default=None, description="Calendar days that must pass between runs.")
    cooldown_adventures: int | None = Field(
        default=None, description="Total adventures completed that must pass between runs."
    )
```

`repeatable: false` is treated as sugar for `max_completions: 1` — an adventure with `repeatable: false` is excluded from the pool once `adventures_completed[ref] >= 1`. A `model_validator` raises an error if both `repeatable: false` and `max_completions` are specified on the same adventure.

#### CharacterState additions in `oscilla/engine/character.py`

```python
# Filled on first completion; stores the ISO date when each adventure was last run.
# Used to evaluate cooldown_days constraints.
adventure_last_completed_on: Dict[str, str] = field(default_factory=dict)
# Stores the total adventures_completed count at the time of last run.
# Used to evaluate cooldown_adventures constraints.
adventure_last_completed_at_total: Dict[str, int] = field(default_factory=dict)
```

Existing `statistics.adventures_completed[adventure_ref]` already counts per-adventure completions for this iteration and is used directly for `max_completions` / `repeatable` checks.

#### Eligibility helper in `oscilla/engine/character.py`

```python
def is_adventure_eligible(
    self,
    adventure_ref: str,
    spec: "AdventureSpec",
    today: "date",
) -> bool:
    """Return True if repeat controls allow running this adventure right now.

    Called AFTER the adventure's `requires` condition has already passed.
    """
    completions = self.statistics.adventures_completed.get(adventure_ref, 0)

    # repeatable: false (equivalent to max_completions: 1)
    if not spec.repeatable and completions >= 1:
        return False

    # max_completions hard cap
    if spec.max_completions is not None and completions >= spec.max_completions:
        return False

    # cooldown_days (calendar)
    if spec.cooldown_days is not None:
        last_on_str = self.adventure_last_completed_on.get(adventure_ref)
        if last_on_str is not None:
            from datetime import date as date_t
            last_on = date_t.fromisoformat(last_on_str)
            if (today - last_on).days < spec.cooldown_days:
                return False

    # cooldown_adventures (total completions as a proxy for time)
    if spec.cooldown_adventures is not None:
        last_total = self.adventure_last_completed_at_total.get(adventure_ref)
        if last_total is not None:
            total_now = sum(self.statistics.adventures_completed.values())
            if total_now - last_total < spec.cooldown_adventures:
                return False

    return True
```

#### Pool filtering in `oscilla/engine/tui.py`

**Before:**

```python
eligible = [
    entry
    for entry in location.spec.adventures
    if evaluate(entry.requires, player, registry)
]
```

**After:**

```python
from datetime import date as _date

eligible = [
    entry
    for entry in location.spec.adventures
    if evaluate(entry.requires, player, registry)
    and player.is_adventure_eligible(
        adventure_ref=entry.ref,
        spec=registry.adventures.require(entry.ref, "Adventure").spec,
        today=_date.today(),
    )
]
```

#### Recording completion in `oscilla/engine/session.py`

In `run_adventure()`, after the pipeline completes and before `sync()`, update both new fields on player:

```python
from datetime import date as _date

player.adventure_last_completed_on[adventure_ref] = _date.today().isoformat()
player.adventure_last_completed_at_total[adventure_ref] = sum(
    player.statistics.adventures_completed.values()
)
```

#### DB: new table `character_iteration_adventure_state`

```sql
CREATE TABLE character_iteration_adventure_state (
    iteration_id UUID NOT NULL REFERENCES character_iterations(id),
    adventure_ref VARCHAR NOT NULL,
    last_completed_on DATE,        -- NULL until first completion
    last_completed_at_total INT,   -- NULL until first completion
    PRIMARY KEY (iteration_id, adventure_ref)
);
```

Upserted in `session.sync()` whenever `adventure_last_completed_on` changes. Loaded back at character restore.

---

### Decision 3 — Adventure Outcome Definitions

#### Model change: `GameSpec` in `oscilla/engine/models/game.py`

```python
# Custom outcome names beyond the three engine-internal defaults.
# Authors must declare any outcome used in end_adventure effects that is
# not one of: completed, defeated, fled.
outcomes: List[str] = Field(default_factory=list)
```

#### Model change: `EndAdventureEffect` in `oscilla/engine/models/adventure.py`

**Before:**

```python
class EndAdventureEffect(BaseModel):
    type: Literal["end_adventure"]
    outcome: Literal["completed", "defeated", "fled"] = "completed"
```

**After:**

```python
_BUILTIN_OUTCOMES: frozenset[str] = frozenset({"completed", "defeated", "fled"})

class EndAdventureEffect(BaseModel):
    type: Literal["end_adventure"]
    outcome: str = Field(default="completed", description=(
        "Outcome name. Built-ins: 'completed', 'defeated', 'fled'. "
        "Custom names must be declared in game.yaml outcomes list."
    ))
```

#### Loader validation for custom outcomes

In `oscilla/engine/loader.py`, add a `_validate_outcome_refs()` function in the post-load validation pass. It scans all `EndAdventureEffect` instances across all adventures and confirms that any outcome not in `_BUILTIN_OUTCOMES` is declared in `registry.game.spec.outcomes`.

#### CharacterStatistics additions

```python
# Per-adventure per-outcome completion counts.
# Key: adventure_ref → {outcome_name: count}
adventure_outcome_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)

def record_adventure_outcome(self, adventure_ref: str, outcome: str) -> None:
    if adventure_ref not in self.adventure_outcome_counts:
        self.adventure_outcome_counts[adventure_ref] = {}
    mapping = self.adventure_outcome_counts[adventure_ref]
    mapping[outcome] = mapping.get(outcome, 0) + 1
```

#### Recording in `session.run_adventure()`

After the pipeline returns an outcome, call:

```python
player.statistics.record_adventure_completed(adventure_ref)  # keeps existing total count
player.statistics.record_adventure_outcome(adventure_ref, outcome.value)
```

#### DB persistence

Use the existing `character_iteration_statistics` table and `stat_type` column. Add a new stat_type pattern `"adventure_outcome:{outcome_name}"` — e.g. `adventure_outcome:completed`, `adventure_outcome:fled`. The `increment_statistic` service function's `stat_type` parameter is widened from a `Literal` to `str`.

On load, `session.py` reconstructs `adventure_outcome_counts` from rows where `stat_type` starts with `"adventure_outcome:"`.

---

### Decision 4 — Quest Stage Condition

#### Model: new `QuestStageCondition` in `oscilla/engine/models/base.py`

```python
class QuestStageCondition(BaseModel):
    type: Literal["quest_stage"]
    quest: str = Field(description="Quest manifest name to check.")
    stage: str = Field(description="Expected current stage name.")
```

Add to the `Condition` union.

#### Handler in `oscilla/engine/conditions.py`

```python
case QuestStageCondition(quest=q, stage=s):
    return player.active_quests.get(q) == s
```

#### Loader validation

In `_validate_condition_refs()` (or equivalent), verify:

1. `quest` resolves to a known quest manifest.
2. `stage` matches one of the quest's declared stage names.

---

### Decision 5 — Quest Failure States

#### Model changes in `oscilla/engine/models/quest.py`

**New fields on `QuestStage`:**

```python
class QuestStage(BaseModel):
    name: str
    description: str = ""
    advance_on: Set[str] = set()
    next_stage: str | None = None
    terminal: bool = False
    completion_effects: List["Effect"] = []
    # NEW
    fail_condition: "Condition | None" = None
    fail_effects: List["Effect"] = []
```

Model validator addition: terminal stages must not declare `fail_condition` (they are already resolved; there is nothing left to fail).

#### New effect model: `QuestFailEffect` in `oscilla/engine/models/adventure.py`

```python
class QuestFailEffect(BaseModel):
    type: Literal["quest_fail"]
    quest_ref: str = Field(description="Name of the Quest manifest to fail.")
```

Add to `Effect` union.

#### CharacterState: new `failed_quests` field

```python
failed_quests: Set[str] = field(default_factory=set)
```

Serialized alongside `active_quests` and `completed_quests` in `to_dict()` / `from_dict()`.

#### `quest_engine.py` failure evaluation

In `evaluate_quest_advancements()`, after the stage advancement loop, add a failure pass over all still-active quests:

```python
async def _evaluate_quest_failures(
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: "TUICallbacks",
) -> None:
    """Evaluate fail_conditions for all active quest stages.

    Called after advancement is complete so a newly entered stage can be
    immediately failed if the fail condition is already satisfied.
    """
    from oscilla.engine.steps.effects import run_effect

    for quest_ref in list(player.active_quests.keys()):
        quest_manifest = registry.quests.get(quest_ref)
        if quest_manifest is None:
            continue
        stage_name = player.active_quests[quest_ref]
        stage_map = {s.name: s for s in quest_manifest.spec.stages}
        stage = stage_map.get(stage_name)
        if stage is None or stage.fail_condition is None:
            continue
        if evaluate(condition=stage.fail_condition, player=player, registry=registry):
            player.active_quests.pop(quest_ref)
            player.failed_quests.add(quest_ref)
            display_name = quest_manifest.spec.displayName
            await tui.show_text(f"[bold red]Quest failed: {display_name}[/bold red]")
            for effect in stage.fail_effects:
                await run_effect(effect=effect, player=player, registry=registry, tui=tui)
```

Call `_evaluate_quest_failures()` at the end of `evaluate_quest_advancements()`.

#### `QuestFailEffect` handler in `oscilla/engine/steps/effects.py`

```python
case QuestFailEffect(quest_ref=quest_ref):
    quest_manifest = registry.quests.get(quest_ref)
    if quest_manifest is None:
        logger.error("quest_fail: quest %r not found in registry.", quest_ref)
        await tui.show_text(f"[bold red]Error: quest {quest_ref!r} not found.[/bold red]")
        return
    if quest_ref not in player.active_quests:
        logger.warning("quest_fail: quest %r is not active — no-op.", quest_ref)
        return
    player.active_quests.pop(quest_ref)
    player.failed_quests.add(quest_ref)
    display_name = quest_manifest.spec.displayName
    await tui.show_text(f"[bold red]Quest failed: {display_name}[/bold red]")
    stage_name = player.active_quests.get(quest_ref, "")
    stage_map = {s.name: s for s in quest_manifest.spec.stages}
    stage = stage_map.get(stage_name)
    if stage:
        for effect in stage.fail_effects:
            await run_effect(effect=effect, player=player, registry=registry, tui=tui)
```

Wait — `player.active_quests.pop(quest_ref)` must happen before reading `stage_name`. Correct implementation:

```python
case QuestFailEffect(quest_ref=quest_ref):
    quest_manifest = registry.quests.get(quest_ref)
    if quest_manifest is None:
        logger.error("quest_fail: quest %r not found in registry.", quest_ref)
        await tui.show_text(f"[bold red]Error: quest {quest_ref!r} not found.[/bold red]")
        return
    if quest_ref not in player.active_quests:
        logger.warning("quest_fail: quest %r is not active — no-op.", quest_ref)
        return
    stage_name = player.active_quests.pop(quest_ref)
    player.failed_quests.add(quest_ref)
    display_name = quest_manifest.spec.displayName
    await tui.show_text(f"[bold red]Quest failed: {display_name}[/bold red]")
    stage_map = {s.name: s for s in quest_manifest.spec.stages}
    stage = stage_map.get(stage_name)
    if stage:
        for effect in stage.fail_effects:
            await run_effect(effect=effect, player=player, registry=registry, tui=tui)
```

#### DB persistence

Extend `set_quest()` signature to accept `status: Literal["active", "completed", "failed"]`. In `session.sync()`, add a persistence pass for `failed_quests` parallel to `completed_quests`:

```python
for quest_ref in state.failed_quests - last_failed:
    await set_quest(
        session=db,
        iteration_id=iteration_id,
        quest_ref=quest_ref,
        status="failed",
        stage=None,
    )
```

Load failed quests in `character.py` service from rows where `status == "failed"`.

No migration needed for this table — `status` is already a free-form `VARCHAR` column. The new status value `"failed"` is backward-compatible.

---

## DB Migration Summary

One new migration required. Changes:

1. **New table `character_iteration_adventure_state`**: `(iteration_id, adventure_ref, last_completed_on DATE, last_completed_at_total INT)`. Stores repeat-control tracking state per adventure per iteration.
2. **No schema change needed** for outcome counts (uses existing `character_iteration_statistics` with new `stat_type` values).
3. **No schema change needed** for `failed_quests` (uses existing `character_iteration_quests` with new `status = "failed"` value).

---

## Risks / Trade-offs

| Risk                                                                                                                                                                 | Mitigation                                                                                                  |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `cooldown_adventures` uses total adventures across all locations as the counter, not just adventures at the same location. This is simpler but can surprise authors. | Document clearly in `adventures.md`.                                                                        |
| `increment_statistic` stat_type widened from `Literal` to `str` allows arbitrary strings in the stats table.                                                         | The loader validates outcome names against `game.yaml` before any runtime execution.                        |
| `fail_condition` evaluated on every milestone grant could be expensive for long quest lists.                                                                         | Failure is checked only for active quests; most games will have < 10 active quests at a time.               |
| `end_adventure` outcome is now `str`, breaking type-level exhaustiveness checks.                                                                                     | Loader validates all outcome strings at load time. Runtime uses the string value directly with no matching. |

---

## Documentation Plan

| Document                     | Audience        | Topics                                                                                                                                                                                                                                                                      |
| ---------------------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/authors/adventures.md` | Content authors | Passive step (text, effects, bypass, bypass_text examples); repeat control fields (repeatable, max_completions, cooldown_days, cooldown_adventures, units, reset-on-prestige note); outcome definitions (declare in game.yaml, end_adventure usage, custom outcome example) |
| `docs/authors/quests.md`     | Content authors | Quest stage condition (syntax, worked example); quest failure states (fail_condition, fail_effects, failed_quests state, quest_fail effect, model validator constraints)                                                                                                    |

---

## Testing Philosophy

### Tier 1 — Unit tests (no DB, no TUI)

- `PassiveStep` model validation: text, effects, bypass, bypass_text all accept None/empty
- `is_adventure_eligible()`: all four constraint types independently and in combination
- `QuestStageCondition` evaluation: active quest at matching stage → True; wrong stage → False; quest not active → False
- Failure evaluation: fail_condition met → quest moves to failed_quests; fail_effects run
- `QuestFailEffect` handler: unknown ref → error; not active → warning; active → state change + effects

### Tier 2 — Integration tests (in-memory SQLite)

- Adventure repeat controls persist across `sync()` and reload
- `failed_quests` persists across `sync()` and reload via `status="failed"` in `character_iteration_quests`
- Adventure outcome counts persist via `adventure_outcome:*` stat_type rows

### Fixture constraints

- All test fixtures go in `tests/fixtures/content/` with `test-` prefixed names
- No test may reference `content/` (testlandia or the-example-kingdom)
- Passive step tests construct `PassiveStep` models directly — no YAML loading
