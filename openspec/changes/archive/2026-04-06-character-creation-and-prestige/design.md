## Context

The triggered adventures system shipped `on_character_create`, `on_stat_threshold`, and `emit_trigger` — the exact hooks needed for character creation flows and prestige resets — but neither feature has been wired at the authoring level or documented for content authors. This change activates both.

A secondary issue is an existing naming bug: `PrestigeCountCondition` uses `type: "iteration"` as its YAML discriminator key, while the spec, condition evaluator, and documentation all call it `prestige_count`. This inconsistency exists at a layer authors interact with directly. Fixing it now, before any live content package uses prestige conditions, is nearly free.

**Key files:**

| File | Role |
|---|---|
| `oscilla/engine/character.py` | Rename `iteration` → `prestige_count`; add `prestige_pending: PrestigeCarryForward | None` |
| `oscilla/engine/models/base.py` | Fix `PrestigeCountCondition.type` Literal from `"iteration"` to `"prestige_count"` |
| `oscilla/engine/models/game.py` | Add `PrestigeConfig`, `CharacterCreationDefaults`, and updated `GameSpec` |
| `oscilla/engine/models/adventure.py` | Add `PrestigeEffect` and `SetNameEffect` to the `Effect` union |
| `oscilla/engine/steps/effects.py` | Add `PrestigeEffect` and `SetNameEffect` dispatch handlers |
| `oscilla/engine/templates.py` | Rename `PlayerContext.iteration` → `prestige_count` |
| `oscilla/engine/session.py` | Handle `prestige_pending` at `adventure_end` persist; update `_persist_diff`; use placeholder name in `_create_new_character()` |
| `oscilla/services/character.py` | Update `prestige_character()` to accept carry-forward; add `rename_character()` |
| `docs/authors/adventures.md` | Document `on_character_create` usage with full examples; document `type: set_name` |
| `docs/authors/game-configuration.md` | Document `prestige:` block and `character_creation:` block in `game.yaml` |
| `content/testlandia/` | Character-creation adventure; prestige ceremony adventure; updated `game.yaml` |

---

## Goals / Non-Goals

**Goals:**

- Fix `PrestigeCountCondition.type` YAML key: `"iteration"` → `"prestige_count"`. All refs updated.
- Rename `CharacterState.iteration` → `CharacterState.prestige_count` everywhere.
- Document `on_character_create` for content authors; add testlandia creation adventure.
- Add `prestige:` block to `game.yaml` for carry-forward and pre/post effects.
- Add `PrestigeEffect` (`type: prestige`) to the effect system; dispatch resets in-memory state and defers DB transition to `adventure_end`.
- Adventures can include steps after the `prestige` effect fires — the player sees the reset state immediately in subsequent steps.
- Testlandia demonstrates the full prestige flow end-to-end.

**Non-Goals:**

- Cross-iteration conditions (e.g., "milestone ever reached in any past iteration") — roadmap candidate; deferred.
- Cross-iteration template expressions (e.g., `{{ player.past_iterations | length }}`).
- Cross-iteration effects.
- Item carry-over on prestige — carrying items and equipment across iterations is out of scope here and will be addressed as part of the Inventory Storage roadmap item.
- Player-defined custom pronoun forms at creation time — good roadmap item, no new step type needed now; `set_pronouns` covers built-in and author-defined sets. Author-defined *default* pronouns for biographic games are in scope via `character_creation.default_pronouns` in `game.yaml`.
- TUI character-sheet panel improvements (prestige count in UI) — separate TUI change.
- `--character-name` CLI flag behavior is unchanged: when a name is provided at the CLI, it is used directly and the `type: set_name` effect in the adventure does nothing (the player already has a real name, not a placeholder).

---

## Decisions

### Decision 1: Rename `iteration` → `prestige_count` everywhere authors touch it

The internal DB column `character_iterations.iteration` keeps its name — it is an ordinal row identifier, not a concept authors see. Every Python field and every YAML key seen by content authors adopts `prestige_count`.

**Rationale:** The original `PrestigeCountCondition` type key was `"iteration"` — an implementation detail leaking into the authoring surface. Standardizing on `prestige_count` matches the spec, the roadmap prose, and the intuition that authors care about *how many times they have prestiged*, not the structural row number.

**Migration:** No live content packages use this feature yet (the prestige service function was always unwired). The only changes needed are in code and specs.

### Decision 2: Prestige carry-forward and pre/post effects live in `game.yaml`, not on the effect

Authors declare the prestige configuration once in `game.yaml`:

```yaml
prestige:
  carry_stats: [legacy_power, guild_rank]
  carry_skills: [master-swordplay]
  carry_milestones: [pledged-to-guild]
  pre_prestige_effects:
    - type: stat_change
      stat: legacy_power
      amount: 1
  post_prestige_effects:
    - type: milestone_grant
      name: prestige-veteran
```

The `type: prestige` effect in an adventure has no additional parameters — it simply fires the configured prestige pipeline.

**Rationale:** Prestige carry-forward is a core mechanic declaration, not a per-adventure implementation detail. Authors should not be able to accidentally create two adventures with different carry lists. Placing it in `game.yaml` follows the established design pattern: the game manifest holds the authoritative vocabulary and configuration; adventure manifests describe events. A game that wants no prestige simply omits the `prestige:` block entirely and the effect is unavailable (a hard load error is raised if the effect appears but no `prestige:` block is declared).

**Alternative considered:** Carry-forward as parameters on the `prestige` effect. Rejected — it decentralizes the declaration and creates inconsistency risk if multiple adventures can trigger prestige.

### Decision 3: `prestige_pending` field on `CharacterState` (ephemeral, deferred DB transition)

When the `prestige` effect fires inside an adventure:

1. `pre_prestige_effects` run immediately (grants legacy stats, etc.).
2. Character state is reset in-memory to config defaults.
3. Carried stats and skills are applied to the reset state.
4. `prestige_count` is incremented.
5. `post_prestige_effects` run against the new state.
6. `state.prestige_pending = PrestigeCarryForward(...)` is set.
7. Steps continue as normal — subsequent steps see the new state.

At `adventure_end` in `_persist_diff`, if `prestige_pending` is set:

- `prestige_character(session, character_id, character_config, carry_forward)` is called.
- `self._iteration_id` is updated to the new row's ID.
- `self._last_saved_state = None` to force a full write.
- `state.prestige_pending = None` is cleared.
- Normal diff then writes the reset state to the new iteration.

