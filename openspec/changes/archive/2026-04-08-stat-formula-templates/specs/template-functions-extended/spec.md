## ADDED Requirements

### Requirement: Dice pool functions available in all templates

The following dice pool functions SHALL be added to `SAFE_GLOBALS` and available in all template evaluation contexts:

| Function                                           | Signature                                      | Description                                                                                                  |
| -------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `roll_pool(n, sides)`                              | `(int, int) → List[int]`                       | Roll `n` dice each with `sides` faces; returns list of individual results                                    |
| `keep_highest(pool, n)`                            | `(List[int], int) → List[int]`                 | Return the `n` highest values from pool (sorted descending)                                                  |
| `keep_lowest(pool, n)`                             | `(List[int], int) → List[int]`                 | Return the `n` lowest values from pool (sorted ascending)                                                    |
| `count_successes(pool, threshold)`                 | `(List[int], int) → int`                       | Count dice in pool with value `>= threshold`                                                                 |
| `explode(pool, sides, on=None, max_explosions=10)` | `(List[int], int, int\|None, int) → List[int]` | Re-roll dice that land on `on` (default: `sides`) and append results; capped at `max_explosions` extra rolls |
| `roll_fudge(n)`                                    | `(int,) → List[int]`                           | Roll `n` FATE/Fudge dice; each result is `-1`, `0`, or `1` with equal probability                            |
| `weighted_roll(options, weights)`                  | `(List, List[int\|float]) → any`               | Return one element from `options` chosen according to `weights`                                              |

All functions SHALL raise `ValueError` for invalid arguments (e.g. `n < 1`, mismatched list lengths). `ValueError` raised during mock render at load time SHALL be a content load error.

#### Scenario: roll_pool returns correct count and valid range

- **WHEN** `{{ roll_pool(3, 6) | sum }}` is rendered
- **THEN** the output is an integer between `3` and `18` inclusive

#### Scenario: keep_highest returns n largest in descending order

- **WHEN** `{{ keep_highest([1, 5, 3, 4], 2) }}` is rendered
- **THEN** the output represents `[5, 4]`

#### Scenario: keep_lowest returns n smallest in ascending order

- **WHEN** `{{ keep_lowest([1, 5, 3, 4], 2) }}` is rendered
- **THEN** the output represents `[1, 3]`

#### Scenario: count_successes counts values at or above threshold

- **WHEN** `{{ count_successes([3, 5, 2, 6], 5) }}` is rendered
- **THEN** the output is `"2"`

#### Scenario: explode appends additional results for max-face rolls

- **WHEN** `{{ explode([6, 3], 6) }}` is rendered
- **THEN** the output list is at least 2 elements long (the 6 triggers at least one extra roll)

#### Scenario: roll_fudge returns values only in {-1, 0, 1}

- **WHEN** `{{ roll_fudge(4) }}` is rendered
- **THEN** every element of the result is in `{-1, 0, 1}` and the list has 4 elements

#### Scenario: weighted_roll with mismatched lengths is a load error

- **WHEN** a template contains `{{ weighted_roll(['a', 'b'], [50]) }}`
- **THEN** `load()` raises a `ContentLoadError` (mock render raises `ValueError`)

---

### Requirement: Die shorthand aliases available in all templates

The following single-die shorthand functions SHALL be added to `SAFE_GLOBALS`:

| Function | Returns                  |
| -------- | ------------------------ |
| `d4()`   | Random int in `[1, 4]`   |
| `d6()`   | Random int in `[1, 6]`   |
| `d8()`   | Random int in `[1, 8]`   |
| `d10()`  | Random int in `[1, 10]`  |
| `d12()`  | Random int in `[1, 12]`  |
| `d20()`  | Random int in `[1, 20]`  |
| `d100()` | Random int in `[1, 100]` |

These are ergonomic aliases for `roll(1, N)`. They use the same secure PRNG as `roll()`.

#### Scenario: d20() returns value in valid die range

- **WHEN** `{{ d20() }}` is rendered
- **THEN** the output is an integer string between `"1"` and `"20"` inclusive

#### Scenario: d6() usable in effect amount expressions

- **WHEN** a `stat_change` effect has `amount: "{{ d6() }}"` and the stat exists
- **THEN** `load()` compiles and mock-renders the template without error

---

### Requirement: Display and numeric helper functions available in all templates

The following display and conversion helper functions SHALL be added to `SAFE_GLOBALS`:

| Function          | Signature            | Description                                                                                   |
| ----------------- | -------------------- | --------------------------------------------------------------------------------------------- |
| `ordinal(n)`      | `(int) → str`        | English ordinal string: `1 → "1st"`, `2 → "2nd"`, `11 → "11th"`, `13 → "13th"`, `21 → "21st"` |
| `signed(n)`       | `(int\|float) → str` | Signed display string: `5 → "+5"`, `-3 → "-3"`, `0 → "0"`                                     |
| `stat_mod(value)` | `(int) → int`        | D&D-style ability modifier: `floor((value - 10) / 2)`                                         |

These functions raise `ValueError` for non-numeric input; this is caught at load-time mock render.

#### Scenario: ordinal handles teen numbers correctly

- **WHEN** `{{ ordinal(11) }}`, `{{ ordinal(12) }}`, `{{ ordinal(13) }}` are rendered
- **THEN** the outputs are `"11th"`, `"12th"`, `"13th"` respectively

#### Scenario: ordinal handles regular numbers correctly

- **WHEN** `{{ ordinal(1) }}`, `{{ ordinal(2) }}`, `{{ ordinal(3) }}`, `{{ ordinal(21) }}` are rendered
- **THEN** the outputs are `"1st"`, `"2nd"`, `"3rd"`, `"21st"` respectively

#### Scenario: signed uses plus sign for positive

- **WHEN** `{{ signed(5) }}` is rendered
- **THEN** the output is `"+5"`

#### Scenario: signed does not add plus sign to zero

- **WHEN** `{{ signed(0) }}` is rendered
- **THEN** the output is `"0"`

#### Scenario: stat_mod applies D&D formula correctly

- **WHEN** `{{ stat_mod(14) }}` is rendered
- **THEN** the output is `"2"` (floor((14-10)/2))

#### Scenario: stat_mod with below-10 value returns negative modifier

- **WHEN** `{{ stat_mod(8) }}` is rendered
- **THEN** the output is `"-1"` (floor((8-10)/2))
