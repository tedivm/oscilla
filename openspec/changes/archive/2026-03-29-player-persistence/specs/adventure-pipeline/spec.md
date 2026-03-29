## ADDED Requirements

### Requirement: Pipeline accepts an optional PersistCallback

`AdventurePipeline.__init__` SHALL accept an `on_state_change: PersistCallback | None = None` parameter. When `None`, no persistence calls are made and the pipeline behaves identically to its pre-persistence behaviour. The `PersistCallback` protocol SHALL be defined in `oscilla/engine/pipeline.py` as:

```python
class PersistCallback(Protocol):
    async def __call__(
        self,
        state: CharacterState,
        event: Literal["step_start", "combat_round", "adventure_end"],
    ) -> None: ...
```

#### Scenario: Pipeline with no callback is unchanged

- **WHEN** `AdventurePipeline` is constructed without `on_state_change`
- **THEN** the pipeline runs to completion without error and no persistence calls are attempted

#### Scenario: Pipeline with callback receives correct events

- **WHEN** `AdventurePipeline` is constructed with a `PersistCallback` and a two-step adventure (narrative, combat) is run
- **THEN** the callback is called with `event="step_start"` before each step and `event="combat_round"` after each combat round and `event="adventure_end"` once after the outcome is resolved

---

### Requirement: Pipeline calls PersistCallback with step_start before each step dispatch

Before dispatching any step handler, the pipeline SHALL call `on_state_change(state, "step_start")` if a callback is registered. This checkpoint captures the current `AdventurePosition.step_index` before the step mutates the character state.

#### Scenario: step_start fires before narrative step

- **WHEN** a narrative step begins
- **THEN** `on_state_change(state, "step_start")` is awaited before `show_text()` is called

---

### Requirement: Pipeline calls PersistCallback with combat_round after each combat round

After each combat round resolution (both character and enemy actions complete), the pipeline SHALL call `on_state_change(state, "combat_round")`. This checkpoint captures the current `step_state` (enemy HP) so a crash mid-combat can be resumed from the last round.

#### Scenario: combat_round fires after each round

- **WHEN** a combat step runs for three rounds before the character wins
- **THEN** `on_state_change(state, "combat_round")` is called three times

---

### Requirement: Pipeline calls PersistCallback with adventure_end after effects are applied

After the adventure outcome is determined and all outcome effects (XP, items, milestones) have been applied to the character, the pipeline SHALL call `on_state_change(state, "adventure_end")`. At this point, `active_adventure` SHALL be set to `None` on the character state before the callback fires.

#### Scenario: adventure_end fires after effects, before returning to caller

- **WHEN** an adventure completes with the COMPLETED outcome
- **THEN** all effects are applied to the character, `active_adventure` is set to None, and `on_state_change(state, "adventure_end")` is awaited before `run()` returns