**Rationale:** Effect handlers operate on `CharacterState` only — they have no access to the DB session. The `adventure_end` persist path in `session.py` is the only correct place to call `prestige_character()`. Deferring to `adventure_end` also ensures mid-adventure `step_start` and `combat_round` persists continue to write to the old iteration (they are effectively skipped while prestige is pending — see below).

**Mid-adventure persists while prestige is pending:** `_persist_diff` for `step_start` and `combat_round` events is skipped when `prestige_pending` is set. The old iteration's data is not corrupted by partial resets. If the game crashes between the prestige step and `adventure_end`, the worst case is the adventure replays from the last checkpoint with the pre-prestige state — acceptable for graceful recovery.

### Decision 4: `prestige` effect is unavailable if no `prestige:` block is declared in `game.yaml`

At content load time, any adventure manifest containing `type: prestige` effects is validated. If `registry.game.spec.prestige` is `None`, a `LoadError` is appended for each offending adventure and the load fails with `ContentLoadError`. Authors must declare a `prestige:` block in `game.yaml` before using `type: prestige` in any adventure. Content packages that do not use `type: prestige` are completely unaffected.

### Decision 5: Character name is collected inside the creation adventure via `SetNameEffect`

The TUI currently blocks on a `tui.input_text()` prompt for the character name before creating the `CharacterRecord`. This prevents name collection from being an authored adventure step, unlike pronoun selection.

**New behavior:** `_create_new_character()` uses a unique placeholder name (`f"new-{uuid4()}"`) when no `--character-name` CLI argument is provided. The character is saved to the DB immediately with the placeholder, and the creation adventure runs. The content author places a `type: set_name` effect in the creation adventure where they want the name prompt to appear. When the effect fires, `tui.input_text()` is called and `state.name` is updated. At the next persist checkpoint, `_persist_diff` detects the name change and calls `rename_character()` to update `CharacterRecord.name` in the DB.

**When `--character-name` is given:** The placeholder step is skipped — the character already has a real name. The `type: set_name` effect detects that `state.name` does not look like a placeholder and skips the prompt, so the adventure flow is unchanged for CLI-driven creation.

**DB constraint:** `CharacterRecord` has a unique constraint on `(user_id, game_name, name)`. `rename_character()` enforces this and raises a descriptive error if the name is already taken.

**Rationale:** This unifies name collection with the rest of the creation flow — name, pronouns, and backstory all happen inside the adventure manifest. No TUI-level prompt changes are needed: `tui.input_text()` is already available to effect handlers.

### Decision 6: `CharacterCreationDefaults` in `game.yaml` for biographic games

Some games have a fixed protagonist — the author names the character ("Protagonist", "Elara") and chooses their pronouns, removing the need for player selection. Adding a `character_creation:` block to `GameSpec` handles this cleanly:

```yaml
character_creation:
  default_name: "Elara"
  default_pronouns: she_her
```

**`default_name`:** When set, `_create_new_character()` uses this value directly instead of the UUID placeholder. Because the value is not a UUID placeholder, `SetNameEffect` detects it as a real name and skips the prompt automatically — no special-casing needed. Authors simply omit the `type: set_name` step from their creation adventure.

**`default_pronouns`:** When set, `new_character()` initializes `CharacterState.pronouns` from this key using `PRONOUN_SETS.get(key, DEFAULT_PRONOUN_SET)`. If the creation adventure also includes a `set_pronouns` step, it overrides the default (the adventure wins). If no `set_pronouns` step is present, the config default stands. The key is validated at load time against known built-in and author-declared pronoun sets.

**Interaction with `--character-name` CLI flag:** The CLI flag always wins over `default_name`. The check order in `_create_new_character()` is: CLI arg → `default_name` → UUID placeholder.

**Rationale:** Authors building biographic or linear-narrative games should not be forced to write a creation adventure with empty choice steps just to skip player input. The game-level config determines defaults; adventure steps are opt-in overrides. This mirrors how the `prestige:` block and `trigger_adventures:` work — declare intent in `game.yaml`, express event flow in adventures.

**Alternative considered:** A `skip_name_prompt:` boolean flag. Rejected — `default_name` is strictly more expressive and covers the same case without a separate skip flag.

---

## Schema Changes

### Fix: `PrestigeCountCondition.type` YAML key

```python
# Before (oscilla/engine/models/base.py)
class PrestigeCountCondition(BaseModel):
    type: Literal["iteration"]
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    eq: int | None = None
    mod: ModComparison | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "PrestigeCountCondition":
        if all(v is None for v in [self.gt, self.gte, self.lt, self.lte, self.eq, self.mod]):
            raise ValueError("iteration condition must specify at least one of: gt, gte, lt, lte, eq, mod")
        return self
```

```python
# After (oscilla/engine/models/base.py)
class PrestigeCountCondition(BaseModel):
    type: Literal["prestige_count"]
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    eq: int | None = None
    mod: ModComparison | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "PrestigeCountCondition":
        if all(v is None for v in [self.gt, self.gte, self.lt, self.lte, self.eq, self.mod]):
            raise ValueError("prestige_count condition must specify at least one of: gt, gte, lt, lte, eq, mod")
        return self
```

### `game.yaml` additions: `PrestigeConfig`

```python
# After (oscilla/engine/models/game.py) — new classes before GameSpec
from oscilla.engine.models.adventure import Effect  # avoids circular; use TYPE_CHECKING if needed


class PrestigeConfig(BaseModel):
    """Author-defined prestige reset behavior for the game package.

    Declared once in game.yaml under the `prestige:` key.
    Absent = prestige is not available; any adventure using type: prestige
    will raise a ContentLoadError at content load time.
    """

    # Stats (by name) whose current value is copied from the old iteration
    # to the new iteration AFTER config defaults are applied.
    carry_stats: set[str] = Field(default_factory=set)
    # Skill refs whose membership in known_skills carries to the new iteration.
    carry_skills: set[str] = Field(default_factory=set)
    # Milestone refs that are re-granted on the new iteration if they were set
    # on the old iteration at the time of prestige.
    carry_milestones: set[str] = Field(default_factory=set)
    # Effects that run against the OLD character state just before the reset.
    # Use this to grant legacy bonuses (stat_change, milestone_grant, etc.).
    pre_prestige_effects: List["Effect"] = []
    # Effects that run against the NEW (reset) character state immediately
    # after the reset and carry-forward are applied.
    post_prestige_effects: List["Effect"] = []
```

