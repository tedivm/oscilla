## Context

Character state currently records time-related information using three different, inconsistent approaches that have accumulated across separate feature additions:

1. **ISO date strings** — `adventure_last_completed_on: Dict[str, str]` stores `date.today().isoformat()`. Day-precision is an arbitrary constraint; sub-day cooldowns are impossible.
2. **Adventure-count countdown** — `skill_cooldowns: Dict[str, int]` stores "num adventures remaining before this skill is usable again." The method that decrements it (`tick_skill_cooldowns()`) is **never called**, so adventure-scoped skill cooldowns are silently non-functional.
3. **`__game__` prefix hack** — `adventure_last_completed_at_ticks` stores game-tick values under keys like `f"__game__{adventure_ref}"`, sharing a single dict with internal-tick values to avoid adding a second field.

Additionally:

- `milestones: Set[str]` stores only the milestone name, with no record of when it was granted. This prevents "time since milestone" narrative conditions.
- Adventure cooldowns use three separate flat YAML fields (`cooldown_days`, `cooldown_ticks`, `cooldown_game_ticks`); skills use a completely different `SkillCooldown(scope, count)` schema. There is no shared model.

This change unifies all time tracking onto a clean two-track model (internal ticks + real-world Unix timestamps), creates a shared `Cooldown` Pydantic model used everywhere, fixes the skill cooldown bug, and adds `milestone_ticks_elapsed` to the condition evaluator.

**Key files and their roles:**

| File                                    | Role                                                                                                              |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `oscilla/engine/character.py`           | `CharacterState` dataclass — field renames, type changes, bug fix                                                 |
| `oscilla/engine/models/base.py`         | `MilestoneRecord` model added; `MilestoneTicksElapsedCondition` added to Condition union                          |
| `oscilla/engine/models/adventure.py`    | Flat cooldown fields replaced by `cooldown: Cooldown \| None`; `Cooldown` model defined                           |
| `oscilla/engine/models/skill.py`        | `SkillCooldown` replaced by shared `Cooldown`                                                                     |
| `oscilla/engine/conditions.py`          | `milestone_ticks_elapsed` evaluator branch                                                                        |
| `oscilla/engine/session.py`             | Real-world timestamp write replaced; `skill_cooldowns` diff replaced; adventure state diff updated                |
| `oscilla/models/character_iteration.py` | Three DB table schemas updated; Alembic migration required                                                        |
| `oscilla/services/character.py`         | `add_milestone`, `set_skill_cooldown`, `upsert_adventure_state` updated; `load_character` deserialization updated |
| `oscilla/engine/pipeline.py`            | Tick recording updated; `adventure_last_completed_game_ticks` written separately                                  |
| `oscilla/engine/actions.py`             | Skill cooldown checks rewritten to expiry-timestamp model                                                         |
| `oscilla/engine/steps/combat.py`        | Skill cooldown checks rewritten to expiry-timestamp model                                                         |
| `oscilla/engine/templates.py`           | `SECONDS_PER_*` constants injected into `SAFE_GLOBALS` and mock context                                           |
| `content/testlandia/`                   | New adventures demonstrating all new capabilities                                                                 |

---

## Goals / Non-Goals

**Goals:**

- Fix the skill cooldown bug — `tick_skill_cooldowns()` is defined but never called; adventure-scoped skill cooldowns are non-functional. Replaced by expiry-timestamp model that requires no ceremony.
- Unify milestones onto tick-anchored storage — `Dict[str, MilestoneRecord]` preserves both grant tick and real-world grant timestamp; `has_milestone()` API unchanged.
- New condition `milestone_ticks_elapsed` enables "how long ago" narrative gates.
- Single shared `Cooldown` Pydantic model used by both adventure repeat controls and skill cooldowns.
- Replace ISO date string timestamps with Unix timestamps (int seconds) for sub-day real-world cooldown precision.
- Template constants (`SECONDS_PER_MINUTE`, `SECONDS_PER_HOUR`, `SECONDS_PER_DAY`, `SECONDS_PER_WEEK`) injected into the template context.
- Clean up the `__game__` prefix hack — `adventure_last_completed_game_ticks` is a separate dict.
- Testlandia demonstrates all new capabilities end-to-end.

**Non-Goals:**

- Named-cycle cooldowns (e.g. `cooldown_cycle: {cycle: "day", value: 1}`) — deferred. The `Cooldown` model can accommodate this in a future change.
- Template access to milestones-as-dict — `player.milestones.has(name)` is the public API; raw `MilestoneRecord` fields are a future author-docs enhancement if needed.
- Cross-iteration milestone queries — tracked milestones are iteration-scoped; prestige resets them.
- Database migration — no live deployments; clean break is acceptable per user decision.

---

## Decisions

### Decision 1: Expiry timestamps replace countdown arithmetic for skill cooldowns

**Current approach (broken):** `skill_cooldowns: Dict[str, int]` stores "N adventures remaining." A `tick_skill_cooldowns()` method was meant to decrement this each adventure, but it is never called. Skills with `scope: adventure` are completely non-functional.

**New approach:** At use time, set an expiry:

- `skill_tick_expiry: Dict[str, int]` — the `internal_ticks` value at which the cooldown expires.
- `skill_real_expiry: Dict[str, int]` — the Unix timestamp (seconds) at which the cooldown expires.

At check time, compare current tick/time against stored expiry. No ceremony, no method to forget to call.

**Rationale:** Countdown state requires maintenance at specific lifecycle points. Expiry timestamps are self-contained — checking `internal_ticks >= expiry` requires no state mutation. This also naturally unifies with the adventure cooldown model, which already uses "last completed at" + "required elapsed" comparisons (we convert this to a composite: store `last_completed + required = expiry` at the use site).

**Alternative considered:** Fix by calling `tick_skill_cooldowns()` at adventure start. Rejected — this propagates the countdown model and prevents `seconds`-based skill cooldowns without a parallel time-tracking mechanism.

### Decision 2: Shared `Cooldown` Pydantic model

A single `Cooldown` model lives in `oscilla/engine/models/adventure.py` (alongside `AdventureSpec`) and is imported by `models/skill.py`. All fields are `int | str | None` to support Jinja2 template strings (e.g. `ticks: "{{ SECONDS_PER_DAY }}"`). Multiple non-None fields are AND-ed — all constraints must pass simultaneously.

```python
class Cooldown(BaseModel):
    # internal_ticks elapsed since the last use — tamper-proof monotone clock.
    ticks: int | str | None = None
    # game_ticks elapsed since the last use — narrative clock, adjustable by effects.
    game_ticks: int | str | None = None
    # Real-world seconds elapsed since the last use — wall-clock track.
    seconds: int | str | None = None
    # Combat turns before reuse — only meaningful with scope: "turn".
    turns: int | str | None = None
    # scope: None (default) = persistent across sessions.
    # scope: "turn" = resets with combat; only "turns" field is evaluated.
    scope: Literal["turn"] | None = None

    @model_validator(mode="after")
    def validate_turn_scope(self) -> "Cooldown":
        if self.scope == "turn":
            if any(v is not None for v in [self.ticks, self.game_ticks, self.seconds]):
                raise ValueError(
                    "Cooldown with scope='turn' may only use 'turns'. "
                    "Remove ticks, game_ticks, and seconds fields."
                )
        else:
            if self.turns is not None:
                raise ValueError(
                    "Cooldown 'turns' field is only valid with scope='turn'."
                )
        return self
```

**Alternative considered:** Keep `SkillCooldown` for skills and `Cooldown` for adventures. Rejected — two schemas for the same concept with different names forces authors to remember which applies where. One model used consistently is always better.

### Decision 3: `milestones: Dict[str, MilestoneRecord]` with preserved `has_milestone()` API

`milestones` changes type from `Set[str]` to `Dict[str, MilestoneRecord]` where `MilestoneRecord` is a small Pydantic model holding both the `internal_ticks` value and the Unix timestamp at the moment of grant. Recording both tracks at grant time is cheap and provides the data for future UI display ("milestone earned N days ago") and future real-world-time conditions without a second migration.

