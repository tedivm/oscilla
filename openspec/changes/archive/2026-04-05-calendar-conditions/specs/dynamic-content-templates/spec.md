## MODIFIED Requirements

### Requirement: Templates have access to a read-only ExpressionContext

Templates SHALL receive an `ExpressionContext` at render time containing a `PlayerContext` (read-only projection of `CharacterState`), an optional `CombatContextView`, and a `GameContext` (read-only projection of `GameSpec`). Templates SHALL NOT be able to mutate any field on these objects.

The `PlayerContext` SHALL expose:

- `player.name` — character name (str)
- `player.level` — current level (int)
- `player.hp` — current HP (int)
- `player.max_hp` — max HP (int)
- `player.iteration` — current game iteration (int)
- `player.stats["<name>"]` — any stat from `CharacterConfig` (dict-subscript access)
- `player.milestones.has("<name>")` — milestone membership check (bool)
- `player.pronouns.<field>` — all pronoun fields (see pronoun-system spec)

The `GameContext` SHALL expose:

- `game.season_hemisphere` — `"northern"` or `"southern"`; defaults to `"northern"` when the game manifest does not declare it
- `game.timezone` — IANA timezone name string (e.g. `"America/New_York"`), or `None` when the game manifest does not declare a timezone

#### Scenario: Template accesses player name

- **WHEN** `{{ player.name }}` is rendered with a `PlayerContext` where `name = "Alex"`
- **THEN** the rendered output contains `"Alex"`

#### Scenario: Template accesses a stat by name

- **WHEN** `{{ player.stats['gold'] }}` is rendered with `stats = {"gold": 150}`
- **THEN** the rendered output contains `"150"`

#### Scenario: Template accesses a nonexistent stat

- **WHEN** a manifest template accesses `player.stats['nonexistent']` and `nonexistent` is not in `CharacterConfig`
- **THEN** `load()` raises a `ContentLoadError` during mock render

#### Scenario: Template accesses an invalid player property

- **WHEN** a manifest template accesses `player.inventory` (a property not in `PlayerContext`)
- **THEN** `load()` raises a `ContentLoadError` during mock render

#### Scenario: Combat context is available inside combat steps

- **WHEN** an effect or branch inside a `CombatStep` uses `{{ combat.turn }}`
- **THEN** `load()` validates it successfully and it renders correctly at runtime

#### Scenario: Combat context is unavailable outside combat steps

- **WHEN** a `NarrativeStep` template accesses `{{ combat.enemy_hp }}`
- **THEN** `load()` raises a `ContentLoadError` identifying the non-combat context

#### Scenario: Template accesses game season_hemisphere

- **WHEN** `{{ game.season_hemisphere }}` is rendered for a game with `season_hemisphere: southern`
- **THEN** the rendered output contains `"southern"`

#### Scenario: Template accesses invalid game property

- **WHEN** a manifest template accesses `game.xp_thresholds` (a property not in `GameContext`)
- **THEN** `load()` raises a `ContentLoadError` during mock render

---

### Requirement: Built-in safe functions are available in all templates

Templates SHALL have access to the following built-in functions without any import statement:

| Function | Signature | Description |
|----------|-----------|-------------|
| `roll(low, high)` | `(int, int) → int` | Random integer N where `low <= N <= high` |
| `choice(items)` | `(list) → any` | Random element from a list |
| `sample(items, k)` | `(list, int) → list` | `k` unique elements from a list, without replacement |
| `random()` | `() → float` | Random float in `[0.0, 1.0)` — familiar shorthand |
| `now()` | `() → datetime` | Current date and time in the game's configured timezone (server local time if `timezone` is not set) |
| `today()` | `() → date` | Current date in the game's configured timezone (server local time if `timezone` is not set) |
| `clamp(value, lo, hi)` | `(num, num, num) → num` | Clamps `value` to `[lo, hi]` |
| `round` | Python builtin | `round(value, ndigits=0)` |
| `sum` | Python builtin | `sum(iterable)` |
| `max`, `min` | Python builtins | Standard max/min |
| `floor`, `ceil`, `abs` | Python/math | Standard math functions |
| `range`, `len`, `int`, `str`, `bool` | Python builtins | Standard utilities |
| `season(date)` | `(date) → str` | Meteorological season respecting the game's `season_hemisphere` setting: `"spring"`, `"summer"`, `"autumn"`, or `"winter"` |
| `month_name(n)` | `(int) → str` | English month name (1 = `"January"` … 12 = `"December"`) |
| `day_name(n)` | `(int) → str` | English weekday name (0 = `"Monday"` … 6 = `"Sunday"`) |
| `week_number(date)` | `(date) → int` | ISO week number (1–53) |
| `mean(values)` | `(list) → float` | Arithmetic mean of a list of numbers |
| `zodiac_sign(date)` | `(date) → str` | Western zodiac sign (e.g. `"Aries"`, `"Scorpio"`) |
| `chinese_zodiac(year)` | `(int) → str` | Chinese zodiac animal (e.g. `"Rat"`, `"Dragon"`) |
| `moon_phase(date)` | `(date) → str` | Approximate lunar phase (e.g. `"Full Moon"`, `"Waxing Crescent"`) |

