## ADDED Requirements

> **Note on timezone**: When `game.yaml` declares a `timezone` (IANA name), all calendar predicates listed below SHALL derive the current date and time from that timezone. When `timezone` is absent or `None`, all predicates use server local time. See the `timezone` requirement at the end of this file.

### Requirement: `season_is` condition predicate

The `season_is` predicate SHALL accept one of `"spring"`, `"summer"`, `"autumn"`, or `"winter"` and evaluate to true when the current real-world meteorological season matches the given value. The season SHALL be determined by the `season()` function in `calendar_utils`. When a `ContentRegistry` is provided and its game manifest declares `season_hemisphere`, that hemisphere SHALL be used; otherwise the evaluator SHALL default to `"northern"`.

#### Scenario: season_is true in matching season

- **WHEN** a `season_is: summer` condition is evaluated on a date in July (Northern Hemisphere)
- **THEN** it evaluates to true

#### Scenario: season_is false in non-matching season

- **WHEN** a `season_is: winter` condition is evaluated on a date in July (Northern Hemisphere)
- **THEN** it evaluates to false

#### Scenario: season_is uses southern hemisphere when configured

- **WHEN** a `season_is: winter` condition is evaluated on a date in July with a registry where `season_hemisphere: southern`
- **THEN** it evaluates to true (July is winter in the Southern Hemisphere)

#### Scenario: season_is defaults to northern when registry is absent

- **WHEN** a `season_is: summer` condition is evaluated on a date in July without a registry
- **THEN** it evaluates to true (defaults to northern hemisphere)

---

### Requirement: `moon_phase_is` condition predicate

The `moon_phase_is` predicate SHALL accept one of the eight lunar phase names (`"New Moon"`, `"Waxing Crescent"`, `"First Quarter"`, `"Waxing Gibbous"`, `"Full Moon"`, `"Waning Gibbous"`, `"Last Quarter"`, `"Waning Crescent"`) and evaluate to true when the approximate current lunar phase matches. The current date SHALL be resolved in the game's configured timezone (or server local time if absent).

#### Scenario: moon_phase_is true on matching phase

- **WHEN** a `moon_phase_is: "Full Moon"` condition is evaluated on a date that `moon_phase()` returns `"Full Moon"` for
- **THEN** it evaluates to true

#### Scenario: moon_phase_is false on non-matching phase

- **WHEN** a `moon_phase_is: "New Moon"` condition is evaluated on a date where the current phase is `"Full Moon"`
- **THEN** it evaluates to false

---

### Requirement: `zodiac_is` condition predicate

The `zodiac_is` predicate SHALL accept one of the twelve Western zodiac sign names and evaluate to true when `zodiac_sign(today())` matches the given value. The current date SHALL be resolved in the game's configured timezone (or server local time if absent).

#### Scenario: zodiac_is true on matching sign

- **WHEN** a `zodiac_is: "Aries"` condition is evaluated on April 5
- **THEN** it evaluates to true (April 5 falls in Aries)

#### Scenario: zodiac_is false on non-matching sign

- **WHEN** a `zodiac_is: "Scorpio"` condition is evaluated on April 5
- **THEN** it evaluates to false

---

### Requirement: `chinese_zodiac_is` condition predicate

The `chinese_zodiac_is` predicate SHALL accept one of the twelve Chinese zodiac animal names and evaluate to true when `chinese_zodiac(today().year)` matches. The current year SHALL be resolved in the game's configured timezone (or server local time if absent).

#### Scenario: chinese_zodiac_is true on matching animal

- **WHEN** a `chinese_zodiac_is: "Horse"` condition is evaluated in a Horse year
- **THEN** it evaluates to true

#### Scenario: chinese_zodiac_is false on non-matching animal

- **WHEN** a `chinese_zodiac_is: "Dragon"` condition is evaluated in a Horse year
- **THEN** it evaluates to false

---

### Requirement: `month_is` condition predicate