`has_milestone(name)` continues to work: `return name in self.milestones`. `grant_milestone(name)` now stores `MilestoneRecord(tick=self.internal_ticks, timestamp=int(time.time()))`. Re-granting is a no-op (milestone already present). Serialization switches from `sorted(self.milestones)` (a list) to a nested dict `{name: {"tick": N, "timestamp": N}}`.

`from_dict` supports three formats for backward compatibility:

- Old list `["milestone-a", "milestone-b"]` → `MilestoneRecord(tick=0, timestamp=0)` per entry.
- Intermediate int-dict `{"milestone-a": 42}` → `MilestoneRecord(tick=42, timestamp=0)` per entry (graceful handling if code was deployed with the `Dict[str, int]` design before this record model was introduced).
- Current nested dict `{"milestone-a": {"tick": 42, "timestamp": 1744000000}}` → parsed directly.

`PlayerMilestoneView` in `templates.py` exposes only `has()` to templates (no raw `MilestoneRecord` access), so no template-breaking change occurs.

`MilestoneRecord` is defined in `oscilla/engine/models/base.py` alongside `MilestoneCondition`.

**Alternative considered:** `Dict[str, int]` storing tick only, with a parallel `milestone_timestamps: Dict[str, int]` for timestamps. Rejected — maintaining two data structures for the same set of milestones is fragile and complicates serialization. A small named record is the right abstraction.

### Decision 4: `adventure_last_completed_game_ticks` as a separate dict

The current `__game__` prefix hack (`adventure_last_completed_at_ticks[f"__game__{ref}"]`) is an undocumented encoding that makes the dict harder to inspect and debug. The new design splits into two clean dicts:

- `adventure_last_completed_at_ticks: Dict[str, int]` — renamed in spirit to `adventure_last_completed_internal_ticks` ... but to minimize churn, we keep the key name as `adventure_last_completed_at_ticks` in the serialized dict and just add the second one as `adventure_last_completed_game_ticks`.
- `adventure_last_completed_game_ticks: Dict[str, int]` — game ticks when each adventure was last completed.
- `adventure_last_completed_real_ts: Dict[str, int]` — Unix timestamp (seconds) when each adventure was last completed.

The `__game__` prefix entries in `adventure_last_completed_at_ticks` are migrated at `from_dict` time.

### Decision 5: Template constants as entries in `SAFE_GLOBALS`

Time constants are injected into `SAFE_GLOBALS` alongside the existing `roll`, `clamp`, etc. functions. This makes them available in any template expression, including cooldown fields like `seconds: "{{ SECONDS_PER_DAY * 7 }}"`.

```python
# Common real-world time multiples for use in template expressions
SECONDS_PER_MINUTE: int = 60
SECONDS_PER_HOUR: int = 3_600
SECONDS_PER_DAY: int = 86_400
SECONDS_PER_WEEK: int = 604_800
```

They are also added to `build_mock_context()` so load-time template validation works.

**Alternative considered:** A `time` namespace (e.g. `time.SECONDS_PER_DAY`). Rejected — the existing pattern is flat globals (`roll`, `clamp`); adding a namespace inconsistency would be confusing.

### Decision 6: Cooldown evaluation at adventure eligibility check time

Adventure cooldowns (`Cooldown` on `AdventureSpec`) are evaluated in `is_adventure_eligible()` on `CharacterState`. The `seconds` field is checked against `adventure_last_completed_real_ts`. Values are rendered through the template engine before numeric comparison (when the stored value is a string). The rendering call requires a minimal template context — only `SAFE_GLOBALS` and the player state; no full `ExpressionContext` is needed since cooldown values are numeric expressions without narrative text.

---

## Implementation Details

### `oscilla/engine/models/adventure.py` — `Cooldown` model and updated `AdventureSpec`

**Before (flat fields on AdventureSpec):**

```python
class AdventureSpec(BaseModel):
    displayName: str
    description: str = ""
    requires: Condition | None = None
    steps: List[Step]
    ticks: int | None = Field(default=None, ge=1, description="Tick cost for this adventure.")
    repeatable: bool = Field(default=True, description="Set to False to make this a one-shot adventure.")
    max_completions: int | None = Field(default=None, description="Hard cap on total completions this iteration.")
    cooldown_days: int | None = Field(default=None, description="Calendar days that must pass between runs.")
    cooldown_adventures: int | None = Field(
        default=None,
        description="Deprecated. Use cooldown_ticks instead.",
    )
    cooldown_ticks: int | None = Field(
        default=None,
        description="internal_ticks that must pass since last completion.",
    )
    cooldown_game_ticks: int | None = Field(
        default=None,
        description="game_ticks that must pass since last completion.",
    )

    @model_validator(mode="after")
    def migrate_deprecated_cooldown_adventures(self) -> "AdventureSpec":
        """Map deprecated cooldown_adventures to cooldown_ticks with a load warning."""
        if self.cooldown_adventures is not None:
            import logging
            logging.getLogger(__name__).warning(
                "Adventure uses deprecated 'cooldown_adventures' — use 'cooldown_ticks' instead. "
                "Mapping %d → cooldown_ticks.",
                self.cooldown_adventures,
            )
            if self.cooldown_ticks is None:
                self.cooldown_ticks = self.cooldown_adventures
            self.cooldown_adventures = None
        return self
```

**After (new `Cooldown` model added before `AdventureSpec`, flat fields replaced):**

```python
class Cooldown(BaseModel):
    """Unified reuse-rate limiter for adventures and skills.

    All numeric fields support Jinja2 template strings (e.g. "{{ SECONDS_PER_DAY * 7 }}").
    Multiple non-None fields are AND-ed — all constraints must pass simultaneously.
    scope='turn' is combat-only; only 'turns' is evaluated for turn-scoped cooldowns.
    """

    # internal_ticks elapsed since last use — tamper-proof monotone clock.
    ticks: int | str | None = None
    # game_ticks elapsed since last use — narrative clock, adjustable by effects.
    game_ticks: int | str | None = None
    # Real-world seconds elapsed since last use — wall-clock track.
    seconds: int | str | None = None
    # Combat turns before reuse — only valid with scope: "turn".
    turns: int | str | None = None
    # scope: None = persistent across sessions.
    # scope: "turn" = resets each combat; only "turns" is evaluated.
    scope: Literal["turn"] | None = None

    @model_validator(mode="after")
    def validate_scope_fields(self) -> "Cooldown":
        if self.scope == "turn":
            incompatible = [f for f in ("ticks", "game_ticks", "seconds") if getattr(self, f) is not None]
            if incompatible:
                raise ValueError(
                    f"Cooldown with scope='turn' may only use 'turns'. "
                    f"Remove these fields: {', '.join(incompatible)}"
                )
        else:
            if self.turns is not None:
                raise ValueError("Cooldown 'turns' field is only valid with scope='turn'.")
        return self

    @model_validator(mode="after")
    def at_least_one_constraint(self) -> "Cooldown":
        if all(v is None for v in (self.ticks, self.game_ticks, self.seconds, self.turns)):
            raise ValueError("Cooldown must specify at least one of: ticks, game_ticks, seconds, turns.")
        return self


class AdventureSpec(BaseModel):
    displayName: str
    description: str = ""
    requires: Condition | None = None
    steps: List[Step]
    ticks: int | None = Field(default=None, ge=1, description="Tick cost for this adventure.")
    repeatable: bool = Field(default=True, description="Set to False to make this a one-shot adventure.")
    max_completions: int | None = Field(default=None, description="Hard cap on total completions this iteration.")
    # Single nested Cooldown object replaces cooldown_days, cooldown_ticks, cooldown_game_ticks.
    cooldown: Cooldown | None = None

    # validate_repeat_controls and validate_unique_labels unchanged ...
```

### `oscilla/engine/models/skill.py` — replace `SkillCooldown` with `Cooldown`

**Before:**

```python
class SkillCooldown(BaseModel):
    """Prevents a skill from being used too frequently."""

    scope: Literal["turn", "adventure"] = Field(
        description="'turn' resets each combat; 'adventure' persists across adventures."
    )
    count: int = Field(ge=1, description="Turns or adventures required between uses.")


class SkillSpec(BaseModel):
    # ...
    cooldown: SkillCooldown | None = None
```

