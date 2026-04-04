# Templates

Narrative text in Oscilla is more than static strings. Any `text` field in an [adventure step](./adventures.md), and some numeric fields like XP amounts and stat change values, can contain **[Jinja2](https://jinja.palletsprojects.com/en/stable/templates/) template expressions** that are evaluated at runtime. This lets you write adventures that reference the player's name, react to their stats, vary by season, and use proper pronouns automatically.

Templates are opt-in. A plain string with no `{{` or `{%` passes through unchanged. You can add as much or as little dynamic content as your adventure calls for.

> **For developers:** Oscilla runs templates in [Jinja2's sandbox mode](https://jinja.palletsprojects.com/en/stable/sandbox/). This prevents templates from accessing private attributes (anything prefixed with `_`), calling unsafe methods, or reaching outside the provided context objects. If you're used to writing Jinja2 in a web framework, the syntax is identical — but arbitrary Python builtins and internal object attributes are blocked. Everything documented on this page works as-is; the sandbox only restricts things that aren't part of the authoring API.

---

## The Player Context

Inside a template, the `player` object gives you access to everything about the character right now.

```yaml
text: |
  Welcome back, {{ player.name }}!
  You are level {{ player.level }} with {{ player.hp }}/{{ player.max_hp }} HP.
```

| Expression | Type | Description |
|---|---|---|
| `{{ player.name }}` | str | Character name |
| `{{ player.level }}` | int | Current level |
| `{{ player.hp }}` | int | Current hit points |
| `{{ player.max_hp }}` | int | Maximum hit points |
| `{{ player.stats.<name> }}` | int/bool | Any stat defined in `CharacterConfig` |
| `{{ player.milestones.has("name") }}` | bool | True if player holds that milestone |

### Accessing Stats

Refer to any stat by name exactly as defined in [`character_config.yaml`](./game-configuration.md#stats):

```yaml
text: |
  You have {{ player.stats.gold }} gold pieces in your pouch.
  Your strength is {{ player.stats.strength }}.
```

### Milestone Checks in Text

Use `player.milestones.has()` in a conditional to change text based on story progress:

```yaml
text: |
  {% if player.milestones.has('hero-of-the-realm') %}
  The crowd parts for you. Word travels fast.
  {% else %}
  You slip through the market unnoticed.
  {% endif %}
```

---

## Random and Calculated Values

### Rolling Dice

The `roll(low, high)` function returns a random integer between `low` and `high` inclusive. Use it in `text` for flavor, or in numeric effect fields for dynamic rewards.

```yaml
# In narrative text
text: "You find {{ roll(10, 50) }} gold coins scattered on the floor."

# In an XP grant — dynamic reward
effects:
  - type: xp_grant
    amount: "{{ roll(50, 150) }}"

# In a stat_change
effects:
  - type: stat_change
    stat: gold
    amount: "{{ roll(5, 20) }}"
```

### Using Player Stats in Calculations

Effect amounts can reference player stats:

```yaml
effects:
  - type: stat_change
    stat: gold
    amount: "{{ player.stats.luck * 5 }}"
```

### Other Randomness Functions

```yaml
# Pick one randomly from a list
text: "The merchant offers you a {{ choice(['sword', 'shield', 'amulet']) }}."

# Float [0.0, 1.0)
text: "Your accuracy is {{ (random() * 100) | round }}%."
```

---

## Math and Utility Functions

| Function | Description | Example |
|---|---|---|
| `roll(low, high)` | Random integer inclusive | `{{ roll(1, 20) }}` |
| `choice(seq)` | Pick one at random | `{{ choice(["fire","ice","wind"]) }}` |
| `random()` | Float in [0.0, 1.0) | `{{ random() }}` |
| `sample(seq, n)` | Pick n without repeats | `{{ sample(items, 2) }}` |
| `clamp(val, lo, hi)` | Clamp to range [lo, hi] | `{{ clamp(player.stats.strength, 0, 20) }}` |
| `min(a, b)` | Minimum of two values | `{{ min(10, player.stats.speed) }}` |
| `max(a, b)` | Maximum of two values | `{{ max(0, player.stats.gold) }}` |
| `round(n)` | Round to nearest integer | `{{ round(x) }}` |
| `floor(n)` | Round down | `{{ floor(x) }}` |
| `ceil(n)` | Round up | `{{ ceil(x) }}` |
| `abs(n)` | Absolute value | `{{ abs(player.stats.debt) }}` |
| `int(x)` | Convert to integer | `{{ int(x) }}` |
| `str(x)` | Convert to string | `{{ str(player.level) }}` |
| `len(seq)` | Length of a sequence | `{{ len(items) }}` |
| `range(n)` | Integer range for loops | `{% for i in range(3) %}` |
| `sum(seq)` | Sum a sequence | `{{ sum(values) }}` |

---

## Calendar and Astronomical Functions

These functions take a `datetime.date` object from `today()` and compute calendar information. Use them for seasonal narrative variation, holiday events, or atmospheric flavor.

```yaml
text: |
  The {{ season(today()) }} air bites with cold as you approach the gate.
  Tonight is a {{ moon_phase(today()) }}.
```

| Function | Returns | Example output |
|---|---|---|
| `now()` | Current UTC datetime | `now().year` → `2026` |
| `today()` | Current UTC date | Use as argument to functions below |
| `season(date)` | `"spring"`, `"summer"`, `"autumn"`, or `"winter"` | `"winter"` |
| `month_name(date)` | Full month name | `"December"` |
| `day_name(date)` | Day of week | `"Friday"` |
| `week_number(date)` | ISO week number 1–53 | `51` |
| `zodiac_sign(date)` | Western zodiac sign | `"Sagittarius"` |
| `chinese_zodiac(date)` | Chinese zodiac animal | `"Horse"` |
| `moon_phase(date)` | Moon phase description | `"Waxing Gibbous"` |
| `mean(values)` | Arithmetic mean | `{{ mean([10, 20, 30]) }}` → `20.0` |

---

## Filters

[Jinja2 filters](https://jinja.palletsprojects.com/en/stable/templates/#filters) transform values. Apply them with the pipe `|` character. Oscilla adds a few custom filters on top of the standard set; all available filters are listed below.

```yaml
text: "{{ player.name | upper }} enters the tavern."
text: "You found {{ count }} {{ count | pluralize('wolf', 'wolves') }}."
text: "Strength modifier: {{ player.stats.strength | stat_modifier }}"
```

| Filter | Description | Example |
|---|---|---|
| `stat_modifier` | Format as `+n` or `-n` | `12 \| stat_modifier` → `+2` (relative to 10) |
| `pluralize(singular, plural)` | `singular` if value is 1, else `plural` | `1 \| pluralize("wolf","wolves")` → `"wolf"` |
| `upper` | Uppercase | `"hero" \| upper` → `"HERO"` |
| `lower` | Lowercase | `"HERO" \| lower` → `"hero"` |
| `capitalize` | First letter uppercase | `"they" \| capitalize` → `"They"` |

---

## Pronouns

Oscilla automatically adapts narrative text to match each player's chosen pronouns. There are two ways to use pronouns in text: **placeholder shorthand** (recommended for most cases) and **Jinja2 expressions** (for more control). To add custom pronoun options beyond the built-in three, see [Game Configuration §Custom Pronoun Sets](./game-configuration.md#custom-pronoun-sets).

### Pronoun Placeholder Shorthand

Write `{they}`, `{them}`, `{their}`, and verb placeholders directly in text. No Jinja2 syntax needed — just curly braces without double brackets.

The capitalization of the placeholder controls the capitalization of the output.

```yaml
text: "{They} {are} a formidable warrior, and {their} reputation precedes {them}."
# they/them → "They are a formidable warrior, and their reputation precedes them."
# she/her   → "She is a formidable warrior, and her reputation precedes her."
# he/him    → "He is a formidable warrior, and his reputation precedes him."
```

Both `{is}` and `{are}` expand identically — write whichever reads most naturally:

```yaml
text: "{They} {were} the last one standing."
# they/them → "They were the last one standing."
# she/her   → "She was the last one standing."
# he/him    → "He was the last one standing."
```

### Jinja2 Pronoun Expressions

When you need the full pronoun object — for grammatically complex constructions, or to access `possessive_standalone` and `reflexive` — use the `player.pronouns` object:

```yaml
text: "{{ player.name }} looks at {{ player.pronouns.reflexive }} in the mirror."
# they/them → "Hero looks at themselves in the mirror."
# she/her   → "Hero looks at herself in the mirror."
```

---

## Conditional Text

Use Jinja2 [`{% if %}`](https://jinja.palletsprojects.com/en/stable/templates/#if) blocks to switch between entire passages based on any condition. Unlike [adventure step conditions](./conditions.md) (which filter whole adventures or options), template conditionals apply within a single text field.

```yaml
text: |
  You enter the forge.
  {% if player.stats.strength >= 15 %}
  The blacksmith eyes your arms approvingly. "Strong hands. You'll do fine here."
  {% else %}
  The blacksmith sizes you up skeptically. "Can you even lift a hammer?"
  {% endif %}
```

```yaml
text: |
  {% if player.milestones.has('slew-the-dragon') %}
  Songs are already being written about your deed.
  {% elif player.level >= 10 %}
  People watch you with cautious respect.
  {% else %}
  You pass unnoticed through the crowd.
  {% endif %}
```

---

## Where Templates Can Be Used

Templates are supported in these fields:

| Field | Example |
|---|---|
| Narrative step `text` | `"Hello, {{ player.name }}!"` |
| `xp_grant.amount` | `"{{ roll(50, 150) }}"` |
| `stat_change.amount` | `"{{ player.stats.luck * 2 }}"` |
| `item_drop.count` | `"{{ roll(1, 3) }}"` |

Fields that don't support templates will treat the string literally.

---

## Validation

Run `oscilla validate` to catch template errors before playing:

```bash
uv run oscilla validate
```

Template syntax errors and unknown context references are reported with the file name and field where the error occurred. All template expressions are validated at load time, so while it is impossible to detect all potential errors a good number should be caught by this command.

---

## Reference

### Player Context Object

| Expression | Type | Description |
|---|---|---|
| `player.name` | str | Character name |
| `player.level` | int | Current level |
| `player.hp` | int | Current hit points |
| `player.max_hp` | int | Maximum hit points |
| `player.stats.<name>` | int/bool | Any declared stat by name |
| `player.milestones.has("<name>")` | bool | True if player holds the milestone |
| `player.pronouns.subject` | str | Subject pronoun (they/she/he) |
| `player.pronouns.object` | str | Object pronoun (them/her/him) |
| `player.pronouns.possessive` | str | Possessive adjective (their/her/his) |
| `player.pronouns.possessive_standalone` | str | Standalone possessive (theirs/hers/his) |
| `player.pronouns.reflexive` | str | Reflexive (themselves/herself/himself) |
| `player.pronouns.uses_plural_verbs` | bool | True for they/them pronoun sets |

### Pronoun Placeholder Reference

| Placeholder | Expands to | they/them | she/her | he/him |
|---|---|---|---|---|
| `{they}` | subject | they | she | he |
| `{They}` | subject, capitalized | They | She | He |
| `{THEY}` | subject, uppercase | THEY | SHE | HE |
| `{them}` | object | them | her | him |
| `{their}` | possessive adjective | their | her | his |
| `{is}` / `{are}` | linking verb | are | is | is |
| `{was}` / `{were}` | past linking verb | were | was | was |
| `{has}` / `{have}` | auxiliary verb | have | has | has |

---

*See [Game Configuration](./game-configuration.md#custom-pronoun-sets) for defining custom pronoun sets in `CharacterConfig`.*
*See the [Jinja2 Template Designer Documentation](https://jinja.palletsprojects.com/en/stable/templates/) for the full Jinja2 syntax reference.*