The `month_is` predicate SHALL evaluate to true when the current month (resolved in the game's configured timezone, or server local time if absent) matches the configured value. The value SHALL accept either an integer (1–12) or a full English month name (case-insensitive). String values SHALL be normalised to integer at parse time; invalid names SHALL raise a validation error.

#### Scenario: month_is true with integer

- **WHEN** a `month_is: 10` condition is evaluated in October
- **THEN** it evaluates to true

#### Scenario: month_is true with string name

- **WHEN** a `month_is: "October"` condition is evaluated in October
- **THEN** it evaluates to true

#### Scenario: month_is false in wrong month

- **WHEN** a `month_is: 12` condition is evaluated in October
- **THEN** it evaluates to false

#### Scenario: invalid string month name fails at parse time

- **WHEN** a manifest declares `month_is: "Octobr"` (misspelled)
- **THEN** content load raises a `ContentLoadError` before the registry is returned

---

### Requirement: `day_of_week_is` condition predicate

The `day_of_week_is` predicate SHALL evaluate to true when the current day of the week (resolved in the game's configured timezone, or server local time if absent) matches. The value SHALL accept either an integer (0 = Monday … 6 = Sunday) or a full English weekday name (case-insensitive). String values SHALL be normalised to integer at parse time; invalid names SHALL raise a validation error.

#### Scenario: day_of_week_is true with integer

- **WHEN** a `day_of_week_is: 0` condition is evaluated on a Monday
- **THEN** it evaluates to true

#### Scenario: day_of_week_is true with string name

- **WHEN** a `day_of_week_is: "Monday"` condition is evaluated on a Monday
- **THEN** it evaluates to true

#### Scenario: day_of_week_is false on wrong day

- **WHEN** a `day_of_week_is: "Saturday"` condition is evaluated on a Monday
- **THEN** it evaluates to false

---

### Requirement: `date_is` condition predicate

The `date_is` predicate SHALL evaluate to true when today's date (resolved in the game's configured timezone, or server local time if absent) matches the configured month and day. An optional `year` field, when set, restricts the match to that specific calendar year; when omitted, the predicate matches annually. The `month` field SHALL accept an integer or a full English month name (same normalisation as `month_is`).

#### Scenario: date_is true on matching annual date

- **WHEN** a `date_is: {month: 12, day: 25}` condition is evaluated on December 25 of any year
- **THEN** it evaluates to true

#### Scenario: date_is false on non-matching day

- **WHEN** a `date_is: {month: 12, day: 25}` condition is evaluated on December 26
- **THEN** it evaluates to false

#### Scenario: date_is with year true only in that year

- **WHEN** a `date_is: {month: 12, day: 25, year: 2026}` condition is evaluated on December 25, 2026
- **THEN** it evaluates to true

#### Scenario: date_is with year false in a different year

- **WHEN** a `date_is: {month: 12, day: 25, year: 2026}` condition is evaluated on December 25, 2027
- **THEN** it evaluates to false

---

### Requirement: `time_between` condition predicate

The `time_between` predicate SHALL evaluate to true when the current time (in the game's configured IANA timezone when set, or server local time when no timezone is configured) falls within the configured window. Both `start` and `end` SHALL be strings in 24-hour `HH:MM` format (e.g. `"22:00"`, `"09:30"`). AM/PM notation is explicitly not supported; values that do not match `HH:MM` SHALL be rejected with a validation error at content load time. When `start < end` the window is same-day; when `start > end` the window wraps midnight. When `start == end` the predicate SHALL always evaluate to false and log a warning.

#### Scenario: time_between true inside same-day window

- **WHEN** a `time_between: {start: "09:00", end: "17:00"}` condition is evaluated at 14:30
- **THEN** it evaluates to true

#### Scenario: time_between false outside same-day window

- **WHEN** a `time_between: {start: "09:00", end: "17:00"}` condition is evaluated at 20:00
- **THEN** it evaluates to false

#### Scenario: time_between true in midnight-wrapping window

- **WHEN** a `time_between: {start: "22:00", end: "04:00"}` condition is evaluated at 23:30
- **THEN** it evaluates to true (23:30 >= 22:00)

#### Scenario: time_between true just after midnight in wrapping window

- **WHEN** a `time_between: {start: "22:00", end: "04:00"}` condition is evaluated at 02:00
- **THEN** it evaluates to true (02:00 <= 04:00)

#### Scenario: time_between false outside midnight-wrapping window

- **WHEN** a `time_between: {start: "22:00", end: "04:00"}` condition is evaluated at 12:00
- **THEN** it evaluates to false

#### Scenario: time_between zero-duration window always false

- **WHEN** a `time_between: {start: "12:00", end: "12:00"}` condition is evaluated at any time
- **THEN** it evaluates to false

#### Scenario: time_between rejects AM/PM notation at load time

- **WHEN** a manifest declares `time_between: {start: "9:00 AM", end: "5:00 PM"}`
- **THEN** content load raises a `ContentLoadError` before the registry is returned

#### Scenario: time_between rejects malformed time strings at load time

- **WHEN** a manifest declares `time_between: {start: "9:00", end: "17:00"}` (single-digit hour, no leading zero)
- **THEN** content load raises a `ContentLoadError` before the registry is returned

#### Scenario: time_between uses game-configured timezone

- **WHEN** `game.yaml` declares `timezone: "America/New_York"` and `time_between: {start: "09:00", end: "17:00"}` is evaluated when New York time is 14:00
- **THEN** it evaluates to true regardless of the server's local timezone

---

### Requirement: Calendar predicates compose with `all`, `any`, `not`

All calendar predicates SHALL work as leaf nodes under existing branch nodes (`all`, `any`, `not`), enabling multi-condition expressions such as "October full moon" or "weekend night".

#### Scenario: all composition with two calendar predicates

- **WHEN** an `all` condition contains `month_is: 10` and `moon_phase_is: "Full Moon"` and both are true on the evaluated date
- **THEN** the `all` node evaluates to true

#### Scenario: not wraps a calendar predicate

- **WHEN** a `not` condition wraps `season_is: winter` and the current season is summer
- **THEN** the `not` node evaluates to true

---

### Requirement: `season_hemisphere` field on `GameSpec`

The `GameSpec` model SHALL include an optional `season_hemisphere` field accepting `"northern"` (default) or `"southern"`. This field SHALL control the hemisphere used by the `season_is` condition predicate when a `ContentRegistry` is available. Games that omit this field SHALL behave identically to games that explicitly set it to `"northern"`.

#### Scenario: game.yaml with southern hemisphere affects season_is

- **WHEN** `game.yaml` declares `season_hemisphere: southern` and a `season_is: winter` condition is evaluated in July
- **THEN** the condition evaluates to true

#### Scenario: game.yaml without season_hemisphere defaults to northern

- **WHEN** `game.yaml` does not declare `season_hemisphere` and a `season_is: summer` condition is evaluated in July
- **THEN** the condition evaluates to true

---

### Requirement: `timezone` field on `GameSpec`

The `GameSpec` model SHALL include an optional `timezone` field accepting an IANA timezone name string (e.g. `"America/New_York"`, `"Europe/London"`). When set, **all calendar condition predicates** SHALL derive the current date and time from `datetime.datetime.now(tz=zoneinfo.ZoneInfo(timezone))`. When absent or `None`, server local time SHALL be used. An unrecognised IANA key SHALL cause a `logger.warning` and fall back to server local time without raising an error.

#### Scenario: timezone causes season rollover at audience midnight

- **WHEN** `game.yaml` declares `timezone: "Asia/Tokyo"` and it is 00:30 JST on December 1 (but still November 30 in server local time) and a `month_is: 12` condition is evaluated
- **THEN** it evaluates to true (the game's audience is in December)

#### Scenario: game.yaml with timezone affects time_between

- **WHEN** `game.yaml` declares `timezone: "America/New_York"` and a `time_between: {start: "09:00", end: "17:00"}` condition is evaluated when New York time is 14:00
- **THEN** the condition evaluates to true regardless of the server's local timezone

#### Scenario: game.yaml without timezone falls back to server local time

- **WHEN** `game.yaml` does not declare `timezone` and a `time_between` condition is evaluated
- **THEN** the condition evaluates based on server local time

#### Scenario: game.yaml with unrecognised timezone falls back gracefully

- **WHEN** `game.yaml` declares `timezone: "Mars/Olympus_Mons"` (not a valid IANA key)
- **THEN** a warning is logged and the condition evaluates using server local time