**After:**

```python
from oscilla.engine.models.adventure import Cooldown  # noqa: TC001  (runtime import)


class SkillSpec(BaseModel):
    # ...
    # Uses the same Cooldown model as adventures.
    # scope: None = persistent; scope: "turn" = per-combat only.
    cooldown: Cooldown | None = None
```

`SkillCooldown` is removed. All existing `scope: adventure, count: N` skill YAML must be updated to `ticks: N` (or `seconds: N`, etc.).

### `oscilla/engine/models/base.py` — `MilestoneRecord` and `MilestoneTicksElapsedCondition`

**New `MilestoneRecord` model added (near `MilestoneCondition`):**

```python
class MilestoneRecord(BaseModel):
    """Snapshot of both time tracks recorded when a milestone is granted."""

    tick: int = Field(description="internal_ticks value at the moment the milestone was granted.")
    timestamp: int = Field(description="Unix timestamp (seconds) at the moment the milestone was granted.")
```

**New `MilestoneTicksElapsedCondition` added near `MilestoneCondition`:**

```python
class MilestoneTicksElapsedCondition(BaseModel):
    """True when at least (or at most) N internal ticks have elapsed since the named milestone was granted.

    If the milestone has not been granted, the condition evaluates to False.
    Uses internal_ticks — the tamper-proof monotone clock — so it is unaffected
    by adjust_game_ticks effects.
    """

    type: Literal["milestone_ticks_elapsed"]
    name: str = Field(description="Milestone name to check.")
    gte: int | None = Field(default=None, description="Elapsed ticks must be >= this value.")
    lte: int | None = Field(default=None, description="Elapsed ticks must be <= this value.")

    @model_validator(mode="after")
    def require_comparator(self) -> "MilestoneTicksElapsedCondition":
        if self.gte is None and self.lte is None:
            raise ValueError("milestone_ticks_elapsed must specify at least one of: gte, lte")
        return self
```

Added to the `Condition` union before the calendar predicates.

### `oscilla/engine/character.py` — `CharacterState` field changes

**Before (relevant fields):**

```python
@dataclass
class CharacterState:
    # ...
    milestones: Set[str] = field(default_factory=set)
    # ...
    skill_cooldowns: Dict[str, int] = field(default_factory=dict)
    adventure_last_completed_on: Dict[str, str] = field(default_factory=dict)
    adventure_last_completed_at_ticks: Dict[str, int] = field(default_factory=dict)
```

**After:**

```python
@dataclass
class CharacterState:
    # ...
    # Milestone name → MilestoneRecord(tick, timestamp) capturing both time tracks at grant time.
    milestones: Dict[str, MilestoneRecord] = field(default_factory=dict)
    # ...
    # Adventure-scoped skill cooldowns — absolute expiry tick and Unix timestamp.
    # Set at use time: expiry_tick = internal_ticks + required_ticks.
    # Removed when expired; never decremented.
    skill_tick_expiry: Dict[str, int] = field(default_factory=dict)
    skill_real_expiry: Dict[str, int] = field(default_factory=dict)
    # Real-world Unix timestamp (seconds) when each adventure was last completed.
    adventure_last_completed_real_ts: Dict[str, int] = field(default_factory=dict)
    # internal_ticks value when each adventure was last completed.
    adventure_last_completed_at_ticks: Dict[str, int] = field(default_factory=dict)
    # game_ticks value when each adventure was last completed.
    adventure_last_completed_game_ticks: Dict[str, int] = field(default_factory=dict)
```

**`grant_milestone` — before:**

```python
def grant_milestone(self, name: str) -> None:
    """Add a milestone flag. No-op if already held."""
    self.milestones.add(name)
```

**After:**

```python
from oscilla.engine.models.base import MilestoneRecord


def grant_milestone(self, name: str) -> None:
    """Record a milestone capturing the current tick and real-world timestamp. No-op if already held."""
    if name not in self.milestones:
        self.milestones[name] = MilestoneRecord(tick=self.internal_ticks, timestamp=int(time.time()))
```

**`has_milestone` — unchanged:** `return name in self.milestones` works for both `Set` and `Dict`.

**`tick_skill_cooldowns` — removed entirely.** Expiry-timestamp storage makes countdown ceremony unnecessary. Any references to this method are deleted.

**`is_adventure_eligible` — before (`cooldown_days`/`cooldown_ticks`/`cooldown_game_ticks`):**

```python
def is_adventure_eligible(
    self,
    adventure_ref: str,
    spec: "AdventureSpec",
    today: "date",
) -> bool:
    from datetime import date as date_t
    completions = self.statistics.adventures_completed.get(adventure_ref, 0)

    if not spec.repeatable and completions >= 1:
        return False
    if spec.max_completions is not None and completions >= spec.max_completions:
        return False

    if spec.cooldown_days is not None:
        last_on_str = self.adventure_last_completed_on.get(adventure_ref)
        if last_on_str is not None:
            last_on = date_t.fromisoformat(last_on_str)
            if (today - last_on).days < spec.cooldown_days:
                return False

    if spec.cooldown_ticks is not None:
        last_ticks = self.adventure_last_completed_at_ticks.get(adventure_ref)
        if last_ticks is not None:
            if self.internal_ticks - last_ticks < spec.cooldown_ticks:
                return False

    if spec.cooldown_game_ticks is not None:
        last_game_ticks = self.adventure_last_completed_at_ticks.get(f"__game__{adventure_ref}")
        if last_game_ticks is not None:
            if self.game_ticks - last_game_ticks < spec.cooldown_game_ticks:
                return False

    return True
```

**After (signature changes — `today` removed, `now_ts` added, `Cooldown` unified):**

```python
def is_adventure_eligible(
    self,
    adventure_ref: str,
    spec: "AdventureSpec",
    now_ts: int,
    template_engine: "GameTemplateEngine | None" = None,
) -> bool:
    """Return True if repeat controls allow running this adventure right now.

    now_ts: current Unix timestamp in seconds (from int(time.time())).
    template_engine: required to evaluate str-typed Cooldown fields; omit in tests
                     that only use plain int cooldown values.
    """
    completions = self.statistics.adventures_completed.get(adventure_ref, 0)

    if not spec.repeatable and completions >= 1:
        return False
    if spec.max_completions is not None and completions >= spec.max_completions:
        return False

    if spec.cooldown is None:
        return True

    cd = spec.cooldown

    # Resolve str template fields to int if needed.
    # A minimal context with only SAFE_GLOBALS is sufficient for numeric expressions.
    def _resolve(v: int | str | None) -> int | None:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if template_engine is None:
            logger.warning("Cooldown field %r is a template string but no engine provided — treating as 0.", v)
            return 0
        return int(template_engine.render_int(v, context={}))

    ticks_required = _resolve(cd.ticks)
    game_ticks_required = _resolve(cd.game_ticks)
    seconds_required = _resolve(cd.seconds)

    # scope: "turn" cooldowns are managed by combat context, not here.
    if cd.scope == "turn":
        return True

    # ticks constraint
    if ticks_required is not None:
        last = self.adventure_last_completed_at_ticks.get(adventure_ref)
        if last is not None and self.internal_ticks - last < ticks_required:
            return False

    # game_ticks constraint
    if game_ticks_required is not None:
        last = self.adventure_last_completed_game_ticks.get(adventure_ref)
        if last is not None and self.game_ticks - last < game_ticks_required:
            return False

    # seconds (real-world) constraint
    if seconds_required is not None:
        last = self.adventure_last_completed_real_ts.get(adventure_ref)
        if last is not None and now_ts - last < seconds_required:
            return False

    return True
```

All callers of `is_adventure_eligible` pass `now_ts=int(time.time())`. The `today` parameter is removed.

**`to_dict` — before (relevant fields):**

```python
return {
    # ...
    "milestones": sorted(self.milestones),
    "skill_cooldowns": dict(self.skill_cooldowns),
    "adventure_last_completed_on": dict(self.adventure_last_completed_on),
    "adventure_last_completed_at_ticks": dict(self.adventure_last_completed_at_ticks),
    # ...
}
```

**After:**

