## Context

Adventures are currently player-driven: the player navigates to a region → location → adventure pool. There is no mechanism for the engine to automatically fire an adventure in response to a lifecycle event. The proposal adds a **trigger system** that lets content authors in `game.yaml` wire lifecycle events to ordered lists of adventures, with a persistent FIFO queue on `CharacterState` draining those adventures at defined safe points in the game loop.

The key files touched are:

| File | Role |
|---|---|
| `oscilla/engine/models/game.py` | `GameSpec` gains `triggers` and `trigger_adventures` |
| `oscilla/engine/models/adventure.py` | New `EmitTriggerEffect` type and `Effect` union update |
| `oscilla/engine/character.py` | `CharacterState` gains `pending_triggers: List[str]` |
| `oscilla/engine/registry.py` | `ContentRegistry` gains `trigger_index: Dict[str, List[str]]` |
| `oscilla/engine/loader.py` | Load-time validation of trigger keys and custom trigger names |
| `oscilla/engine/steps/effects.py` | New `emit_trigger` effect handler |
| `oscilla/engine/session.py` | `drain_trigger_queue()` + detection point calls |
| `oscilla/models/character_iteration.py` | New `CharacterIterationPendingTrigger` table |
| `db/versions/` | Migration creating `character_iteration_pending_triggers` table |
| `oscilla/services/character.py` | `pending_triggers` loaded from `pending_trigger_rows` relationship |
| `oscilla/engine/tui.py` | Drain calls at creation/rejoin and post-adventure |

---

## Goals / Non-Goals

**Goals:**

- Authors wire lifecycle events to adventures entirely by editing `game.yaml` — no Python required.
- All five built-in trigger types work end-to-end: `on_character_create`, `on_level_up`, `on_game_rejoin`, `on_stat_threshold`, `on_outcome_<name>`.
- `emit_trigger` effect fires custom triggers declared in `game.yaml`.
- Queued triggers survive session disconnects (persisted to DB at `adventure_end`).
- Multiple adventures per trigger run in declaration order.
- Existing adventures and the `repeatable`/`conditions` system apply to triggered adventures unchanged.
- Max queue depth guard prevents runaway cycles.

**Non-Goals:**

- Region/location-scoped triggers (v2).
- `on_outcome_<custom>` for outcomes not declared in `game.yaml` is a load-time error.
- Triggered adventures do not appear in the adventure pool (they are never selected by the player directly) unless they are tied to a location.
- No interruption of an in-progress adventure — the queue only drains at safe points.

---

## Decisions

### Decision 1: Triggers and adventure wiring live entirely in `game.yaml`

**Rationale:** Centralizing trigger configuration in the game manifest follows the established "author-defined vocabulary" pattern. Adventure manifests remain pure adventure definitions. Splitting the mapping across adventure files would make it harder for authors to see at a glance what fires when.