```python
# After (oscilla/engine/models/game.py) — GameSpec gains prestige field
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
    triggers: GameTriggers = Field(default_factory=GameTriggers)
    trigger_adventures: Dict[str, List[str]] = Field(default_factory=dict)
    # Optional character creation defaults. Absent = UUID placeholder name + they/them pronouns.
    character_creation: CharacterCreationDefaults | None = None
    # Optional prestige configuration. Absent = prestige is disabled.
    prestige: PrestigeConfig | None = None
```

### `CharacterCreationDefaults` model

```python
# After (oscilla/engine/models/game.py) — new class before PrestigeConfig

class CharacterCreationDefaults(BaseModel):
    """Author-declared defaults for newly created characters.

    Use this in biographic or linear-narrative games where the protagonist
    has a fixed identity — no player selection steps are needed.

    default_name:
        Used as the character's name instead of the UUID placeholder in
        _create_new_character(). Because it is not a UUID placeholder,
        SetNameEffect detects it as a real name and skips the input prompt
        automatically. Authors simply omit the type: set_name step from
        their creation adventure.

    default_pronouns:
        Initial pronoun-set key (e.g. 'she_her', 'he_him', 'they_them').
        new_character() uses this to initialize CharacterState.pronouns
        instead of the system default (they/them). A set_pronouns step in
        the creation adventure still overrides it if present.
        Validated at load time against built-in and author-declared sets.
    """

    default_name: str | None = Field(
        default=None,
        description="Fixed protagonist name. Bypasses the SetNameEffect prompt.",
    )
    default_pronouns: str | None = Field(
        default=None,
        description="Initial pronoun-set key (e.g. 'she_her'). Overrides the system default (they/them).",
    )
```



### `PrestigeEffect` in the Effect union

```python
# After (oscilla/engine/models/adventure.py) — new class before Effect union

class PrestigeEffect(BaseModel):
    """Reset the character to a new iteration using the prestige config from game.yaml.

    Runs pre_prestige_effects, resets state to character_config defaults, applies
    carry_stats and carry_skills, increments prestige_count, then runs
    post_prestige_effects. Steps after this effect in the same adventure see
    the reset state immediately. The DB transition happens at adventure_end.

    Requires `prestige:` to be declared in game.yaml. If absent,
    raises a ContentLoadError at content load time.
    """

    type: Literal["prestige"]
```

The `Effect` union gains `PrestigeEffect`:

```python
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
        PrestigeEffect,          # ← new
        SetNameEffect,           # ← new
    ],
    Field(discriminator="type"),
]
```

### `SetNameEffect` model

```python
# After (oscilla/engine/models/adventure.py) — new class alongside PrestigeEffect

class SetNameEffect(BaseModel):
    """Prompt the player for a character name and update CharacterState.name.

    Used inside character-creation adventures to collect the player's chosen name
    as an authored step, matching the pattern established by SetPronounsEffect.

    When the character already has a real name (e.g. --character-name was given
    at the CLI), this effect checks whether the current name looks like a
    placeholder (starts with "new-" and is a valid UUID suffix). If not a
    placeholder, the prompt is skipped and the existing name is kept.

    The prompt field is optional; if omitted it defaults to "What is your name?".
    """

    type: Literal["set_name"]
    prompt: str = "What is your name?"
```

### `CharacterState` changes

```python
# Before (oscilla/engine/character.py) — relevant fields
    # 0-based prestige run number; maps to character_iterations.iteration
    iteration: int
```

```python
# After (oscilla/engine/character.py) — renamed field + ephemeral prestige signal
    # Number of times the character has prestiged. Mirrors character_iterations.iteration.
    prestige_count: int
    # Non-None while a prestige transition is pending at adventure_end.
    # Never persisted — cleared during the adventure_end persist path.
    prestige_pending: "PrestigeCarryForward | None" = None
```

`PrestigeCarryForward` is a dataclass defined in `character.py`:

```python
@dataclass
class PrestigeCarryForward:
    """Ephemeral signal written by the prestige effect handler.

    Tells _persist_diff at adventure_end to call prestige_character() and
    swap self._iteration_id before writing the reset state to the new row.
    """
    carry_stats: set[str]      # stat names to copy from old → new state
    carry_skills: set[str]     # skill refs to copy from old → new state
    carry_milestones: set[str] # milestone refs to re-grant on new iteration
```

`new_character()` uses `prestige_count=0` and resolves initial pronouns from the game manifest:

```python
# Before
return cls(
    character_id=uuid4(),
    name=name,
    character_class=None,
    level=1,
    xp=0,
    hp=base_hp,
    max_hp=base_hp,
    iteration=0,
    current_location=None,
    stats=initial_stats,
)

# After — prestige_count replaces iteration; default_pronouns applied from game config
creation_cfg = game_manifest.spec.character_creation

# Resolve initial pronouns: use game-level default if configured, else system default.
initial_pronouns = DEFAULT_PRONOUN_SET
if creation_cfg is not None and creation_cfg.default_pronouns is not None:
    resolved = PRONOUN_SETS.get(creation_cfg.default_pronouns)
    if resolved is not None:
        initial_pronouns = resolved
    else:
        logger.warning(
            "character_creation.default_pronouns %r is not a known pronoun set key — using default.",
            creation_cfg.default_pronouns,
        )

return cls(
    character_id=uuid4(),
    name=name,
    character_class=None,
    level=1,
    xp=0,
    hp=base_hp,
    max_hp=base_hp,
    prestige_count=0,
    pronouns=initial_pronouns,
    current_location=None,
    stats=initial_stats,
)
```

`PRONOUN_SETS` and `DEFAULT_PRONOUN_SET` are already imported from `oscilla.engine.templates` in `character.py`; no new import needed.

`to_dict()` key changes `"iteration"` → `"prestige_count"`:

```python
# Before
return {
    "character_id": str(self.character_id),
    "iteration": self.iteration,
    ...
}

# After
return {
    "character_id": str(self.character_id),
    "prestige_count": self.prestige_count,  # was "iteration"
    ...
}
```

`from_dict()` reads the new key with a backward-compat fallback for any serialized states using `"iteration"`:

```python
# Before
result = cls(
    character_id=UUID(data["character_id"]),
    iteration=data["iteration"],
    ...
)

# After
result = cls(
    character_id=UUID(data["character_id"]),
    # Accept "prestige_count" (new) or "iteration" (legacy serialized states) for backward compat.
    prestige_count=data.get("prestige_count", data.get("iteration", 0)),
    ...
)
```