```python
return {
    # ...
    "milestones": {name: {"tick": r.tick, "timestamp": r.timestamp} for name, r in self.milestones.items()},
    "skill_tick_expiry": dict(self.skill_tick_expiry),
    "skill_real_expiry": dict(self.skill_real_expiry),
    "adventure_last_completed_real_ts": dict(self.adventure_last_completed_real_ts),
    "adventure_last_completed_at_ticks": dict(self.adventure_last_completed_at_ticks),
    "adventure_last_completed_game_ticks": dict(self.adventure_last_completed_game_ticks),
    # ...
}
```

**`from_dict` — milestone backward compatibility:**

```python
from oscilla.engine.models.base import MilestoneRecord

# Milestones support three serialized formats.
raw_milestones = data.get("milestones", [])
if isinstance(raw_milestones, list):
    # Old format: list of milestone names (pre-tick-system saves).
    milestones: Dict[str, MilestoneRecord] = {
        name: MilestoneRecord(tick=0, timestamp=0) for name in raw_milestones
    }
else:
    milestones = {}
    for name, value in raw_milestones.items():
        if isinstance(value, int):
            # Intermediate format: {name: tick_int} — graceful migration if deployed before MilestoneRecord.
            milestones[name] = MilestoneRecord(tick=value, timestamp=0)
        else:
            milestones[name] = MilestoneRecord(**value)
```

**`from_dict` — `__game__` prefix migration:**

```python
raw_at_ticks: Dict[str, int] = dict(
    data.get("adventure_last_completed_at_ticks") or data.get("adventure_last_completed_at_total", {})
)
# Migrate __game__ entries out of adventure_last_completed_at_ticks.
raw_game_ticks: Dict[str, int] = {}
clean_at_ticks: Dict[str, int] = {}
for key, value in raw_at_ticks.items():
    if key.startswith("__game__"):
        raw_game_ticks[key[len("__game__"):]] = value
    else:
        clean_at_ticks[key] = value
# Merge with the new dedicated key if present.
raw_game_ticks.update(data.get("adventure_last_completed_game_ticks", {}))
```

### `oscilla/engine/conditions.py` — `milestone_ticks_elapsed` evaluator

**Before (import and milestone branch):**

```python
from oscilla.engine.models.base import (
    # ...
    MilestoneCondition,
    # ...
)

# in evaluate():
case MilestoneCondition(name=n):
    return n in player.milestones
```

**After:**

```python
from oscilla.engine.models.base import (
    # ...
    MilestoneCondition,
    MilestoneTicksElapsedCondition,
    # ...
)

# in evaluate():
case MilestoneCondition(name=n):
    return n in player.milestones

case MilestoneTicksElapsedCondition(name=n, gte=gte, lte=lte):
    record = player.milestones.get(n)
    if record is None:
        # Milestone not granted → condition is False regardless of comparators.
        return False
    elapsed = player.internal_ticks - record.tick
    if gte is not None and elapsed < gte:
        return False
    if lte is not None and elapsed > lte:
        return False
    return True
```

### `oscilla/engine/pipeline.py` — tick snapshot recording

**Before:**

```python
self._player.internal_ticks += tick_cost
self._player.game_ticks += tick_cost
# Record internal_ticks snapshot for cooldown evaluation.
self._player.adventure_last_completed_at_ticks[adventure_ref] = self._player.internal_ticks
```

**After:**

```python
import time as _time

self._player.internal_ticks += tick_cost
self._player.game_ticks += tick_cost
# Record completion timestamps for cooldown evaluation.
self._player.adventure_last_completed_at_ticks[adventure_ref] = self._player.internal_ticks
self._player.adventure_last_completed_game_ticks[adventure_ref] = self._player.game_ticks
# Real-world timestamp recorded in session.py via _run_adventure (after pipeline returns).
```

### `oscilla/engine/session.py` — real-world timestamp write

**Before:**

```python
self._character.adventure_last_completed_on[adventure_ref] = _date.today().isoformat()
```

**After:**

```python
import time as _time

self._character.adventure_last_completed_real_ts[adventure_ref] = int(_time.time())
```

The `_date` (datetime.date) import is removed from session.py if no longer needed elsewhere.

**`_persist_diff` — before (milestone section):**

```python
last_milestones = last.milestones if last is not None else set()
for milestone_ref in state.milestones - last_milestones:
    await add_milestone(
        session=self.db_session,
        iteration_id=iteration_id,
        milestone_ref=milestone_ref,
    )
```

**After:**

```python
last_milestones = last.milestones if last is not None else {}
for milestone_ref, record in state.milestones.items():
    if milestone_ref not in last_milestones:
        await add_milestone(
            session=self.db_session,
            iteration_id=iteration_id,
            milestone_ref=milestone_ref,
            grant_tick=record.tick,
            grant_timestamp=record.timestamp,
        )
```

Re-granting is a no-op in `grant_milestone()`, so we only ever diff additions (never updates), matching the original set-subtraction behavior.

**`_persist_diff` — before (skill_cooldowns section):**

```python
last_cooldowns = last.skill_cooldowns if last is not None else {}
for skill_ref, remaining in state.skill_cooldowns.items():
    if remaining != last_cooldowns.get(skill_ref):
        await set_skill_cooldown(
            session=self.db_session,
            iteration_id=iteration_id,
            skill_ref=skill_ref,
            cooldown_remaining=remaining,
        )
for skill_ref in last_cooldowns:
    if skill_ref not in state.skill_cooldowns:
        await set_skill_cooldown(
            session=self.db_session,
            iteration_id=iteration_id,
            skill_ref=skill_ref,
            cooldown_remaining=0,
        )
```

**After (skill_tick_expiry and skill_real_expiry — single combined row per skill):**

```python
last_tick_expiry = last.skill_tick_expiry if last is not None else {}
last_real_expiry = last.skill_real_expiry if last is not None else {}
all_skill_refs = set(state.skill_tick_expiry) | set(state.skill_real_expiry)
for skill_ref in all_skill_refs:
    tick_exp = state.skill_tick_expiry.get(skill_ref, 0)
    real_exp = state.skill_real_expiry.get(skill_ref, 0)
    if tick_exp != last_tick_expiry.get(skill_ref, 0) or real_exp != last_real_expiry.get(skill_ref, 0):
        await set_skill_cooldown(
            session=self.db_session,
            iteration_id=iteration_id,
            skill_ref=skill_ref,
            tick_expiry=tick_exp,
            real_expiry=real_exp,
        )
# Delete rows for skills that dropped off entirely (cooldown expired and was cleared).
for skill_ref in set(last_tick_expiry) | set(last_real_expiry):
    if skill_ref not in state.skill_tick_expiry and skill_ref not in state.skill_real_expiry:
        await set_skill_cooldown(
            session=self.db_session,
            iteration_id=iteration_id,
            skill_ref=skill_ref,
            tick_expiry=0,
            real_expiry=0,
        )
```

**`_persist_diff` — before (adventure state diff):**

```python
last_completed_on = last.adventure_last_completed_on if last is not None else {}
last_completed_at_ticks = last.adventure_last_completed_at_ticks if last is not None else {}
for adventure_ref, completed_on in state.adventure_last_completed_on.items():
    if completed_on != last_completed_on.get(adventure_ref) or ...:
        await upsert_adventure_state(
            session=self.db_session,
            iteration_id=iteration_id,
            adventure_ref=adventure_ref,
            last_completed_on=completed_on,
            last_completed_at_ticks=state.adventure_last_completed_at_ticks.get(adventure_ref),
        )
```

**After:**

```python
last_real_ts = last.adventure_last_completed_real_ts if last is not None else {}
last_at_ticks = last.adventure_last_completed_at_ticks if last is not None else {}
last_game_ticks = last.adventure_last_completed_game_ticks if last is not None else {}
all_refs = (
    set(state.adventure_last_completed_real_ts)
    | set(state.adventure_last_completed_at_ticks)
    | set(state.adventure_last_completed_game_ticks)
)
for adventure_ref in all_refs:
    real_ts = state.adventure_last_completed_real_ts.get(adventure_ref)
    at_ticks = state.adventure_last_completed_at_ticks.get(adventure_ref)
    game_ticks = state.adventure_last_completed_game_ticks.get(adventure_ref)
    if (
        real_ts != last_real_ts.get(adventure_ref)
        or at_ticks != last_at_ticks.get(adventure_ref)
        or game_ticks != last_game_ticks.get(adventure_ref)
    ):
        await upsert_adventure_state(
            session=self.db_session,
            iteration_id=iteration_id,
            adventure_ref=adventure_ref,
            last_completed_real_ts=real_ts,
            last_completed_at_ticks=at_ticks,
            last_completed_game_ticks=game_ticks,
        )
```

