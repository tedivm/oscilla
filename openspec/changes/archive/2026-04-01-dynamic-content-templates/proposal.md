## Why

The manifest system is entirely static: narrative text is fixed, effect amounts are hardcoded, and enemy stats never vary. This blocks a wide class of content — personalized storytelling, scaling rewards, dynamic combat, gender-inclusive pronouns, and any game mechanic that depends on player state. A dynamic template system is the prerequisite for expressive, immersive content authoring.

## What Changes

- Introduce a Jinja2-based template engine (`SandboxedEnvironment`) that is applied at runtime to any string field in a manifest that contains `{{`, `{%`, or pronoun placeholder syntax.
- Define a read-only `ExpressionContext` passed to every template render: `player` (name, level, title, stats, milestones, inventory, pronoun set), `combat` (active combat state — only available in combat contexts), and `adventure` (current adventure metadata).
- Add a set of built-in safe functions available in every template: `roll(low, high)`, `choice(items)`, `max()`, `min()`, `floor()`, `ceil()`, `abs()`.
- Add a set of built-in Jinja2 filters: `damage_text`, `stat_modifier`, `pluralize`, `title_case`, and others as documented.
- Introduce pronoun placeholder syntax (`{they}`, `{Their}`, `{THEM}`, `{is}`, `{are}`, `{was}`, `{were}`, `{has}`, `{have}`, `{themselves}`, `{theirs}`) that is preprocessed into correct Jinja2 before rendering. Capitalization of the placeholder (`lowercase`, `Titlecase`, `UPPERCASE`) controls the capitalization of the output.
- All template strings are **precompiled at content load time**. Any invalid syntax, undefined variable access, or type violation is a hard content load error — the same class of error as a missing stat reference.
- Extend `oscilla validate` to exercise every template in a game package against a comprehensive mock context derived from `CharacterConfig` and the content registry. All possible runtime errors must be catchable at validation time.
- Extend `CharacterConfig` with optional `pronoun_sets` configuration and a default pronoun set. Games that do not define pronoun sets fall back to a neutral they/them default.
- Extend `CharacterState` with a `pronouns: PronounSet` field that is set during character creation and persisted.
- Templates are strictly read-only with respect to game state — they produce a rendered string or a scalar value; they never mutate player state.
- All existing static manifest content continues to work unchanged. Template syntax is opt-in per field.

## Capabilities

### New Capabilities

- `dynamic-content-templates`: Core Jinja2 sandbox engine, `ExpressionContext` object, precompilation pipeline, built-in functions (`roll`, `choice`, math), built-in filters, and load-time validation against a comprehensive mock context.
- `pronoun-system`: `PronounSet` dataclass, predefined sets (she/her, he/him, they/them and extensible), pronoun placeholder preprocessing (`{they}`, `{Their}`, `{THEM}`, verb agreement `{is}`/`{are}` etc.), `CharacterConfig` pronoun set definitions, `CharacterState.pronouns` field, and character creation pronoun selection adventure step.

### Modified Capabilities

- `manifest-system`: Template strings are valid field values in all string-typed manifest fields; the loader precompiles them and validates them against a mock context. New load-time error class for template failures.
- `adventure-pipeline`: Effect amounts (`stat_change.amount`, `xp_grant.amount`, `item_drop.count`) and narrative text fields accept template strings. `ExpressionContext` is constructed and passed to the template engine at step execution time.
- `stat-mutation-effects`: `stat_change.amount` and `stat_set.value` may be template strings that resolve to the appropriate type at runtime. Load-time validation must confirm the resolved type matches the target stat type.
- `testlandia`: Add a pronoun selection adventure, narrative adventures using `{{ player.name }}` and `{they}/{their}` pronouns, an adventure with `roll()`-based variable rewards, and an enemy with templated HP and attack values to exercise all major template features for manual QA.

## Impact

- **New module**: `oscilla/engine/templates.py` — `GameTemplateEngine`, `ExpressionContext`, `PronounSet`, pronoun preprocessor, built-in function/filter registry, mock context builder.
- **Character model**: `oscilla/engine/character.py` gains `pronouns: PronounSet`; persistence updated.
- **Character config model**: `oscilla/engine/models/character_config.py` gains `pronoun_sets: List[PronounSetDefinition]`.
- **Adventure models**: `oscilla/engine/models/adventure.py` — `StatChangeEffect.amount`, `XpGrantEffect.amount`, `ItemDropEffect.count` widen from `int` to `int | str` (string = template); `StatSetEffect.value` widens to include `str`.
- **Effect dispatcher**: `oscilla/engine/steps/effects.py` evaluates template strings before applying effects; receives `ExpressionContext`.
- **Pipeline**: `oscilla/engine/pipeline.py` constructs `ExpressionContext` and passes it to step handlers and the template engine.
- **Loader**: `oscilla/engine/loader.py` precompiles and validates all template strings during content load; new `TemplateValidationError`.
- **Validate CLI command**: `oscilla/cli.py` (or dedicated validate command) exercises all templates against mock context.
- **New dependency**: `jinja2` (already likely transitive; becomes a direct declared dependency).
- **Database**: New `pronouns` column on characters table; new migration required.
- **Content**: `content/testlandia/` gains pronoun, template narrative, variable reward, and templated enemy content.