### `PlayerContext` template rename

```python
# Before (oscilla/engine/templates.py)
class PlayerContext:
    name: str
    level: int
    iteration: int      # ← author sees {{ player.iteration }}
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
            iteration=char.iteration,
            ...
        )

# After (oscilla/engine/templates.py)
class PlayerContext:
    name: str
    level: int
    prestige_count: int  # ← author sees {{ player.prestige_count }}
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
            ...
        )
```

---

## Effect Handler: `PrestigeEffect`

```python
# After (oscilla/engine/steps/effects.py) — added case after EmitTriggerEffect

        case PrestigeEffect():
            if registry.game is None or registry.game.spec.prestige is None:
                logger.error(
                    "prestige effect fired but no prestige: block is declared in game.yaml — skipping."
                )
                await tui.show_text("[red]Error: prestige not configured in game.yaml.[/red]")
                return

            prestige_cfg = registry.game.spec.prestige

            # 1. Run pre_prestige_effects against the CURRENT (old) state.
            for pre_eff in prestige_cfg.pre_prestige_effects:
                await run_effect(
                    effect=pre_eff,
                    player=player,
                    registry=registry,
                    tui=tui,
                    combat=combat,
                    ctx=ctx,
                )

            # 2. Snapshot carried stat, skill, and milestone values BEFORE the reset.
            #    We read from the post-pre_effects state so legacy bonuses
            #    already granted are captured in the carry.
            carried_stats: Dict[str, int | bool | None] = {
                stat: player.stats.get(stat)
                for stat in prestige_cfg.carry_stats
                if stat in player.stats
            }
            carried_skills: Set[str] = player.known_skills & prestige_cfg.carry_skills
            carried_milestones: Set[str] = player.milestones & prestige_cfg.carry_milestones

            # 3. Reset in-memory state to config defaults.
            if registry.character_config is None:
                logger.error("prestige effect: character_config not available in registry — skipping reset.")
                return
            all_stats = (
                registry.character_config.spec.public_stats
                + registry.character_config.spec.hidden_stats
            )
            base_hp = (
                registry.game.spec.hp_formula.base_hp
                if registry.game is not None
                else player.max_hp
            )
            # Reset scalar fields
            player.level = 1
            player.xp = 0
            player.hp = base_hp
            player.max_hp = base_hp
            player.character_class = None
            player.current_location = None
            player.milestones = set()
            player.stacks = {}
            player.instances = []
            player.equipment = {}
            player.active_quests = {}
            player.completed_quests = set()
            player.failed_quests = set()
            player.known_skills = set()
            player.skill_cooldowns = {}
            player.adventure_last_completed_on = {}
            player.adventure_last_completed_at_ticks = {}
            player.internal_ticks = 0
            player.game_ticks = 0
            player.era_started_at_ticks = {}
            player.era_ended_at_ticks = {}
            player.stats = {s.name: s.default for s in all_stats}

            # 4. Apply carry-forward: overwrite reset values with carried ones.
            for stat_name, value in carried_stats.items():
                player.stats[stat_name] = value
            player.known_skills = carried_skills
            player.milestones = carried_milestones

            # 5. Increment prestige_count.
            player.prestige_count += 1

            # 6. Run post_prestige_effects against the NEW (reset + carried) state.
            for post_eff in prestige_cfg.post_prestige_effects:
                await run_effect(
                    effect=post_eff,
                    player=player,
                    registry=registry,
                    tui=tui,
                    combat=combat,
                    ctx=ctx,
                )

            # 7. Signal the session layer to perform the DB iteration transition at adventure_end.
            player.prestige_pending = PrestigeCarryForward(
                carry_stats=prestige_cfg.carry_stats,
                carry_skills=prestige_cfg.carry_skills,
                carry_milestones=prestige_cfg.carry_milestones,
            )

            await tui.show_text(
                f"[bold]Your journey begins anew.[/bold] (Prestige {player.prestige_count})"
            )
```

---

## Effect Handler: `SetNameEffect`

```python
# After (oscilla/engine/steps/effects.py) — added case alongside PrestigeEffect

        case SetNameEffect():
            # If the player already has a real name (e.g. --character-name was
            # supplied at the CLI), skip the prompt and keep the existing name.
            # A placeholder name begins with "new-" followed by a UUID.
            if not _is_placeholder_name(player.name):
                return

            chosen: str = await tui.input_text(effect.prompt)
            player.name = chosen.strip()
```

The placeholder detection helper — defined at module level in `effects.py`:

```python
import re

_PLACEHOLDER_PREFIX = "new-"
_UUID_RE = re.compile(
    r"^new-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

def _is_placeholder_name(name: str) -> bool:
    """Return True when the name is a system-generated placeholder."""
    return bool(_UUID_RE.match(name))
```

---

## Session Layer: Handling `prestige_pending` at `adventure_end`

```python
# After (oscilla/engine/session.py) — inside _persist_diff, at adventure_end block

        if event == "adventure_end":
            # Prestige transition: swap iteration rows before writing the reset state.
            if state.prestige_pending is not None and self.registry.character_config is not None:
                new_iteration = await prestige_character(
                    session=self.db_session,
                    character_id=state.character_id,
                    character_config=self.registry.character_config,
                    game_manifest=self.registry.game,  # needed for base_hp
                )
                self._iteration_id = new_iteration.id
                # Force a full diff by clearing the last‐saved snapshot.
                # The new iteration row is empty (just defaults from prestige_character()),
                # so every field in the reset state needs to be written.
                self._last_saved_state = None
                last = None  # shadow the local that _persist_diff uses for diffing
                state.prestige_pending = None
```

**Skipping mid-adventure persists while prestige is pending:**

```python
# After (oscilla/engine/session.py) — top of _persist_diff

    async def _persist_diff(
        self,
        state: "CharacterState",
        event: Literal["step_start", "combat_round", "adventure_end"],
    ) -> None:
        if self._iteration_id is None:
            logger.warning("_persist_diff called before iteration_id was set; skipping.")
            return

        # If prestige is pending (the prestige effect fired mid-adventure), skip
        # step_start and combat_round checkpoints — we must not write the reset
        # state to the old iteration row. The adventure_end path will swap rows.
        if state.prestige_pending is not None and event != "adventure_end":
            return
```

---

## Session Layer: Placeholder Name in `_create_new_character()`