### `oscilla/models/character_iteration.py` — database model changes

**`CharacterIterationMilestone` — before:**

```python
class CharacterIterationMilestone(Base):
    __tablename__ = "character_iteration_milestones"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    milestone_ref: Mapped[str] = mapped_column(String, primary_key=True)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="milestone_rows"
    )
```

**After:**

```python
class CharacterIterationMilestone(Base):
    __tablename__ = "character_iteration_milestones"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    milestone_ref: Mapped[str] = mapped_column(String, primary_key=True)
    # Tick and timestamp recorded at grant time. Both default to 0 (pre-tracking sentinel).
    grant_tick: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    grant_timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    iteration: Mapped["CharacterIterationRecord"] = relationship(
        "CharacterIterationRecord", back_populates="milestone_rows"
    )
```

**`CharacterIterationSkillCooldown` — before:**

```python
class CharacterIterationSkillCooldown(Base):
    __tablename__ = "character_iteration_skill_cooldowns"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    skill_ref: Mapped[str] = mapped_column(String, primary_key=True)
    cooldown_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
```

**After:**

```python
class CharacterIterationSkillCooldown(Base):
    __tablename__ = "character_iteration_skill_cooldowns"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    skill_ref: Mapped[str] = mapped_column(String, primary_key=True)
    # Absolute expiry values — set at use time. Row is deleted when the cooldown expires.
    tick_expiry: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    real_expiry: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
```

**`CharacterIterationAdventureState` — before:**

```python
class CharacterIterationAdventureState(Base):
    __tablename__ = "character_iteration_adventure_state"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    adventure_ref: Mapped[str] = mapped_column(String, primary_key=True)
    last_completed_on: Mapped[str | None] = mapped_column(String, nullable=True)      # ISO date
    last_completed_at_ticks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
```

**After:**

```python
class CharacterIterationAdventureState(Base):
    __tablename__ = "character_iteration_adventure_state"

    iteration_id: Mapped[UUID] = mapped_column(ForeignKey("character_iterations.id"), primary_key=True, nullable=False)
    adventure_ref: Mapped[str] = mapped_column(String, primary_key=True)
    # internal_ticks and game_ticks at last completion; real Unix timestamp of last completion.
    last_completed_at_ticks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_completed_game_ticks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_completed_real_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
```

### `oscilla/services/character.py` — service layer updates

**`add_milestone` — before:**

```python
async def add_milestone(
    session: AsyncSession,
    iteration_id: UUID,
    milestone_ref: str,
) -> None:
    await session.merge(
        CharacterIterationMilestone(
            iteration_id=iteration_id,
            milestone_ref=milestone_ref,
        )
    )
    await session.commit()
```

**After:**

```python
async def add_milestone(
    session: AsyncSession,
    iteration_id: UUID,
    milestone_ref: str,
    grant_tick: int,
    grant_timestamp: int,
) -> None:
    await session.merge(
        CharacterIterationMilestone(
            iteration_id=iteration_id,
            milestone_ref=milestone_ref,
            grant_tick=grant_tick,
            grant_timestamp=grant_timestamp,
        )
    )
    await session.commit()
```

**`set_skill_cooldown` — before:**

```python
async def set_skill_cooldown(
    session: AsyncSession,
    iteration_id: UUID,
    skill_ref: str,
    cooldown_remaining: int,
) -> None:
    if cooldown_remaining <= 0:
        # delete the row ...
    else:
        await session.merge(
            CharacterIterationSkillCooldown(
                iteration_id=iteration_id,
                skill_ref=skill_ref,
                cooldown_remaining=cooldown_remaining,
            )
        )
    await session.commit()
```

**After:**

```python
async def set_skill_cooldown(
    session: AsyncSession,
    iteration_id: UUID,
    skill_ref: str,
    tick_expiry: int,
    real_expiry: int,
) -> None:
    """Upsert (either expiry > 0) or delete (both expiry <= 0) one skill cooldown row."""
    if tick_expiry <= 0 and real_expiry <= 0:
        stmt = select(CharacterIterationSkillCooldown).where(
            and_(
                CharacterIterationSkillCooldown.iteration_id == iteration_id,
                CharacterIterationSkillCooldown.skill_ref == skill_ref,
            )
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            await session.delete(existing)
    else:
        await session.merge(
            CharacterIterationSkillCooldown(
                iteration_id=iteration_id,
                skill_ref=skill_ref,
                tick_expiry=tick_expiry,
                real_expiry=real_expiry,
            )
        )
    await session.commit()
```

**`upsert_adventure_state` — before:**

```python
async def upsert_adventure_state(
    session: AsyncSession,
    iteration_id: UUID,
    adventure_ref: str,
    last_completed_on: str | None,
    last_completed_at_ticks: int | None,
) -> None:
    await session.merge(
        CharacterIterationAdventureState(
            iteration_id=iteration_id,
            adventure_ref=adventure_ref,
            last_completed_on=last_completed_on,
            last_completed_at_ticks=last_completed_at_ticks,
        )
    )
    await session.commit()
```

**After:**

```python
async def upsert_adventure_state(
    session: AsyncSession,
    iteration_id: UUID,
    adventure_ref: str,
    last_completed_at_ticks: int | None,
    last_completed_game_ticks: int | None,
    last_completed_real_ts: int | None,
) -> None:
    await session.merge(
        CharacterIterationAdventureState(
            iteration_id=iteration_id,
            adventure_ref=adventure_ref,
            last_completed_at_ticks=last_completed_at_ticks,
            last_completed_game_ticks=last_completed_game_ticks,
            last_completed_real_ts=last_completed_real_ts,
        )
    )
    await session.commit()
```

**`load_character` — relevant deserialization fragments — before:**

```python
# Milestones — produces a flat list
milestones: List[str] = [row.milestone_ref for row in iteration.milestone_rows]

# Skill cooldowns — countdown integer
skill_cooldowns: Dict[str, int] = {row.skill_ref: row.cooldown_remaining for row in iteration.skill_cooldown_rows}

# Adventure state — two separate dicts from one table
adventure_last_completed_on: Dict[str, str] = {
    row.adventure_ref: row.last_completed_on
    for row in iteration.adventure_state_rows
    if row.last_completed_on is not None
}
adventure_last_completed_at_ticks: Dict[str, int] = {
    row.adventure_ref: row.last_completed_at_ticks
    for row in iteration.adventure_state_rows
    if row.last_completed_at_ticks is not None
}
```

Then passed as:

```python
data: Dict[str, Any] = {
    "milestones": milestones,               # List[str]
    "skill_cooldowns": skill_cooldowns,
    "adventure_last_completed_on": adventure_last_completed_on,
    "adventure_last_completed_at_ticks": adventure_last_completed_at_ticks,
    ...
}
```

**After:**

```python
# Milestones — produces nested dict {name: {"tick": N, "timestamp": N}}
milestones: Dict[str, Dict[str, int]] = {
    row.milestone_ref: {"tick": row.grant_tick, "timestamp": row.grant_timestamp}
    for row in iteration.milestone_rows
}

# Skill cooldowns — two expiry-timestamp dicts
skill_tick_expiry: Dict[str, int] = {
    row.skill_ref: row.tick_expiry for row in iteration.skill_cooldown_rows if row.tick_expiry > 0
}
skill_real_expiry: Dict[str, int] = {
    row.skill_ref: row.real_expiry for row in iteration.skill_cooldown_rows if row.real_expiry > 0
}

# Adventure state — three separate dicts from one table
adventure_last_completed_at_ticks: Dict[str, int] = {
    row.adventure_ref: row.last_completed_at_ticks
    for row in iteration.adventure_state_rows
    if row.last_completed_at_ticks is not None
}
adventure_last_completed_game_ticks: Dict[str, int] = {
    row.adventure_ref: row.last_completed_game_ticks
    for row in iteration.adventure_state_rows
    if row.last_completed_game_ticks is not None
}
adventure_last_completed_real_ts: Dict[str, int] = {
    row.adventure_ref: row.last_completed_real_ts
    for row in iteration.adventure_state_rows
    if row.last_completed_real_ts is not None
}
```