All other Python builtins, modules, and dunder attributes SHALL be blocked by the sandbox.

#### Scenario: roll() returns integer in range

- **WHEN** `{{ roll(1, 6) }}` is rendered
- **THEN** the output is an integer string between `"1"` and `"6"` (inclusive) on every call

#### Scenario: roll() with reversed arguments fails at validation

- **WHEN** a template contains `{{ roll(10, 1) }}`
- **THEN** `load()` raises a `ContentLoadError` (mock render raises `ValueError`)

#### Scenario: choice() selects from a list

- **WHEN** `{{ choice(["sword", "shield", "potion"]) }}` is rendered
- **THEN** the output is one of `"sword"`, `"shield"`, or `"potion"`

#### Scenario: random() returns float in [0.0, 1.0)

- **WHEN** `{{ random() }}` is rendered
- **THEN** the output is a float string representing a value in `[0.0, 1.0)`

#### Scenario: now() returns current datetime in game timezone

- **WHEN** `{{ now().year }}` is rendered for a game with `timezone: "Asia/Tokyo"`
- **THEN** the output is the current four-digit year as seen from Tokyo (which may differ from the server year near midnight)

#### Scenario: today() returns current date in game timezone

- **WHEN** `{{ today().month }}` is rendered for a game with `timezone: "Asia/Tokyo"`
- **THEN** the output is the current month number as seen from Tokyo

#### Scenario: sample() returns k unique elements

- **WHEN** `{{ sample(['sword', 'shield', 'potion', 'key'], 2) }}` is rendered
- **THEN** the output contains exactly 2 distinct elements from the list

#### Scenario: sample() with k larger than list raises ContentLoadError

- **WHEN** a template contains `{{ sample(['a', 'b'], 5) }}`
- **THEN** `load()` raises a `ContentLoadError` (mock render raises `ValueError`)

#### Scenario: clamp() keeps value within bounds

- **WHEN** `{{ clamp(player.hp + 50, 0, player.max_hp) }}` is rendered for a player with `hp=80, max_hp=100`
- **THEN** the output is `"100"` (clamped to max_hp)

#### Scenario: clamp() with lo > hi raises ContentLoadError

- **WHEN** a template contains `{{ clamp(5, 10, 0) }}`
- **THEN** `load()` raises a `ContentLoadError` (mock render raises `ValueError`)

#### Scenario: round() rounds a float to nearest integer

- **WHEN** `{{ round(3.7) }}` is rendered
- **THEN** the output is `"4"`

#### Scenario: sum() totals a list of values

- **WHEN** `{{ sum([player.stats['strength'], player.stats['dexterity']]) }}` is rendered with both stats equal to `10`
- **THEN** the output is `"20"`

#### Scenario: season() uses game hemisphere setting

- **WHEN** `{{ season(today()) }}` is rendered in July for a game with `season_hemisphere: southern`
- **THEN** the output is `"winter"`

#### Scenario: season() defaults to northern hemisphere

- **WHEN** `{{ season(today()) }}` is rendered in July for a game with no `season_hemisphere` declared
- **THEN** the output is `"summer"`

#### Scenario: season() respects game timezone for today()

- **WHEN** `{{ season(today()) }}` is rendered at 23:30 server time on June 30 for a game with `timezone: "Pacific/Auckland"` (where it is already July 1)
- **THEN** the output reflects July (summer in northern / winter in southern), not June

#### Scenario: month_name() returns the correct English month name

- **WHEN** `{{ month_name(3) }}` is rendered
- **THEN** the output is `"March"`

#### Scenario: month_name() with out-of-range argument raises ContentLoadError

- **WHEN** a template contains `{{ month_name(13) }}`
- **THEN** `load()` raises a `ContentLoadError` (mock render raises `ValueError`)

#### Scenario: day_name() returns the correct English weekday name

- **WHEN** `{{ day_name(0) }}` is rendered
- **THEN** the output is `"Monday"`

#### Scenario: week_number() returns a plausible ISO week number

- **WHEN** `{{ week_number(today()) }}` is rendered
- **THEN** the output is an integer string in the range `"1"` to `"53"`

#### Scenario: mean() returns the arithmetic average

- **WHEN** `{{ mean([10, 20, 30]) }}` is rendered
- **THEN** the output is `"20"`

#### Scenario: zodiac_sign() returns a valid sign name

- **WHEN** `{{ zodiac_sign(today()) }}` is rendered
- **THEN** the output is one of the twelve Western zodiac sign names