```python
# After (oscilla/engine/session.py) — _create_new_character()

    async def _create_new_character(
        self,
        character_name: str | None,
        ...,
    ) -> CharacterState:
        # Name resolution priority:
        #   1. CLI --character-name argument (always wins)
        #   2. game.yaml character_creation.default_name (biographic games)
        #   3. UUID placeholder (player-driven games with a set_name adventure step)
        creation_cfg = (
            self.registry.game.spec.character_creation
            if self.registry.game is not None
            else None
        )
        effective_name = (
            character_name
            if character_name is not None
            else (
                creation_cfg.default_name
                if creation_cfg is not None and creation_cfg.default_name is not None
                else f"new-{uuid4()}"
            )
        )
        # (old code: if character_name is None: effective_name = await self.tui.input_text(...))
        state = await create_character(
            session=self.db_session,
            user_id=self.user_id,
            game_name=self.game_name,
            name=effective_name,
            character_config=self.registry.character_config,
        )
        ...
```

The `tui.input_text()` call that was here is removed. The prompt now lives in the creation adventure for games that use player-driven name selection.

## Session Layer: Name-Change Detection in `_persist_diff()`

```python
# After (oscilla/engine/session.py) — inside _persist_diff, any persist event

        # Rename the character record if the player set a name via SetNameEffect.
        if (
            last is not None
            and state.name != last.name
            and not _is_placeholder_name(last.name)  # sanity guard: don't rename over real names
        ) or (
            last is None
            and not _is_placeholder_name(state.name)
            and self._iteration_id is not None
        ):
            # Actually trigger on any mismatch where state.name is a real name:
            pass

        # Simpler formulation: rename whenever state.name differs from what the DB has.
        # The DB name is checked via the character record, not _last_saved_state.
        if state.name != self._db_character_name:
            await rename_character(
                session=self.db_session,
                character_id=state.character_id,
                new_name=state.name,
            )
            self._db_character_name = state.name
```

`self._db_character_name` is a new instance field on `GameSession` initialized from `CharacterRecord.name` at session start (alongside `self._iteration_id`). It tracks the DB-side name so rename is only issued once.

---

## Service Layer: `rename_character()` function

```python
# New function in oscilla/services/character.py

async def rename_character(
    session: AsyncSession,
    character_id: UUID,
    new_name: str,
) -> None:
    """Update CharacterRecord.name and enforce the unique constraint.

    Raises ValueError if the new name is already taken within the same
    (user_id, game_name) scope.
    """
    stmt = select(CharacterRecord).where(
        CharacterRecord.id == character_id
    )
    result = await session.execute(stmt)
    record = result.scalar_one()

    if record.name == new_name:
        return  # nothing to do

    # Check uniqueness within (user_id, game_name).
    conflict_stmt = select(CharacterRecord).where(
        and_(
            CharacterRecord.user_id == record.user_id,
            CharacterRecord.game_name == record.game_name,
            CharacterRecord.name == new_name,
        )
    )
    conflict_result = await session.execute(conflict_stmt)
    if conflict_result.scalar_one_or_none() is not None:
        raise ValueError(
            f"A character named {new_name!r} already exists for this user and game."
        )

    record.name = new_name
    await touch_character_updated_at(session=session, character_id=character_id)
```

---

## Service Layer: `prestige_character()` updated

```python
# After (oscilla/engine/services/character.py)

async def prestige_character(
    session: AsyncSession,
    character_id: UUID,
    character_config: "CharacterConfigManifest",
    game_manifest: "GameManifest | None" = None,
) -> CharacterIterationRecord:
    """Close the active iteration and open a new one seeded from config defaults.

    The carry-forward has already been applied in-memory by the effect handler —
    this function only creates the DB row with base defaults. The session layer's
    _persist_diff will overwrite it in the same transaction via the normal diff
    path after this returns and _last_saved_state is cleared.
    """
    # 1. Find the active iteration
    active_stmt = select(CharacterIterationRecord).where(
        and_(
            CharacterIterationRecord.character_id == character_id,
            CharacterIterationRecord.is_active == True,  # noqa: E712
        )
    )
    active_result = await session.execute(active_stmt)
    active_iteration = active_result.scalar_one()

    # 2. Close it
    active_iteration.is_active = False
    active_iteration.completed_at = datetime.now(tz=timezone.utc)

    # 3. Derive new ordinal
    count_stmt = select(func.count()).where(
        and_(CharacterIterationRecord.character_id == character_id)
    )
    count_result = await session.execute(count_stmt)
    new_ordinal = count_result.scalar_one()

    # 4. Create new iteration row seeded from hp_formula defaults
    base_hp = game_manifest.spec.hp_formula.base_hp if game_manifest is not None else 10
    new_iteration = CharacterIterationRecord(
        character_id=character_id,
        iteration=new_ordinal,
        is_active=True,
        level=1,
        xp=0,
        hp=base_hp,
        max_hp=base_hp,
    )
    session.add(new_iteration)
    await session.flush()

    all_stats = character_config.spec.public_stats + character_config.spec.hidden_stats
    for stat_def in all_stats:
        session.add(
            CharacterIterationStatValue(
                iteration_id=new_iteration.id,
                stat_name=stat_def.name,
                stat_value=_stat_to_int(stat_def.default),
            )
        )

    await touch_character_updated_at(session=session, character_id=character_id)
    # Note: no commit here — the session layer will commit as part of adventure_end.
    return new_iteration
```

Note: `prestige_character()` no longer calls `session.commit()` — the `adventure_end` path in `session.py` owns the commit for the entire transaction (including the diff writes that follow). The old version committed prematurely; this is fixed as part of this change.

---

## Load-time Validation for `PrestigeEffect`

In `oscilla/engine/loader.py`, alongside the existing validation functions that return `List[LoadError]`, add a `_validate_prestige_effects(manifests)` function that returns a `LoadError` for every adventure containing a `PrestigeEffect` when no `prestige:` block is declared in the `GameSpec`. This is a hard error: the whole load fails with `ContentLoadError` if any are found.

```python
# In loader.py validation pass — after existing emit_trigger checks

def _validate_prestige_effects(registry: ContentRegistry) -> None:
    """Warn if any adventure uses type: prestige without a prestige: block."""
    if registry.game is None:
        return
    if registry.game.spec.prestige is not None:
        return  # prestige is configured — no validation needed

    for adv_manifest in registry.adventures.all():
        prestige_effects: List[PrestigeEffect] = []
        for step in adv_manifest.spec.steps:
            _collect_step_prestige_effects(step, prestige_effects)
        if prestige_effects:
                errors.append(
                LoadError(
                    file=adv_manifest.metadata.source_path,
                    message=(
                        f"Adventure {adv_manifest.metadata.name!r} uses type: prestige "
                        "but no prestige: block is declared in game.yaml."
                    ),
                )
            )
```