Then passed as:

```python
data: Dict[str, Any] = {
    "milestones": milestones,               # Dict[str, Dict[str, int]] — bypasses from_dict list compat
    "skill_tick_expiry": skill_tick_expiry,
    "skill_real_expiry": skill_real_expiry,
    "adventure_last_completed_at_ticks": adventure_last_completed_at_ticks,
    "adventure_last_completed_game_ticks": adventure_last_completed_game_ticks,
    "adventure_last_completed_real_ts": adventure_last_completed_real_ts,
    ...
}
```

Note: `load_character` produces the current nested-dict milestone format directly, so the list-migration branch in `from_dict` is only exercised by legacy file-based saves, not the normal DB load path.

### `oscilla/engine/actions.py` — overworld skill cooldown checks

**Before (adventure-scope cooldown check):**

```python
# in the display loop:
if spec.cooldown is not None:
    remaining = player.skill_cooldowns.get(ref, 0)
    if spec.cooldown.scope == "adventure":
        if remaining > 0:
            cooldown_label = f"On cooldown ({remaining} adventure(s) remaining)"
        else:
            cooldown_label = f"Once per {spec.cooldown.count} adventure(s)"
    else:
        cooldown_label = f"Once per {spec.cooldown.count} turn(s) (combat only)"

# availability check:
if spec.cooldown is not None and spec.cooldown.scope == "adventure":
    if player.skill_cooldowns.get(ref, 0) > 0:
        available = False

# pre-use validation:
if spec.cooldown is not None and spec.cooldown.scope == "adventure":
    remaining_adv = player.skill_cooldowns.get(skill_ref, 0)
    if remaining_adv > 0:
        await tui.show_text(...)
        return

# record cooldown after use:
if spec.cooldown is not None and spec.cooldown.scope == "adventure":
    player.skill_cooldowns[skill_ref] = spec.cooldown.count
```

**After:**

```python
import time as _time

def _skill_on_cooldown(player: "CharacterState", skill_ref: str) -> bool:
    """Return True if the named skill is currently on adventure-scope cooldown."""
    tick_expiry = player.skill_tick_expiry.get(skill_ref)
    if tick_expiry is not None and player.internal_ticks < tick_expiry:
        return True
    real_expiry = player.skill_real_expiry.get(skill_ref)
    if real_expiry is not None and int(_time.time()) < real_expiry:
        return True
    return False


def _set_skill_cooldown(
    player: "CharacterState",
    skill_ref: str,
    cooldown: "Cooldown",
    template_engine: "GameTemplateEngine | None" = None,
) -> None:
    """Record adventure-scope skill cooldown expiry timestamps after use.

    scope: "turn" cooldowns are managed by CombatContext — do not call this for
    turn-scoped skills.
    """
    def _resolve(v: int | str | None) -> int | None:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if template_engine is None:
            logger.warning("Cooldown field %r is a template string but no engine provided.", v)
            return 0
        return int(template_engine.render_int(v, context={}))

    ticks_required = _resolve(cooldown.ticks)
    game_ticks_required = _resolve(cooldown.game_ticks)
    seconds_required = _resolve(cooldown.seconds)

    if ticks_required is not None:
        player.skill_tick_expiry[skill_ref] = player.internal_ticks + ticks_required
    if seconds_required is not None:
        player.skill_real_expiry[skill_ref] = int(_time.time()) + seconds_required
    # game_ticks is not tracked for skills — game_ticks can be adjusted by effects,
    # making it unsuitable as an expiry anchor. Only ticks and seconds are supported.
    if game_ticks_required is not None:
        logger.warning(
            "Skill %r specifies game_ticks cooldown which is not supported for skills. "
            "Use ticks or seconds instead.",
            skill_ref,
        )

# in the display loop:
if spec.cooldown is not None and spec.cooldown.scope != "turn":
    on_cd = _skill_on_cooldown(player, ref)
    if on_cd:
        cooldown_label = "On cooldown"
    else:
        cooldown_label = "Adventure cooldown active"

# availability check:
if spec.cooldown is not None and spec.cooldown.scope != "turn":
    if _skill_on_cooldown(player, ref):
        available = False

# pre-use validation:
if spec.cooldown is not None and spec.cooldown.scope != "turn":
    if _skill_on_cooldown(player, skill_ref):
        await tui.show_text(f"[yellow]{spec.displayName} is on cooldown.[/yellow]")
        return

# record cooldown after use:
if spec.cooldown is not None and spec.cooldown.scope != "turn":
    _set_skill_cooldown(player, skill_ref, spec.cooldown, registry.template_engine)
```

### `oscilla/engine/steps/combat.py` — combat skill cooldown checks

**Before (adventure-scope branch in `_use_skill_in_combat`):**

```python
if spec.cooldown is not None and spec.cooldown.scope == "adventure":
    remaining_adv = player.skill_cooldowns.get(skill_ref, 0)
    if remaining_adv > 0:
        await tui.show_text(...)
        return False

# record cooldown after use:
if spec.cooldown is not None:
    if spec.cooldown.scope == "turn":
        ctx.skill_uses_this_combat[skill_ref] = ctx.turn_number
    else:  # adventure
        player.skill_cooldowns[skill_ref] = spec.cooldown.count
```

**After:**

```python
from oscilla.engine.actions import _skill_on_cooldown, _set_skill_cooldown

if spec.cooldown is not None and spec.cooldown.scope != "turn":
    if _skill_on_cooldown(player, skill_ref):
        await tui.show_text(f"[yellow]{spec.displayName} is on cooldown.[/yellow]")
        return False

# record cooldown after use:
if spec.cooldown is not None:
    if spec.cooldown.scope == "turn":
        ctx.skill_uses_this_combat[skill_ref] = ctx.turn_number
    else:
        _set_skill_cooldown(player, skill_ref, spec.cooldown, registry.template_engine)
```

### `oscilla/engine/steps/effects.py` — prestige effect clears skill expiry

**Before:**

```python
player.skill_cooldowns = {}
```

**After:**

```python
player.skill_tick_expiry = {}
player.skill_real_expiry = {}
```

### `oscilla/engine/templates.py` — time constants in `SAFE_GLOBALS`

**Before:**

```python
SAFE_GLOBALS: Dict[str, Any] = {
    "roll": _safe_roll,
    # ...
    "moon_phase": calendar_utils.moon_phase,
}
```

**After:**

```python
# Common real-world time multiples for authored cooldown expressions.
SECONDS_PER_MINUTE: int = 60
SECONDS_PER_HOUR: int = 3_600
SECONDS_PER_DAY: int = 86_400
SECONDS_PER_WEEK: int = 604_800

SAFE_GLOBALS: Dict[str, Any] = {
    "roll": _safe_roll,
    # ...
    "moon_phase": calendar_utils.moon_phase,
    # Time constants for authored cooldown expressions.
    "SECONDS_PER_MINUTE": SECONDS_PER_MINUTE,
    "SECONDS_PER_HOUR": SECONDS_PER_HOUR,
    "SECONDS_PER_DAY": SECONDS_PER_DAY,
    "SECONDS_PER_WEEK": SECONDS_PER_WEEK,
}
```

The constants are already included via `SAFE_GLOBALS` in `build_mock_context()` since that function calls `ctx.update(SAFE_GLOBALS)`.

---

## Edge Cases

**`milestone_ticks_elapsed` with ungranted milestone:** Returns `False` — the player has no grant tick to compare against. This is correct; "3 ticks since X" can only be True if X has been granted.

**Milestone re-grant:** `grant_milestone()` is a no-op if already held (`if name not in self.milestones`). The original `MilestoneRecord` (tick and timestamp) is preserved. This matches the existing `Set.add()` behavior semantically.