**Alternative considered:** A `triggers:` block on the `AdventureSpec` itself (like the roadmap's original sketch). Rejected because it decentralizes the wiring: understanding what fires when requires scanning every adventure file.

### Decision 2: `on_outcome_<name>` as a generalized outcome trigger family

**Rationale:** A single consistent prefix (`on_outcome_`) covers all three built-in outcomes and any custom outcome declared in `game.yaml`, without requiring separate engine knowledge of each. Load-time validation catches misspellings.

**Alternative considered:** Separate `on_defeat`, `on_flee`, `on_completed` names. Rejected because custom outcomes would require a separate mechanism and authors would need to learn two syntaxes.

### Decision 3: FIFO `pending_triggers: List[str]` on `CharacterState`, persisted as a dedicated table

**Rationale:** Queuing on `CharacterState` is consistent with how other runtime state is managed. The `CharacterIterationPendingTrigger` table follows the same pattern used for milestones, skills, quests, and every other multi-valued character state — an explicit composite-PK table with a FK to `character_iterations`. JSON columns are prohibited by project rules: they lose the ability to query/index individual values and make the schema opaque. The `position` integer column preserves FIFO order. Triggers survive disconnects by being persisted at `adventure_end`.

**Alternative considered:** A JSON column on `character_iterations`. Rejected — JSON columns are explicitly against project policy; the table is the correct tool.

### Decision 4: Queue drained by `GameSession.drain_trigger_queue()` at two session points

Two drain points:

- **Drain A**: immediately after the character is loaded or created (handles `on_character_create` and `on_game_rejoin`)
- **Drain B**: after every call to `session.run_adventure()` returns (handles `on_level_up`, `on_outcome_*`, `on_stat_threshold`, `emit_trigger`)

**Rationale:** These are the only "safe" points — no adventure is currently running, no pipeline state is in flight. Draining mid-adventure would require complex interruption logic.

**Alternative considered:** A single drain point after every adventure. Rejected because `on_character_create` and `on_game_rejoin` would never drain before the player sees the world map.

### Decision 5: `on_game_rejoin` uses `characters.updated_at` as last-activity timestamp

`characters.updated_at` is already touched at every `adventure_end` by `touch_character_updated_at()`. The absence threshold (`absence_hours`) is declared on the `on_game_rejoin` entry in `game.yaml`. At session load, the difference between now and `updated_at` is compared to the threshold.

**Alternative considered:** A dedicated `last_played_at` column. Rejected — `updated_at` already serves this purpose correctly.

### Decision 6: `on_stat_threshold` detection in `_apply_stat_change` and `_apply_stat_set`

After every stat mutation, the effect handler checks all thresholds registered for that stat name in `registry.trigger_index`. A threshold fires if the new value meets `>= threshold` and the old value was `< threshold` (upward crossing only in v1 — authors use conditions to gate re-firing).

**Alternative considered:** Polling stat thresholds at drain time. Rejected — a stat might cross and recross between drain points, making the detection unreliable.

### Decision 7: Max queue depth guard — configurable in `game.yaml`, default 6

`GameTriggers` exposes `max_trigger_queue_depth: int` (default `6`, minimum `1`). If `len(pending_triggers) >= max_trigger_queue_depth` when a new trigger would be appended, the append is skipped and a `logger.warning` is emitted. This prevents runaway `emit_trigger` cycles from hanging the session indefinitely.

A default of 6 is intentionally conservative — it is high enough to cover legitimate multi-step trigger chains (e.g. `on_character_create` + `on_level_up` × 3 + two custom events) while making accidental cycles immediately obvious in logs rather than silently processing dozens of adventures. Authors with complex chains can raise the limit in `game.yaml`.

---

## Schema Changes

### `game.yaml` additions

```python
# Before (oscilla/engine/models/game.py)
class GameSpec(BaseModel):
    displayName: str
    description: str = ""
    xp_thresholds: List[int] = Field(min_length=1)
    hp_formula: HpFormula
    item_labels: List[ItemLabelDef] = []
    passive_effects: List[PassiveEffect] = []
    outcomes: List[str] = Field(default_factory=list)
    season_hemisphere: Literal["northern", "southern"] = "northern"
    timezone: str | None = None
    time: GameTimeSpec | None = None
```

```python
# After (oscilla/engine/models/game.py)
from typing import Dict


class StatThresholdTrigger(BaseModel):
    """A stat threshold that fires a named trigger when crossed upward."""

    # The stat name to watch (must match a stat in character_config.yaml).
    stat: str
    # Fires when stat value transitions from < threshold to >= threshold.
    threshold: int
    # The trigger name this entry maps to in trigger_adventures.
    name: str


class GameRejoinTrigger(BaseModel):
    """Configuration for the on_game_rejoin built-in trigger."""

    # Minimum absence in hours before the rejoin trigger fires.
    absence_hours: int = Field(ge=1)


class GameTriggers(BaseModel):
    """All trigger configuration for the game package."""

    # Names of custom triggers that can be emitted via emit_trigger effect.
    # Must be declared here before they can be used — typos caught at load time.
    custom: List[str] = []
    # Configuration for the on_game_rejoin trigger.
    # Absent = on_game_rejoin trigger is never fired even if wired in trigger_adventures.
    on_game_rejoin: GameRejoinTrigger | None = None
    # Named stat threshold triggers. Each entry must have a unique `name`.
    on_stat_threshold: List[StatThresholdTrigger] = []
    # Maximum number of pending_triggers entries allowed before new appends are
    # dropped with a warning. Raise this only if your content requires deep chains.
    max_trigger_queue_depth: int = Field(default=6, ge=1)


class GameSpec(BaseModel):
    displayName: str
    description: str = ""
    xp_thresholds: List[int] = Field(min_length=1)
    hp_formula: HpFormula
    item_labels: List[ItemLabelDef] = []
    passive_effects: List[PassiveEffect] = []
    outcomes: List[str] = Field(default_factory=list)
    season_hemisphere: Literal["northern", "southern"] = "northern"
    timezone: str | None = None
    time: GameTimeSpec | None = None
    # Trigger configuration. Absent = no triggers defined.
    triggers: GameTriggers = Field(default_factory=GameTriggers)
    # Maps trigger name → ordered list of adventure refs to run.
    # Valid keys: on_character_create, on_level_up, on_outcome_<name>,
    #             on_game_rejoin, <threshold.name>, <custom trigger name>.
    # Validated at load time against the known trigger vocabulary.
    trigger_adventures: Dict[str, List[str]] = Field(default_factory=dict)
```

Example `game.yaml` author syntax:

```yaml
spec:
  triggers:
    custom:
      - player_became_hero
    on_game_rejoin:
      absence_hours: 24
    on_stat_threshold:
      - stat: fame
        threshold: 100
        name: fame-cap

  trigger_adventures:
    on_character_create:
      - character-intro
    on_level_up:
      - level-up-scene
    on_outcome_defeated:
      - defeat-recovery-scene
    on_game_rejoin:
      - rejoin-recap
    fame-cap:
      - fame-cap-scene
    player_became_hero:
      - hero-welcome
```

---

## New `EmitTriggerEffect`

```python
# Before (oscilla/engine/models/adventure.py) — Effect union omitting EmitTriggerEffect
Effect = Annotated[
    Union[
        XpGrantEffect,
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
    ],
    Field(discriminator="type"),
]
```

```python
# After (oscilla/engine/models/adventure.py)
class EmitTriggerEffect(BaseModel):
    """Fire a named custom trigger, queuing any registered adventures.

    The trigger name must be declared in game.yaml's triggers.custom list.
    Validated at content load time — unknown names are a load-time error.
    """

    type: Literal["emit_trigger"]
    trigger: str = Field(description="Custom trigger name declared in game.yaml triggers.custom")


Effect = Annotated[
    Union[
        XpGrantEffect,
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
    ],
    Field(discriminator="type"),
]
```

---

## `CharacterState` Changes

```python
# Before (oscilla/engine/character.py) — end of CharacterState fields
    era_started_at_ticks: Dict[str, int] = field(default_factory=dict)
    era_ended_at_ticks: Dict[str, int] = field(default_factory=dict)
```

```python
# After (oscilla/engine/character.py)
    era_started_at_ticks: Dict[str, int] = field(default_factory=dict)
    era_ended_at_ticks: Dict[str, int] = field(default_factory=dict)
    # FIFO queue of trigger names awaiting drain. Appended by detection points
    # and effect handlers; drained in order by GameSession.drain_trigger_queue().
    # Persisted to DB at adventure_end so queued triggers survive reconnects.
    pending_triggers: List[str] = field(default_factory=list)
```

New helper on `CharacterState`:

```python
    def enqueue_trigger(self, trigger_name: str, max_depth: int = 6) -> None:
        """Append a trigger name to the pending queue.

        Silently drops and logs a warning if the queue would reach max_depth,
        preventing infinite emit_trigger cycles. Callers should pass
        registry.game.spec.triggers.max_trigger_queue_depth as max_depth.
        The default of 6 matches GameTriggers.max_trigger_queue_depth's default.
        """
        if len(self.pending_triggers) >= max_depth:
            logger.warning(
                "Trigger queue depth limit (%d) reached; dropping trigger %r. "
                "Check for emit_trigger cycles in your content.",
                max_depth,
                trigger_name,
            )
            return
        self.pending_triggers.append(trigger_name)
```

All callsites that invoke `enqueue_trigger` SHALL pass the game-configured depth:

```python
# Pattern used at every callsite
max_depth = registry.game.spec.triggers.max_trigger_queue_depth
player.enqueue_trigger(trigger_name, max_depth=max_depth)
```

---

## `ContentRegistry` Trigger Index

```python
# After (oscilla/engine/registry.py) — added to ContentRegistry.__init__
    # Built by loader.py after all manifests are registered.
    # trigger_name → ordered list of adventure refs from trigger_adventures.
    trigger_index: Dict[str, List[str]] = field(default_factory=dict)
```

The index is a plain `Dict[str, List[str]]` built once at load time from `game.spec.trigger_adventures` after validation. At runtime, `drain_trigger_queue()` does a simple dict lookup — no manifest scanning at drain time.

---

## Loader Validation

New validation added to `loader.py` after `GameManifest` registration:

```python
def _validate_trigger_adventures(
    game: GameManifest,
    adventures: KindRegistry[AdventureManifest],
) -> List[str]:
    """Return a list of load warning strings for trigger_adventures validation.

    Checks:
    - Each key in trigger_adventures is a known trigger name.
    - Each adventure ref in every list resolves to a registered adventure.
    - emit_trigger names in effects validate against triggers.custom.

    Known trigger names:
      - Built-in lifecycle: on_character_create, on_level_up
      - on_outcome_<name> for every built-in and declared outcome
      - on_game_rejoin (only valid if triggers.on_game_rejoin is configured)
      - <threshold.name> for each entry in triggers.on_stat_threshold
      - Each name in triggers.custom
    """
    warnings: List[str] = []
    spec = game.spec

    # Build allowed trigger key set
    built_in_outcomes = {"completed", "defeated", "fled"}
    all_outcomes = built_in_outcomes | set(spec.outcomes)
    allowed_keys: set[str] = {
        "on_character_create",
        "on_level_up",
    }
    allowed_keys |= {f"on_outcome_{o}" for o in all_outcomes}
    if spec.triggers.on_game_rejoin is not None:
        allowed_keys.add("on_game_rejoin")
    for threshold in spec.triggers.on_stat_threshold:
        allowed_keys.add(threshold.name)
    for custom in spec.triggers.custom:
        allowed_keys.add(custom)

    for trigger_key, adv_refs in spec.trigger_adventures.items():
        if trigger_key not in allowed_keys:
            warnings.append(
                f"trigger_adventures key {trigger_key!r} is not a known trigger name. "
                f"Allowed: {sorted(allowed_keys)}"
            )
        for ref in adv_refs:
            if adventures.get(ref) is None:
                warnings.append(
                    f"trigger_adventures[{trigger_key!r}] references unknown adventure {ref!r}."
                )

    # Duplicate threshold names are an error
    threshold_names = [t.name for t in spec.triggers.on_stat_threshold]
    seen: set[str] = set()
    for name in threshold_names:
        if name in seen:
            warnings.append(
                f"Duplicate on_stat_threshold name {name!r} in game.yaml triggers."
            )
        seen.add(name)

    return warnings
```

```python
def _build_trigger_index(game: GameManifest) -> Dict[str, List[str]]:
    """Build the runtime lookup table from trigger_adventures."""
    return dict(game.spec.trigger_adventures)
```

---

## Detection Points

### `on_character_create`

```python
# After (oscilla/engine/session.py) — _create_new_character()
    async def _create_new_character(
        self,
        name: str | None,
        user_id: UUID,
    ) -> "CharacterState":
        """Prompt for a name if not provided, create state, and persist immediately."""
        from oscilla.engine.character import CharacterState

        if name is None:
            name = await self.tui.input_text("Enter your character's name:")

        if self.registry.game is None or self.registry.character_config is None:
            raise RuntimeError("Content registry not properly loaded (missing game or character_config).")

        state = CharacterState.new_character(
            name=name,
            game_manifest=self.registry.game,
            character_config=self.registry.character_config,
        )
        # Queue the on_character_create trigger before the first persist so it
        # survives into the drain call immediately following start().
        if "on_character_create" in self.registry.trigger_index:
            max_depth = self.registry.game.spec.triggers.max_trigger_queue_depth
            state.enqueue_trigger("on_character_create", max_depth=max_depth)

        await save_character(
            session=self.db_session,
            state=state,
            user_id=user_id,
            game_name=self.game_name,
        )
        return state
```

### `on_game_rejoin`

Checked in `start()` on the load path (not creation path):

```python
# After (oscilla/engine/session.py) — in start(), after successful load_character()
        # on_game_rejoin: fire if the player has been absent longer than the configured threshold.
        if state is not None and self.registry.game is not None:
            rejoin_cfg = self.registry.game.spec.triggers.on_game_rejoin
            if rejoin_cfg is not None and "on_game_rejoin" in self.registry.trigger_index:
                # characters.updated_at is touched at adventure_end — reliable last-activity marker.
                last_active = record.updated_at  # CharacterRecord.updated_at (timezone-aware)
                absence = datetime.now(tz=timezone.utc) - last_active
                if absence.total_seconds() >= rejoin_cfg.absence_hours * 3600:
                    max_depth = self.registry.game.spec.triggers.max_trigger_queue_depth
                    state.enqueue_trigger("on_game_rejoin", max_depth=max_depth)
```

### `on_level_up`

```python
# After (oscilla/engine/steps/effects.py) — in handle_xp_grant_effect(), after levels_gained loop
        for level in levels_gained:
            await tui.show_text(f"[bold]Level up![/bold] You are now level {level}!")
            # Queue once per level gained so multi-level jumps fire the trigger repeatedly.
            player.enqueue_trigger("on_level_up", max_depth=registry.game.spec.triggers.max_trigger_queue_depth)
```

(The `player` reference is already passed to the effect handler. No new parameters needed.)

### `on_outcome_<name>`

```python
# After (oscilla/engine/session.py) — run_adventure(), after outcome returned
        outcome = await pipeline.run(adventure_ref=adventure_ref)

        # Record repeat-control tracking state after each adventure run.
        self._character.adventure_last_completed_on[adventure_ref] = _date.today().isoformat()
        self._character.statistics.record_adventure_outcome(adventure_ref=adventure_ref, outcome=outcome.value)

        # Queue on_outcome_<name> trigger for this adventure's outcome.
        trigger_key = f"on_outcome_{outcome.value}"
        if trigger_key in self.registry.trigger_index:
            max_depth = self.registry.game.spec.triggers.max_trigger_queue_depth
            self._character.enqueue_trigger(trigger_key, max_depth=max_depth)

        return outcome
```

### `on_stat_threshold`

The threshold index is built once by the loader:

```python
# ContentRegistry gains:
    # stat_name → list of (threshold_value, trigger_name) pairs, sorted ascending.
    stat_threshold_index: Dict[str, List[tuple[int, str]]] = field(default_factory=dict)
```

```python
def _build_stat_threshold_index(
    game: GameManifest,
) -> Dict[str, List[tuple[int, str]]]:
    """Build stat→[(threshold, trigger_name)] lookup for detection in effect handlers."""
    index: Dict[str, List[tuple[int, str]]] = {}
    for entry in game.spec.triggers.on_stat_threshold:
        index.setdefault(entry.stat, []).append((entry.threshold, entry.name))
    # Sort ascending so we can check all thresholds on a stat in one pass
    for lst in index.values():
        lst.sort()
    return index
```

Detection in the stat change effect handler:

```python
# After (oscilla/engine/steps/effects.py) — appended to StatChangeEffect and StatSetEffect handlers
        # Check stat thresholds after every stat mutation.
        stat_thresholds = registry.stat_threshold_index.get(stat_name, [])
        for threshold_value, trigger_name in stat_thresholds:
            # Fire on upward crossing only: old < threshold, new >= threshold.
            if old_value < threshold_value <= new_value:
                player.enqueue_trigger(trigger_name, max_depth=registry.game.spec.triggers.max_trigger_queue_depth)
```

`old_value` is captured before the mutation; `new_value` after.

### `emit_trigger` effect handler

```python
# After (oscilla/engine/steps/effects.py) — new case in the match statement
        case EmitTriggerEffect(trigger=trigger_name):
            # The loader verified this name is declared in triggers.custom.
            # If it has no registered adventures, this is a no-op (not an error).
            player.enqueue_trigger(trigger_name, max_depth=registry.game.spec.triggers.max_trigger_queue_depth)
```

---

## `GameSession.drain_trigger_queue()`

```python
# New method on GameSession (oscilla/engine/session.py)
    async def drain_trigger_queue(self) -> None:
        """Drain the player's pending_triggers queue, running each registered adventure.

        Continues until the queue is empty. Newly queued triggers (from emit_trigger
        effects inside triggered adventures) are appended to the back of the same list
        and processed in order — FIFO. The max-depth guard on enqueue_trigger() prevents
        runaway cycles.

        A triggered adventure that does not meet its `requires` condition is skipped
        silently, consistent with how pool adventures are filtered.
        """
        if self._character is None:
            return

        from datetime import date as _date

        while self._character.pending_triggers:
            trigger_name = self._character.pending_triggers.pop(0)
            adventure_refs = self.registry.trigger_index.get(trigger_name, [])

            for adventure_ref in adventure_refs:
                adv_manifest = self.registry.adventures.get(adventure_ref)
                if adv_manifest is None:
                    logger.warning(
                        "Triggered adventure %r not found in registry; skipping.",
                        adventure_ref,
                    )
                    continue

                # Apply conditions gate — same as pool eligibility check.
                from oscilla.engine.conditions import evaluate

                if not evaluate(adv_manifest.spec.requires, self._character, self.registry):
                    logger.debug(
                        "Triggered adventure %r skipped: requires condition not met.",
                        adventure_ref,
                    )
                    continue

                # Apply repeat controls — triggered adventures respect the same rules.
                if not self._character.is_adventure_eligible(
                    adventure_ref=adventure_ref,
                    spec=adv_manifest.spec,
                    today=_date.today(),
                ):
                    logger.debug(
                        "Triggered adventure %r skipped: repeat control not satisfied.",
                        adventure_ref,
                    )
                    continue

                await self.run_adventure(adventure_ref=adventure_ref)
                # run_adventure() already handles repeat-control tracking, outcome recording,
                # and on_outcome_* trigger queuing — chaining works naturally.

        # Persist the (now empty) queue so the drain is visible to a future session.
        await self._on_state_change(state=self._character, event="adventure_end")
```

---

## TUI Integration

```python
# After (oscilla/engine/tui.py) — _run_game(), after session.start() and status panel refresh
                    await session.start()
                    player = session._character
                    if player is None:
                        ...
                        return

                    status_panel.refresh_player(player)
                    self._player = player

                    # Drain A: on_character_create and on_game_rejoin triggers.
                    await session.drain_trigger_queue()
                    status_panel.refresh_player(player)

                    while True:
                        # ... region/location/adventure loop ...
                        outcome = await session.run_adventure(adventure_ref)
                        # Drain B: on_level_up, on_outcome_*, on_stat_threshold, emit_trigger.
                        await session.drain_trigger_queue()
                        message = _OUTCOME_MESSAGES.get(outcome.value, ...)
                        await tui.show_text(message)
                        status_panel.refresh_player(player)
```

---

## Persistence Changes

### Migration

New table `character_iteration_pending_triggers` alongside the existing character-iteration satellite tables:

```python
# db/versions/<hash>_add_pending_triggers_table.py

def upgrade() -> None:
    op.create_table(
        "character_iteration_pending_triggers",
        sa.Column("iteration_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("trigger_name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["iteration_id"],
            ["character_iterations.id"],
        ),
        sa.PrimaryKeyConstraint("iteration_id", "position"),
    )

def downgrade() -> None:
    op.drop_table("character_iteration_pending_triggers")
```

### ORM model

```python
# After (oscilla/models/character_iteration.py) — new class alongside other satellite tables
class CharacterIterationPendingTrigger(Base):
    """One row per queued trigger awaiting drain.

    position preserves FIFO order — rows are loaded ascending by position
    and written with consecutive 0-based positions.
    """

    __tablename__ = "character_iteration_pending_triggers"

    iteration_id: Mapped[UUID] = mapped_column(
        ForeignKey("character_iterations.id"), primary_key=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    trigger_name: Mapped[str] = mapped_column(String, nullable=False)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="pending_trigger_rows"
    )
```

`CharacterIterationRecord` gains the back-reference:

```python
    pending_trigger_rows: Mapped[List["CharacterIterationPendingTrigger"]] = relationship(
        "CharacterIterationPendingTrigger",
        back_populates="iteration",
        order_by="CharacterIterationPendingTrigger.position",
        cascade="all, delete-orphan",
    )
```

### `load_character` service

```python
# After (oscilla/services/character.py) — in _build_character_state(), reading pending_triggers
    # Rows are already ordered ascending by position via the relationship order_by.
    state.pending_triggers = [
        row.trigger_name for row in iteration.pending_trigger_rows
    ]
```

### Persistence in `_persist_diff`

The pending trigger queue is replaced atomically at `adventure_end`: delete all existing rows for the iteration, then insert new rows with 0-based positions.

```python
# After (oscilla/engine/session.py) — in _persist_diff(), inside the adventure_end block
        if event == "adventure_end":
            ...
            # Replace the pending trigger queue atomically.
            last_pending = last.pending_triggers if last is not None else []
            if state.pending_triggers != last_pending:
                await self.db_session.execute(
                    delete(CharacterIterationPendingTrigger).where(
                        CharacterIterationPendingTrigger.iteration_id == iteration_id
                    )
                )
                for position, trigger_name in enumerate(state.pending_triggers):
                    self.db_session.add(
                        CharacterIterationPendingTrigger(
                            iteration_id=iteration_id,
                            position=position,
                            trigger_name=trigger_name,
                        )
                    )
```

---

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| `emit_trigger` cycle causes infinite loop | Max queue depth guard (configurable, default 6) with warning log; authors can raise the limit in `game.yaml` for complex chains |
| `on_stat_threshold` fires multiple times if stat bounces up and down | Authors use `repeatable: false` or `conditions:` on the triggered adventure; the engine does not dedup threshold crossings |
| `on_game_rejoin` fires on the very first session if `characters.updated_at` is close to creation time | Characters are created with `updated_at` set to creation time; absence check compares against threshold — unlikely to fire on first session unless threshold is very small |
| Triggered adventure chain is long, making session startup slow | No technical limit on chain depth other than queue guard; a very long chain of non-repeatable adventures drains once and the problem self-resolves |
| No pending trigger rows in DB for characters created before migration | The relationship defaults to an empty list when no rows exist — no special handling needed for pre-migration characters |

---

## Migration Plan

1. Generate and apply the Alembic migration creating the `character_iteration_pending_triggers` table.
2. No data migration needed — characters with no rows in the new table load with an empty queue, which is the correct starting state.
3. Deploy engine changes. No rollback concerns — existing characters simply have no queued triggers on first load after migration.
4. Rollback: drop the table via the `downgrade()` path; revert code. No meaningful data loss (the table only contains transient in-flight queue state).

---

## Documentation Plan

### Author documentation

| Document | Audience | Topics |
|---|---|---|
| `docs/authors/game-configuration.md` | Content authors | New `triggers` and `trigger_adventures` blocks in `game.yaml`; all trigger type names and their meaning; `on_stat_threshold` syntax; `on_game_rejoin` `absence_hours` field; `on_outcome_<name>` family; `custom` trigger names; multiple-adventure ordering; the condition/repeat-control system applies to triggered adventures |
| `docs/authors/effects.md` | Content authors | New `emit_trigger` effect: field definitions, validation rules, example YAML, note that the trigger name must appear in `game.yaml triggers.custom` |
| `docs/authors/adventures.md` | Content authors | Note that triggered adventures use the same manifest structure; cross-ref to game-configuration.md for wiring syntax; note that `repeatable`/`max_completions`/`cooldown_*` and `requires` apply to triggered adventures exactly as they do to pool adventures |

### Developer documentation

| Document | Audience | Topics |
|---|---|---|
| `docs/dev/game-engine.md` | Engine developers | Trigger queue lifecycle (append → persist → drain); detection points for each trigger type and where they live in the code; `ContentRegistry.trigger_index` and `stat_threshold_index` build process; `drain_trigger_queue()` algorithm and FIFO semantics; max-depth guard; interaction with `is_adventure_eligible()` and the condition evaluator |

---

## Testing Philosophy

### Unit tests — `tests/engine/test_triggers.py`

Test the detection point logic, queue mechanics, and drain behavior in isolation using minimal fixture content (no `content/` directory).

**Fixtures required:**

```python
# tests/engine/test_triggers.py

from dataclasses import field
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import AdventureManifest, AdventureSpec, NarrativeStep
from oscilla.engine.models.game import (
    GameManifest,
    GameRejoinTrigger,
    GameSpec,
    GameTriggers,
    HpFormula,
    StatThresholdTrigger,
)
from oscilla.engine.registry import ContentRegistry


def _make_game_manifest(
    trigger_adventures: Dict[str, List[str]] | None = None,
    custom_triggers: List[str] | None = None,
    on_game_rejoin: GameRejoinTrigger | None = None,
    on_stat_threshold: List[StatThresholdTrigger] | None = None,
) -> GameManifest:
    """Build a minimal GameManifest for trigger tests."""
    return GameManifest(
        apiVersion="game/v1",
        kind="Game",
        metadata=MagicMock(name="test-game"),
        spec=GameSpec(
            displayName="Test Game",
            xp_thresholds=[100, 200, 400],
            hp_formula=HpFormula(base_hp=20, hp_per_level=5),
            triggers=GameTriggers(
                custom=custom_triggers or [],
                on_game_rejoin=on_game_rejoin,
                on_stat_threshold=on_stat_threshold or [],
            ),
            trigger_adventures=trigger_adventures or {},
        ),
    )


def _make_adventure_manifest(name: str) -> AdventureManifest:
    """Build a minimal one-step adventure manifest."""
    return AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=MagicMock(name=name),
        spec=AdventureSpec(
            displayName=name,
            steps=[NarrativeStep(type="narrative", text="Test")],
        ),
    )
```

**Test: enqueue respects max depth guard**

```python
def test_enqueue_trigger_max_depth() -> None:
    """enqueue_trigger drops new entries once the queue reaches max_depth."""
    state = CharacterState(
        character_id=__import__("uuid").uuid4(),
        name="test",
        character_class=None,
        level=1,
        xp=0,
        hp=20,
        max_hp=20,
        iteration=0,
        current_location=None,
    )
    max_depth = 3  # use a small value to keep the test fast and obvious
    for i in range(max_depth):
        state.enqueue_trigger(f"trigger_{i}", max_depth=max_depth)
    assert len(state.pending_triggers) == max_depth
    state.enqueue_trigger("overflow", max_depth=max_depth)
    assert len(state.pending_triggers) == max_depth  # still at limit, not limit+1
```

**Test: on_level_up enqueues once per level**

```python
def test_on_level_up_enqueues_per_level() -> None:
    """Each level gained from add_xp enqueues on_level_up once."""
    state = CharacterState(
        character_id=__import__("uuid").uuid4(),
        name="test",
        character_class=None,
        level=1,
        xp=0,
        hp=20,
        max_hp=20,
        iteration=0,
        current_location=None,
    )
    # Simulate two levels gained (thresholds: [100, 200])
    levels_gained, _ = state.add_xp(amount=250, xp_thresholds=[100, 200], hp_per_level=5)
    assert len(levels_gained) == 2
    # The effect handler enqueues once per level — simulate that here
    for _ in levels_gained:
        state.enqueue_trigger("on_level_up")
    assert state.pending_triggers.count("on_level_up") == 2
```

**Test: stat threshold fires on upward crossing only**

```python
def test_stat_threshold_upward_crossing_only() -> None:
    """Threshold trigger enqueues on upward crossing; not on downward."""
    thresholds: List[tuple[int, str]] = [(100, "fame-cap")]

    def _check_threshold(player: CharacterState, stat_name: str, old_val: int, new_val: int) -> None:
        """Simulate the detection logic from the effect handler."""
        for threshold_value, trigger_name in thresholds:
            if old_val < threshold_value <= new_val:
                player.enqueue_trigger(trigger_name)

    state = CharacterState(
        character_id=__import__("uuid").uuid4(),
        name="test",
        character_class=None,
        level=1, xp=0, hp=20, max_hp=20, iteration=0, current_location=None,
    )
    state.stats["fame"] = 99

    # Upward crossing: 99 → 101
    _check_threshold(state, "fame", 99, 101)
    assert state.pending_triggers == ["fame-cap"]

    # No re-fire: 101 → 110 (already past threshold)
    _check_threshold(state, "fame", 101, 110)
    assert state.pending_triggers == ["fame-cap"]  # no new entry

    # Downward: 110 → 50 (no fire on downward)
    _check_threshold(state, "fame", 110, 50)
    assert state.pending_triggers == ["fame-cap"]  # still just one

    # Re-arm via repeatable adventure: upward again 50 → 105
    _check_threshold(state, "fame", 50, 105)
    assert state.pending_triggers == ["fame-cap", "fame-cap"]  # fires again
```

**Test: drain skips ineligible adventures**

```python
@pytest.mark.asyncio
async def test_drain_skips_ineligible() -> None:
    """drain_trigger_queue skips adventures whose requires condition is not met."""
    from oscilla.engine.models.base import Condition
    from oscilla.engine.models.adventure import AdventureSpec

    adv_spec = AdventureSpec(
        displayName="gated",
        steps=[NarrativeStep(type="narrative", text="x")],
        requires=Condition(type="level", value=99),  # never met at level 1
    )
    adv = AdventureManifest(
        apiVersion="game/v1", kind="Adventure",
        metadata=MagicMock(name="gated-adv"),
        spec=adv_spec,
    )

    registry = ContentRegistry()
    registry.trigger_index = {"on_level_up": ["gated-adv"]}
    registry.adventures.register(adv)

    mock_tui = AsyncMock()
    state = CharacterState(
        character_id=__import__("uuid").uuid4(),
        name="test", character_class=None,
        level=1, xp=0, hp=20, max_hp=20, iteration=0, current_location=None,
    )
    state.pending_triggers = ["on_level_up"]

    # Inject state + mock session
    session = MagicMock()
    session._character = state
    session.registry = registry
    session.run_adventure = AsyncMock()
    session._on_state_change = AsyncMock()

    from oscilla.engine.session import GameSession
    await GameSession.drain_trigger_queue(session)

    # No adventure should have run
    session.run_adventure.assert_not_called()
    assert state.pending_triggers == []
```

### Integration tests — `tests/engine/test_trigger_integration.py`

Full end-to-end pipeline tests using the `MockTUI` fixture from `conftest.py`.

```python
# Complete stub required alongside integration tests:
class MockTUI:
    """Minimal TUICallbacks implementor for pipeline/session integration tests."""

    def __init__(self, choices: List[int] | None = None) -> None:
        self._choices = list(choices or [])
        self.texts: List[str] = []

    async def show_text(self, text: str) -> None:
        self.texts.append(text)

    async def show_menu(self, prompt: str, options: List[str]) -> int:
        if self._choices:
            return self._choices.pop(0)
        return 1

    async def wait_for_ack(self) -> None:
        pass

    async def show_combat_round(self, *args: object, **kwargs: object) -> None:
        pass

    async def input_text(self, prompt: str) -> str:
        return "Test Character"

    async def show_skill_menu(self, *args: object, **kwargs: object) -> None:
        pass
```

**Test: on_character_create queues and drains before game loop**

```python
@pytest.mark.asyncio
async def test_on_character_create_fires_before_game_loop(
    db_session: AsyncSession,
) -> None:
    """on_character_create trigger adventure runs before the player enters the world."""
    from tests.fixtures.content.trigger_tests import build_trigger_test_registry

    registry = build_trigger_test_registry(
        trigger_adventures={"on_character_create": ["welcome-adventure"]},
    )
    tui = MockTUI()
    async with GameSession(
        registry=registry, tui=tui, db_session=db_session, game_name="test"
    ) as session:
        await session.start()
        # The on_character_create adventure should have been drained by start() → drain_trigger_queue()
        assert any("welcome" in t.lower() for t in tui.texts), (
            "Welcome adventure narrative should appear before game loop"
        )
        assert session._character.pending_triggers == []
```

### Loader validation tests — `tests/engine/test_trigger_loader_validation.py`

```python
def test_unknown_trigger_key_is_load_warning() -> None:
    """A trigger_adventures key that is not a valid trigger name produces a load warning."""
    game = _make_game_manifest(trigger_adventures={"on_mistyped_event": ["some-adv"]})
    adv = _make_adventure_manifest("some-adv")
    registry = ContentRegistry()
    registry.adventures.register(adv)
    warnings = _validate_trigger_adventures(game=game, adventures=registry.adventures)
    assert any("on_mistyped_event" in w for w in warnings)


def test_unknown_adventure_ref_is_load_warning() -> None:
    """A trigger_adventures value referencing a non-existent adventure produces a warning."""
    game = _make_game_manifest(trigger_adventures={"on_level_up": ["no-such-adv"]})
    registry = ContentRegistry()
    warnings = _validate_trigger_adventures(game=game, adventures=registry.adventures)
    assert any("no-such-adv" in w for w in warnings)


def test_on_outcome_custom_valid_when_declared() -> None:
    """on_outcome_<custom> is valid when the outcome is declared in game.yaml."""
    game = GameManifest(
        apiVersion="game/v1", kind="Game",
        metadata=MagicMock(name="g"),
        spec=GameSpec(
            displayName="g", xp_thresholds=[100], hp_formula=HpFormula(base_hp=20, hp_per_level=5),
            outcomes=["discovered"],
            trigger_adventures={"on_outcome_discovered": ["discovery-adv"]},
        ),
    )
    adv = _make_adventure_manifest("discovery-adv")
    registry = ContentRegistry()
    registry.adventures.register(adv)
    warnings = _validate_trigger_adventures(game=game, adventures=registry.adventures)
    assert warnings == []


def test_on_outcome_unknown_is_load_warning() -> None:
    """on_outcome_<name> for an undeclared outcome produces a load warning."""
    game = _make_game_manifest(trigger_adventures={"on_outcome_discovered": ["disc-adv"]})
    adv = _make_adventure_manifest("disc-adv")
    registry = ContentRegistry()
    registry.adventures.register(adv)
    warnings = _validate_trigger_adventures(game=game, adventures=registry.adventures)
    assert any("on_outcome_discovered" in w for w in warnings)
```

---

## Testlandia Integration

All testlandia content lives under `content/testlandia/`. New files are added; no existing files are structurally modified (only `game.yaml` gains the `triggers` / `trigger_adventures` blocks).

### Files to create

| File | Purpose |
|---|---|
| `content/testlandia/game.yaml` | Add `triggers` + `trigger_adventures` blocks |
| `content/testlandia/adventures/triggered/test-character-intro.yaml` | `on_character_create` demo |
| `content/testlandia/adventures/triggered/test-level-up-scene.yaml` | `on_level_up` demo |
| `content/testlandia/adventures/triggered/test-defeat-recovery.yaml` | `on_outcome_defeated` demo |
| `content/testlandia/adventures/triggered/test-threshold-scene.yaml` | `on_stat_threshold` demo |
| `content/testlandia/adventures/triggered/test-custom-trigger-scene.yaml` | `emit_trigger` demo |
| `content/testlandia/adventures/triggered/test-rejoin-scene.yaml` | `on_game_rejoin` demo |

### `game.yaml` additions

```yaml
triggers:
  custom:
    - test-custom-event
  on_game_rejoin:
    absence_hours: 1    # short threshold so QA testers can trigger it within a session break
  on_stat_threshold:
    - stat: gold        # testlandia 'gold' integer stat — convenient for QA since gold changes frequently
      threshold: 50
      name: test-threshold-reached

trigger_adventures:
  on_character_create:
    - test-character-intro
  on_level_up:
    - test-level-up-scene
  on_outcome_defeated:
    - test-defeat-recovery
  on_game_rejoin:
    - test-rejoin-scene
  test-threshold-reached:
    - test-threshold-scene
  test-custom-event:
    - test-custom-trigger-scene
```

### `test-character-intro.yaml`

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: test-character-intro
spec:
  displayName: "Welcome to Testlandia"
  repeatable: false
  steps:
    - type: choice
      prompt: "Choose a starting bonus:"
      options:
        - label: "Extra gold (+10)"
          effects:
            - type: stat_change
              stat: gold
              amount: 10
        - label: "Extra strength (+1)"
          effects:
            - type: stat_change
              stat: strength
              amount: 1
    - type: narrative
      text: "Your adventure begins."
```

### `test-level-up-scene.yaml`

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: test-level-up-scene
spec:
  displayName: "Level Up!"
  steps:
    - type: narrative
      text: "You feel stronger. Your level has increased!"
      effects:
        - type: stat_change
          stat: gold
          amount: 5
```

### `test-defeat-recovery.yaml`

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: test-defeat-recovery
spec:
  displayName: "Recovery"
  steps:
    - type: narrative
      text: "You wake up bruised but alive. Someone carried you to safety."
      effects:
        - type: heal
          amount: full
```

### `test-threshold-scene.yaml`

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: test-threshold-scene
spec:
  displayName: "Threshold Reached"
  repeatable: false
  steps:
    - type: narrative
      text: "A tracker stat has crossed its threshold. This scene fires exactly once."
      effects:
        - type: milestone_grant
          milestone: test-threshold-fired
```

### `test-custom-trigger-scene.yaml`

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: test-custom-trigger-scene
spec:
  displayName: "Custom Trigger Fired"
  steps:
    - type: narrative
      text: "A custom emit_trigger event was received and routed correctly."
```

### `test-rejoin-scene.yaml`

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: test-rejoin-scene
spec:
  displayName: "Welcome Back"
  steps:
    - type: narrative
      text: "You've been away for a while. The world has continued without you."
```

### Manual QA steps

1. Start a new testlandia game → `test-character-intro` should fire immediately before the region menu appears.
2. Complete enough adventures to level up → `test-level-up-scene` fires after the level-up notification.
3. Lose a combat (`on_outcome_defeated`) → `test-defeat-recovery` fires with a heal.
4. Repeatedly gain gold via testlandia adventures until gold reaches 50 → `test-threshold-scene` fires once, then never again (repeatable: false).
5. Trigger an adventure that contains `emit_trigger: test-custom-event` → `test-custom-trigger-scene` fires immediately afterward.
6. Close the game, wait ≥1 hour (or temporarily set `absence_hours: 0` for testing), reopen → `test-rejoin-scene` fires before the region menu.

---

## Open Questions

None outstanding — all design decisions were resolved during the exploration phase.