---

## Testlandia Integration

### Phase 1: Character Creation Adventure

**New file:** `content/testlandia/adventures/character-creation.yaml`

This single adventure handles both first-time character creation and post-prestige re-entry by branching on `prestige_count`. First-timers see the full pronoun and backstory selection; returning players skip those steps and instead receive a brief acknowledgment of their legacy.

```yaml
kind: Adventure
metadata:
  name: character-creation
spec:
  displayName: "A New Beginning"
  description: "Your story begins here."
  steps:
    # Only shown on the very first creation (prestige_count == 0).
    - type: conditional
      requires:
        type: prestige_count
        eq: 0
      steps:
        - type: narrative
          text: |
            You open your eyes for the first time.
            The world of Testlandia stretches before you.
          effects:
            - type: set_name
              prompt: "What is your name, traveler?"

        - type: choice
          prompt: "What pronouns would you like to use?"
          options:
            - label: "They/them"
              effects:
                - type: set_pronouns
                  set: they_them
            - label: "She/her"
              effects:
                - type: set_pronouns
                  set: she_her
            - label: "He/him"
              effects:
                - type: set_pronouns
                  set: he_him

        - type: choice
          prompt: "Where did you come from?"
          options:
            - label: "The academy - trained in careful observation."
              effects:
                - type: stat_change
                  stat: intelligence
                  amount: 2
                - type: stat_change
                  stat: strength
                  amount: -2
            - label: "The streets - you learned to survive on your wits."
              effects:
                - type: stat_change
                  stat: cunning
                  amount: 2
                - type: stat_change
                  stat: reputation
                  amount: -50
            - label: "Nowhere in particular. You prefer not to say."
              effects: []

    # Only shown on prestige re-entry (prestige_count >= 1).
    - type: conditional
      requires:
        type: prestige_count
        gte: 1
      steps:
        - type: narrative
          text: |
            The world of Testlandia greets you again, {{ player.name }}.
            This is your {{ player.prestige_count }} return.
            Legacy power carries with you: {{ player.stats.legacy_power }}.
            Reputation carried: {{ player.stats.reputation }}.
            {% if player.milestones.has('reached-enlightenment') %}
            Your enlightenment follows you into this new life.
            {% endif %}

    # Always shown — welcome message for all new iterations.
    - type: narrative
      text: |
        Welcome, {{ player.name }}. {They} {are} ready to begin.
        Current cunning: {{ player.stats.cunning }}.
```

**Update `content/testlandia/game.yaml`:**

```yaml
trigger_adventures:
  on_character_create:
    - character-creation
```

### Phase 2: Prestige Content

**Update `content/testlandia/game.yaml`:**

```yaml
triggers:
  on_stat_threshold:
    - stat: level
      threshold: 5
      name: max-level-reached
    # Granted when reputation reaches 5; carries forward across prestiges.
    - stat: reputation
      threshold: 5
      name: reached-enlightenment

trigger_adventures:
  on_character_create:
    - character-creation
  max-level-reached:
    - prestige-ceremony

prestige:
  carry_stats:
    - legacy_power
    - reputation
  carry_milestones:
    - reached-enlightenment
    - has-prestiged
  pre_prestige_effects:
    - type: stat_change
      stat: legacy_power
      amount: 1
  post_prestige_effects:
    - type: milestone_grant
      name: has-prestiged
```

**Update `content/testlandia/character_config.yaml`** — add `reputation` to public stats and `legacy_power` to hidden stats:

```yaml
public_stats:
  - name: reputation
    type: int
    default: 0
    description: "Standing in the world. Carries forward on prestige; triggers reached-enlightenment at 5."

hidden_stats:
  - name: legacy_power
    type: int
    default: 0
    description: "Accumulated legacy bonus from previous prestige runs. Carries forward on prestige."
```

**New file:** `content/testlandia/adventures/prestige-ceremony.yaml`

```yaml
kind: Adventure
metadata:
  name: prestige-ceremony
spec:
  displayName: "The End of an Age"
  description: "Your journey reaches its zenith."
  steps:
    - type: narrative
      text: |
        You have reached the pinnacle of what this iteration of your life could offer.
        Level {{ player.level }}. Reputation: {{ player.stats.reputation }}.
        Legacy power accumulated: {{ player.stats.legacy_power }}.
        {% if player.milestones.has('reached-enlightenment') %}
        You carry the mark of enlightenment with you.
        {% endif %}

    - type: choice
      text: "The ancient threshold stands before you. Do you cross it?"
      choices:
        - text: "Step through. Begin again."
          effects:
            - type: prestige
        - text: "Turn back. Not yet."
          effects:
            - type: end_adventure

    - type: narrative
      text: |
        A new age dawns. This is your {{ player.prestige_count }} prestige run.
        Your legacy power carries with you: {{ player.stats.legacy_power }}.
        Reputation carried: {{ player.stats.reputation }}.
        {% if player.milestones.has('reached-enlightenment') %}
        Your enlightenment endures.
        {% endif %}
```

**Update an existing testlandia location** to add a prestige-gated adventure entry:

```yaml
# In an existing location (e.g. testlandia town square)
adventures:
  - ref: prestige-veteran-quest
    requires:
      prestige_count:
        gte: 1
```

**New file:** `content/testlandia/adventures/prestige-veteran-quest.yaml` — a short narrative adventure only accessible after first prestige:

```yaml
kind: Adventure
metadata:
  name: prestige-veteran-quest
spec:
  displayName: "Veteran's Remembrance"
  description: "Only those who have lived before may enter."
  steps:
    - type: narrative
      text: |
        The elder nods. "I remember you," {they say}. "You've been here before."
        Your legacy power: {{ player.stats.legacy_power }}.
        Reputation: {{ player.stats.reputation }}.
        Prestige runs completed: {{ player.prestige_count }}.
        {% if player.milestones.has('reached-enlightenment') %}
        The mark of enlightenment shines in your eyes.
        {% endif %}
```

---

## Documentation Plan

### `docs/authors/adventures.md` — updates

**Audience:** Content authors writing adventure manifests.

**Topics to add:**