**`from_dict` with old milestone list format:** Migrated to `MilestoneRecord(tick=0, timestamp=0)` per entry. Tick=0 means "before the tick system" — `milestone_ticks_elapsed` conditions will see `elapsed = current_ticks - 0 = current_ticks`, which means old milestones will satisfy any `gte` condition once enough ticks have passed. This is a reasonable migration behavior; authors are unlikely to have conditions that check recently-earned milestones on a freshly migrated save.

**`from_dict` with intermediate int-dict milestone format:** Migrated to `MilestoneRecord(tick=N, timestamp=0)` per entry. Timestamp=0 is the sentinel for "granted before timestamp tracking." This handles any save data from a deployment using the `Dict[str, int]` design before `MilestoneRecord` was introduced.

**Skill cooldown `game_ticks` field:** Logged as a warning and ignored. Game ticks are adjustable by effects, making them unsuitable as a "time since event" anchor for skill reuse. If an author specifies this, they get a warning at use time.

**Template string cooldown with no engine:** Logged as a warning; treated as 0 (no cooldown). Only occurs in tests that bypass the registry. Production always has a template engine.

**`is_adventure_eligible` with str-typed cooldown and no template engine:** Treats the cooldown as 0 (no restriction). The template engine is only absent in unit test scenarios that construct minimal state — production paths always pass the engine.

**Adventure not yet completed (no entry in `adventure_last_completed_at_ticks`):** `last is None` → constraint passes. Adventures that have never been run are always eligible (subject to `requires` and capacity limits).

---

## Migration Plan

**Alembic schema migration required.** Three tables need column-level changes. No data migration is necessary (per confirmed absence of live deployments), but the schema must be updated via a single new Alembic migration so the tables match the new service layer.

### Database schema changes

**`character_iteration_milestones`** — add grant-time columns:

```sql
ALTER TABLE character_iteration_milestones ADD COLUMN grant_tick BIGINT NOT NULL DEFAULT 0;
ALTER TABLE character_iteration_milestones ADD COLUMN grant_timestamp BIGINT NOT NULL DEFAULT 0;
```

Existing rows get `tick=0, timestamp=0` — the same sentinel values used by `from_dict` migration.

**`character_iteration_skill_cooldowns`** — replace countdown with expiry timestamps:

```sql
ALTER TABLE character_iteration_skill_cooldowns DROP COLUMN cooldown_remaining;
ALTER TABLE character_iteration_skill_cooldowns ADD COLUMN tick_expiry BIGINT NOT NULL DEFAULT 0;
ALTER TABLE character_iteration_skill_cooldowns ADD COLUMN real_expiry BIGINT NOT NULL DEFAULT 0;
```

**`character_iteration_adventure_state`** — replace ISO date string with Unix timestamp; add game-ticks column:

```sql
ALTER TABLE character_iteration_adventure_state DROP COLUMN last_completed_on;
ALTER TABLE character_iteration_adventure_state ADD COLUMN last_completed_real_ts BIGINT;
ALTER TABLE character_iteration_adventure_state ADD COLUMN last_completed_game_ticks BIGINT;
```

Alembic must express all of these as `op.add_column` / `op.drop_column` calls compatible with both SQLite and PostgreSQL.

**Content migration (testlandia + content packages):**

All adventure manifests using `cooldown_days`, `cooldown_ticks`, or `cooldown_game_ticks` must be updated to the nested `cooldown:` format:

```yaml
# Before
cooldown_ticks: 5

# After
cooldown:
  ticks: 5
```

```yaml
# Before
cooldown_days: 1

# After
cooldown:
  seconds: "{{ SECONDS_PER_DAY }}"
```

All skill manifests using `SkillCooldown` must be updated:

```yaml
# Before
cooldown:
  scope: adventure
  count: 3

# After
cooldown:
  ticks: 3
```

```yaml
# Before
cooldown:
  scope: turn
  count: 2

# After
cooldown:
  scope: turn
  turns: 2
```

---

## Risks / Trade-offs

| Risk                                                                 | Mitigation                                                                                                     |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Content authors with existing manifests must update to nested schema | All changes are pre-v1 and there are no live packages; testlandia is explicitly updated as part of this change |
| `game_ticks` not supported as skill expiry anchor                    | Documented behavior with warning at runtime; `ticks` or `seconds` cover all real use cases                     |
| Old serialized saves (milestone as list) loaded after this change    | `from_dict` detects list and migrates to `{name: 0}` dict with a warning per entry                             |
| `__game__` prefix entries left in serialized adventure ticks dict    | `from_dict` strips prefix and merges into new `adventure_last_completed_game_ticks` transparently              |
| Template-string cooldown resolved to 0 when no engine                | Only in test scenarios without a registry; acceptable, documented                                              |

---

## Documentation Plan

### New document: `docs/authors/cooldowns.md`

- **Audience:** Content authors
- **Topics:** Unified `cooldown:` schema syntax; difference between `ticks`, `game_ticks`, `seconds`, `turns`; `scope: turn` behavior; template expressions in cooldown fields; `SECONDS_PER_*` constants reference; adventure vs skill usage examples; migration guide from old flat fields.

### Updated document: `docs/authors/adventures.md`

- **Audience:** Content authors
- **Topics:** Update repeat-controls section: replace `cooldown_days`, `cooldown_ticks`, `cooldown_game_ticks` with `cooldown:` block examples. Add cross-reference to `docs/authors/cooldowns.md`.

### Updated document: `docs/authors/skills.md`

- **Audience:** Content authors
- **Topics:** Update cooldown section: replace `scope: adventure, count: N` with `ticks: N` equivalent. Add cross-reference to `docs/authors/cooldowns.md`.

### Updated document: `docs/authors/conditions.md`

- **Audience:** Content authors
- **Topics:** Add `milestone_ticks_elapsed` condition documentation with `gte`/`lte` fields and usage examples. Clarify that `internal_ticks` is the monotone clock (distinct from `game_ticks`).

### Updated document: `docs/authors/templates.md`

- **Audience:** Content authors
- **Topics:** Add `SECONDS_PER_MINUTE`, `SECONDS_PER_HOUR`, `SECONDS_PER_DAY`, `SECONDS_PER_WEEK` to the built-in constants reference table.

### Updated document: `docs/dev/game-engine.md`

- **Audience:** Engine developers
- **Topics:** Document the two-track time model (internal_ticks vs Unix seconds); explain `CharacterState` timestamp fields; document the `Cooldown` model and where it resolves templates; describe `_skill_on_cooldown` and `_set_skill_cooldown` helper functions and their locations.

---

## Testing Philosophy

### Unit tests — `tests/engine/test_character.py`

Test `CharacterState` in isolation: no registry, no TUI, no DB.