- `on_character_create` trigger: what it is, when it fires, how to wire it in `game.yaml`
- `type: set_name` effect: behavior, the placeholder-name pattern, interaction with `--character-name` CLI flag
- Full name + pronoun selection example (the testlandia `character-creation.yaml` adventure)
- Backstory stat bonuses example
- How to branch on `prestige_count` within a single creation adventure to show different steps for first-time creation vs. prestige re-entry — authors do not need two separate adventures
- Explanation of "the character sees the creation adventure before the world map" — no TUI config needed
- Note that omitting `on_character_create` wiring means creation is instant (just config defaults)

### `docs/authors/game-configuration.md` — updates

**Audience:** Content authors configuring `game.yaml`.

**Topics to add:**

- `character_creation:` block: `default_name` and `default_pronouns` fields; when to use them (biographic games); interaction with `SetNameEffect` and `set_pronouns` steps; how adventure steps can still override game-level defaults
- `prestige:` block: all fields documented with examples
- `carry_stats`, `carry_skills`, and `carry_milestones`: semantic explanation (values copied from old iteration to new)
- `pre_prestige_effects` and `post_prestige_effects`: when they run, what effects are appropriate
- Full testlandia-style prestige configuration example
- Warning about `prestige_count` condition syntax: `prestige_count: {gte: 1}`
- `{{ player.prestige_count }}` in templates

### New doc (optional but recommended): `docs/authors/prestige.md`

**Audience:** Content authors building prestige-based games.

**Topics:**

- Conceptual overview: what prestige is and how the engine models it
- The prestige lifecycle diagram (using Mermaid)
- Carry-forward design guidance
- Using `prestige_count` in conditions and templates
- Cross-referencing with `on_stat_threshold` as the prestige trigger mechanism

---

## Testing Philosophy

### Unit tests — `tests/engine/test_prestige_effect.py`

New test file. Tests use `CharacterState` dataclasses and mock registries directly — no YAML loading.

**Tests required:**

```python
# Fixture: a minimal registry with a prestige config
@pytest.fixture
def prestige_registry(mock_registry: ContentRegistry) -> ContentRegistry:
    """ContentRegistry with prestige configured: carry legacy_power, pre/post effects."""
    mock_registry.game.spec.prestige = PrestigeConfig(
        carry_stats={"legacy_power"},
        carry_skills=set(),
        carry_milestones=set(),
        pre_prestige_effects=[
            StatChangeEffect(type="stat_change", stat="legacy_power", amount=1)
        ],
        post_prestige_effects=[],
    )
    mock_registry.character_config.spec.public_stats = [
        StatDef(name="cunning", type="int", default=0),
    ]
    mock_registry.character_config.spec.hidden_stats = [
        StatDef(name="legacy_power", type="int", default=0),
    ]
    return mock_registry


async def test_prestige_resets_level(prestige_registry, mock_tui):
    """Level resets to 1 after prestige."""
    player = make_character(level=5, stats={"cunning": 3, "legacy_power": 0})
    await run_effect(
        effect=PrestigeEffect(type="prestige"),
        player=player,
        registry=prestige_registry,
        tui=mock_tui,
    )
    assert player.level == 1


async def test_prestige_increments_prestige_count(prestige_registry, mock_tui):
    """prestige_count increments by 1 each prestige."""
    player = make_character(prestige_count=0, stats={"cunning": 0, "legacy_power": 0})
    await run_effect(PrestigeEffect(type="prestige"), player, prestige_registry, mock_tui)
    assert player.prestige_count == 1


async def test_prestige_runs_pre_effects_before_reset(prestige_registry, mock_tui):
    """pre_prestige_effects fire against old state so legacy_power is +1 before carry."""
    player = make_character(stats={"cunning": 3, "legacy_power": 0})
    await run_effect(PrestigeEffect(type="prestige"), player, prestige_registry, mock_tui)
    # pre_effect granted legacy_power +1, then carry brought it forward
    assert player.stats["legacy_power"] == 1


async def test_prestige_carry_stat_survives_reset(prestige_registry, mock_tui):
    """Legacy stat value (post pre-effects) is present in new state."""
    player = make_character(stats={"cunning": 3, "legacy_power": 5})
    await run_effect(PrestigeEffect(type="prestige"), player, prestige_registry, mock_tui)
    # pre_effect adds 1 → legacy_power becomes 6, then carry copies it
    assert player.stats["legacy_power"] == 6


async def test_prestige_non_carry_stat_resets(prestige_registry, mock_tui):
    """Stats not in carry_stats reset to config defaults."""
    player = make_character(stats={"cunning": 99, "legacy_power": 0})
    await run_effect(PrestigeEffect(type="prestige"), player, prestige_registry, mock_tui)
    assert player.stats["cunning"] == 0  # config default


async def test_prestige_sets_prestige_pending(prestige_registry, mock_tui):
    """prestige_pending is set after effect fires (signals DB transition)."""
    player = make_character(stats={"cunning": 0, "legacy_power": 0})
    await run_effect(PrestigeEffect(type="prestige"), player, prestige_registry, mock_tui)
    assert player.prestige_pending is not None


async def test_prestige_no_config_logs_error(mock_registry, mock_tui):
    """Runtime guard: PrestigeEffect logs error and leaves state unchanged when prestige: is absent.

    The loader should prevent this in production, but a belt-and-suspenders guard exists.
    """
    mock_registry.game.spec.prestige = None
    player = make_character(prestige_count=0, level=5, stats={"cunning": 3})
    await run_effect(PrestigeEffect(type="prestige"), player, mock_registry, mock_tui)
    assert player.prestige_count == 0
    assert player.level == 5
```

### Unit tests — `tests/engine/test_prestige_count_rename.py`

```python
def test_prestige_count_condition_yaml_key():
    """The YAML discriminator key is 'prestige_count', not 'iteration'."""
    data = {"type": "prestige_count", "gte": 1}
    cond = parse_condition(data)
    assert isinstance(cond, PrestigeCountCondition)


def test_iteration_yaml_key_is_rejected():
    """The old 'iteration' key no longer parses as PrestigeCountCondition."""
    data = {"type": "iteration", "gte": 1}
    with pytest.raises(ValidationError):
        parse_condition(data)


def test_character_state_prestige_count_field():
    """CharacterState has prestige_count not iteration."""
    state = CharacterState.new_character(name="Test", ...)
    assert state.prestige_count == 0
    assert not hasattr(state, "iteration")


def test_to_dict_uses_prestige_count_key():
    d = make_character(prestige_count=2).to_dict()
    assert "prestige_count" in d
    assert "iteration" not in d


def test_from_dict_backward_compat_iteration_key():
    """from_dict() accepts old 'iteration' key for legacy saves."""
    data = minimal_character_dict()
    data["iteration"] = 3  # old key
    state = CharacterState.from_dict(data=data, character_config=minimal_config())
    assert state.prestige_count == 3
```