```python
def test_grant_milestone_records_tick() -> None:
    state = CharacterState(...)
    state.internal_ticks = 42
    state.grant_milestone("joined-guild")
    record = state.milestones["joined-guild"]
    assert record.tick == 42
    assert record.timestamp > 0  # real Unix timestamp was recorded


def test_grant_milestone_noop_if_already_held() -> None:
    state = CharacterState(...)
    state.internal_ticks = 10
    state.grant_milestone("joined-guild")
    original_ts = state.milestones["joined-guild"].timestamp
    state.internal_ticks = 99
    state.grant_milestone("joined-guild")  # should not overwrite
    assert state.milestones["joined-guild"].tick == 10
    assert state.milestones["joined-guild"].timestamp == original_ts


def test_has_milestone_returns_true_for_granted() -> None:
    state = CharacterState(...)
    state.grant_milestone("test-milestone")
    assert state.has_milestone("test-milestone") is True


def test_has_milestone_returns_false_for_unknown() -> None:
    state = CharacterState(...)
    assert state.has_milestone("never-granted") is False


def test_from_dict_migrates_milestone_list() -> None:
    """Old milestone format was a list — must migrate to dict with tick=0."""
    data = {
        "milestones": ["milestone-a", "milestone-b"],
        # ... other required fields ...
    }
    state = CharacterState.from_dict(data, character_config=_make_char_config())
    assert state.milestones["milestone-a"] == MilestoneRecord(tick=0, timestamp=0)
    assert state.milestones["milestone-b"] == MilestoneRecord(tick=0, timestamp=0)


def test_from_dict_migrates_milestone_int_dict() -> None:
    """Intermediate format {name: int} migrates to MilestoneRecord(tick=N, timestamp=0)."""
    data = {
        "milestones": {"veteran": 42},
        # ... other required fields ...
    }
    state = CharacterState.from_dict(data, character_config=_make_char_config())
    assert state.milestones["veteran"] == MilestoneRecord(tick=42, timestamp=0)


def test_from_dict_migrates_game_prefix_from_at_ticks() -> None:
    """__game__ prefixed entries in adventure_last_completed_at_ticks must migrate."""
    data = {
        "adventure_last_completed_at_ticks": {
            "dungeon-raid": 15,
            "__game__dungeon-raid": 8,
        },
        # ...
    }
    state = CharacterState.from_dict(data, character_config=_make_char_config())
    assert state.adventure_last_completed_at_ticks == {"dungeon-raid": 15}
    assert state.adventure_last_completed_game_ticks == {"dungeon-raid": 8}


def test_is_adventure_eligible_ticks_cooldown() -> None:
    from oscilla.engine.models.adventure import AdventureSpec, Cooldown

    spec = _make_adventure_spec(cooldown=Cooldown(ticks=5))
    state = CharacterState(...)
    state.internal_ticks = 10
    state.adventure_last_completed_at_ticks["test-adv"] = 8  # 2 ticks ago
    state.statistics.adventures_completed["test-adv"] = 1
    assert state.is_adventure_eligible("test-adv", spec, now_ts=0) is False  # 2 < 5

    state.internal_ticks = 14  # 6 ticks elapsed
    assert state.is_adventure_eligible("test-adv", spec, now_ts=0) is True   # 6 >= 5


def test_is_adventure_eligible_seconds_cooldown() -> None:
    from oscilla.engine.models.adventure import AdventureSpec, Cooldown

    spec = _make_adventure_spec(cooldown=Cooldown(seconds=3600))
    state = CharacterState(...)
    BASE_TS = 1_700_000_000
    state.adventure_last_completed_real_ts["test-adv"] = BASE_TS
    state.statistics.adventures_completed["test-adv"] = 1
    assert state.is_adventure_eligible("test-adv", spec, now_ts=BASE_TS + 1800) is False
    assert state.is_adventure_eligible("test-adv", spec, now_ts=BASE_TS + 3600) is True
```

### Unit tests — `tests/engine/test_conditions.py`

```python
def test_milestone_ticks_elapsed_false_when_not_granted() -> None:
    from oscilla.engine.models.base import MilestoneTicksElapsedCondition
    from oscilla.engine.conditions import evaluate

    state = CharacterState(...)  # no milestones
    cond = MilestoneTicksElapsedCondition(type="milestone_ticks_elapsed", name="test", gte=0)
    assert evaluate(cond, state) is False


def test_milestone_ticks_elapsed_gte_pass() -> None:
    state = CharacterState(...)
    state.internal_ticks = 10
    state.grant_milestone("joined-guild")  # grant at tick 10
    state.internal_ticks = 20  # 10 ticks elapsed

    cond = MilestoneTicksElapsedCondition(type="milestone_ticks_elapsed", name="joined-guild", gte=5)
    assert evaluate(cond, state) is True


def test_milestone_ticks_elapsed_gte_fail() -> None:
    state = CharacterState(...)
    state.internal_ticks = 10
    state.grant_milestone("joined-guild")
    state.internal_ticks = 12  # 2 ticks elapsed

    cond = MilestoneTicksElapsedCondition(type="milestone_ticks_elapsed", name="joined-guild", gte=5)
    assert evaluate(cond, state) is False


def test_milestone_ticks_elapsed_lte() -> None:
    state = CharacterState(...)
    state.internal_ticks = 0
    state.grant_milestone("new-recruit")
    state.internal_ticks = 3

    cond = MilestoneTicksElapsedCondition(type="milestone_ticks_elapsed", name="new-recruit", lte=5)
    assert evaluate(cond, state) is True

    state.internal_ticks = 10
    assert evaluate(cond, state) is False
```

### Unit tests — `tests/engine/models/test_cooldown.py`

```python
def test_cooldown_turn_scope_rejects_ticks_field() -> None:
    with pytest.raises(ValidationError):
        Cooldown(scope="turn", turns=2, ticks=5)


def test_cooldown_no_scope_rejects_turns_field() -> None:
    with pytest.raises(ValidationError):
        Cooldown(ticks=5, turns=2)


def test_cooldown_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        Cooldown()


def test_cooldown_valid_ticks() -> None:
    cd = Cooldown(ticks=10)
    assert cd.ticks == 10
    assert cd.scope is None


def test_cooldown_valid_turn_scope() -> None:
    cd = Cooldown(scope="turn", turns=3)
    assert cd.turns == 3
    assert cd.scope == "turn"


def test_cooldown_template_string_accepted() -> None:
    cd = Cooldown(seconds="{{ SECONDS_PER_DAY }}")
    assert cd.seconds == "{{ SECONDS_PER_DAY }}"
```

### Integration tests — `tests/engine/test_skill_cooldown_integration.py`

These tests use `MockTUI` and a minimal fixture registry with a skill that has a `ticks`-type cooldown. They verify that after using a skill, the overworld action handler correctly marks it unavailable and marks it available again after advancing ticks.

```python
@pytest.fixture
def skill_cooldown_registry(mock_content_registry: ContentRegistry) -> ContentRegistry:
    """Registry with a single overworld skill with a ticks cooldown of 3."""
    # Build a minimal SkillManifest with cooldown=Cooldown(ticks=3) and inject into registry.
    # ...
    return mock_content_registry


@pytest.mark.asyncio
async def test_skill_unavailable_during_ticks_cooldown(
    skill_cooldown_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    state = CharacterState(...)
    state.known_skills.add("test-cooldown-skill")
    state.internal_ticks = 0

    # Use the skill.
    await handle_overworld_action(...)
    assert "test-cooldown-skill" in state.skill_tick_expiry
    assert state.skill_tick_expiry["test-cooldown-skill"] == 3  # 0 + 3

    # Tick forward by 2 — still on cooldown.
    state.internal_ticks = 2
    # ... check skill appears unavailable in menu ...

    # Tick forward past expiry.
    state.internal_ticks = 3
    # ... check skill appears available again ...
```

### Testlandia integration

See the Testlandia Integration section below.

---

## Testlandia Integration

The following content additions allow a developer to manually QA all new capabilities by playing through testlandia.

**File: `content/testlandia/adventures/test-cooldown-seconds.yaml`**

An adventure with `cooldown: seconds: "{{ SECONDS_PER_MINUTE }}"`. Demonstrates real-world cool-down with template constant. After completing it, attempting to run it again immediately shows it is unavailable; waiting 60 real seconds (or mocking time) makes it available again.

**File: `content/testlandia/adventures/test-cooldown-ticks.yaml`**

An adventure with `cooldown: ticks: 3`. After completing it, the next 2 adventures do not restore eligibility; completing a third restores it.

**File: `content/testlandia/adventures/test-milestone-timestamps.yaml`**

An adventure that:

1. Grants milestone `timestamp-test` via `milestone_grant` effect.
2. Has a follow-up step gated by `milestone_ticks_elapsed: {name: timestamp-test, gte: 2}` — visible only after completing 2 more adventures.

This allows a developer to verify that the condition evaluates correctly: the gated step is absent immediately after grant, and present after ticking forward.

**File: `content/testlandia/skills/`** (updated existing skill, or new `test-cooldown-skill.yaml`)

A skill with `cooldown: {ticks: 2}`. Demonstrates adventure-scoped skill cooldown actually working (the previously broken path). A developer can use the skill, see it marked unavailable, complete another adventure, see it still unavailable, complete one more, and see it become available.

**`content/testlandia/character_config.yaml`** — no changes required.

**`content/testlandia/game.yaml`** — no changes required.

---

## Open Questions

None — all design decisions have been confirmed by the developer.