### Integration tests — existing triggered-adventure tests

Any test that builds `CharacterState` with `iteration=0` must be updated to `prestige_count=0`. Run `make pytest` to catch all failures; the rename is mechanical.

### Unit tests — `tests/engine/test_set_name_effect.py`

New test file. Tests use `CharacterState` dataclasses and mock TUI directly — no YAML loading.

```python
async def test_set_name_updates_character_name(mock_registry, mock_tui):
    """SetNameEffect prompts and sets player.name when current name is a placeholder."""
    player = make_character(name="new-11111111-0000-0000-0000-000000000000")
    mock_tui.input_text = AsyncMock(return_value="Lyra")
    await run_effect(
        effect=SetNameEffect(type="set_name"),
        player=player,
        registry=mock_registry,
        tui=mock_tui,
    )
    assert player.name == "Lyra"
    mock_tui.input_text.assert_awaited_once()


async def test_set_name_strips_whitespace(mock_registry, mock_tui):
    """SetNameEffect strips leading/trailing whitespace from entered name."""
    player = make_character(name="new-11111111-0000-0000-0000-000000000000")
    mock_tui.input_text = AsyncMock(return_value="  Lyra  ")
    await run_effect(SetNameEffect(type="set_name"), player, mock_registry, mock_tui)
    assert player.name == "Lyra"


async def test_set_name_skips_when_name_is_real(mock_registry, mock_tui):
    """SetNameEffect does nothing when the player already has a real (non-placeholder) name."""
    player = make_character(name="AlreadyNamed")
    mock_tui.input_text = AsyncMock()
    await run_effect(SetNameEffect(type="set_name"), player, mock_registry, mock_tui)
    assert player.name == "AlreadyNamed"
    mock_tui.input_text.assert_not_awaited()


def test_placeholder_name_detection():
    """_is_placeholder_name correctly identifies generated placeholder names."""
    assert _is_placeholder_name("new-11111111-2222-3333-4444-555555555555") is True
    assert _is_placeholder_name("Lyra") is False
    assert _is_placeholder_name("new-notauuid") is False
    assert _is_placeholder_name("") is False


def test_set_name_skips_when_default_name_is_set(mock_registry, mock_tui):
    """SetNameEffect skips when the game uses a default_name — character already has a real name."""
    # Simulate a biographic game: _create_new_character used "Elara" as the name.
    player = make_character(name="Elara")
    mock_tui.input_text = AsyncMock()
    await run_effect(SetNameEffect(type="set_name"), player, mock_registry, mock_tui)
    assert player.name == "Elara"
    mock_tui.input_text.assert_not_awaited()
```

### Unit tests — `tests/engine/test_character_creation_defaults.py`

New test file covering `CharacterCreationDefaults` and its effect on `new_character()`.

```python
def test_new_character_uses_default_pronouns_from_game_spec(mock_game_manifest):
    """new_character() picks up default_pronouns from game.yaml character_creation block."""
    mock_game_manifest.spec.character_creation = CharacterCreationDefaults(
        default_pronouns="she_her"
    )
    state = CharacterState.new_character(
        name="Elara",
        game_manifest=mock_game_manifest,
        character_config=minimal_config(),
    )
    # she_her PronounSet should be set, not the default they_them
    assert state.pronouns == PRONOUN_SETS["she_her"]


def test_new_character_uses_default_pronoun_set_when_no_config(mock_game_manifest):
    """new_character() uses DEFAULT_PRONOUN_SET when no character_creation block."""
    mock_game_manifest.spec.character_creation = None
    state = CharacterState.new_character(
        name="Player",
        game_manifest=mock_game_manifest,
        character_config=minimal_config(),
    )
    assert state.pronouns == DEFAULT_PRONOUN_SET


def test_new_character_warns_and_falls_back_on_unknown_pronoun_key(mock_game_manifest, caplog):
    """new_character() logs a warning and falls back to DEFAULT_PRONOUN_SET for unknown keys."""
    mock_game_manifest.spec.character_creation = CharacterCreationDefaults(
        default_pronouns="xir_xir"  # not a built-in key
    )
    state = CharacterState.new_character(
        name="Player",
        game_manifest=mock_game_manifest,
        character_config=minimal_config(),
    )
    assert state.pronouns == DEFAULT_PRONOUN_SET
    assert "xir_xir" in caplog.text


def test_character_creation_defaults_default_name_bypasses_placeholder():
    """CharacterCreationDefaults.default_name is not a UUID placeholder."""
    cfg = CharacterCreationDefaults(default_name="Protagonist")
    assert not _is_placeholder_name(cfg.default_name)
```



The `testlandia` content package is loaded in `test_cli_content.py` and `test_www.py`. These run the loader and validate all manifests. They will catch:

- Missing `legacy_power` stat definition
- Invalid trigger wiring
- Bad prestige config references
- Malformed `type: set_name` steps in the creation adventure

No new test files for testlandia content — it is exercised by the existing content-load tests.

---

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| `CharacterState.iteration` rename touches many test files | Mechanical grep-and-replace; `make mypy_check` catches any missed refs |
| `mid-adventure prestige_pending` skips checkpoints — crash recovery replays from pre-prestige | Acceptable: prestige adventures are short narrative sequences; authors are advised not to include combat after `type: prestige` |
| `prestige_character()` no longer commits — relies on caller pattern | The adventure_end path in `session.py` already owns the commit; removing the premature commit is strictly correct |
| hard error for missing `prestige:` block | Failing loudly prevents silent runtime no-ops that would confuse authors; the check is cheap and the misconfiguration is always a content bug |
| Placeholder name in DB between creation start and `SetNameEffect` firing | Placeholder names use `new-{uuid4()}` and are never unique-constrained by a user — the rename path enforces uniqueness only on real names |
| `rename_character()` raises `ValueError` if name already taken | The TUI should catch `ValueError` and re-prompt; exact UX is left to the TUI change that wires this end-to-end |
| `character_creation.default_pronouns` key not validated at parse time by Pydantic | Add a `model_validator` on `CharacterCreationDefaults` that checks the key against `PRONOUN_SETS` at load time; `new_character()` also has a runtime fallback with a warning |
