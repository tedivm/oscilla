## ADDED Requirements

### Requirement: PronounSet defines all grammatical forms for a player

A `PronounSet` dataclass SHALL store the following fields, all lowercase:

- `subject` — nominative pronoun (e.g. `"they"`, `"she"`, `"he"`)
- `object` — objective pronoun (e.g. `"them"`, `"her"`, `"him"`)
- `possessive` — attributive possessive (e.g. `"their"`, `"her"`, `"his"`)
- `possessive_standalone` — nominal possessive (e.g. `"theirs"`, `"hers"`, `"his"`)
- `reflexive` — reflexive pronoun (e.g. `"themselves"`, `"herself"`, `"himself"`)
- `uses_plural_verbs` (bool) — `True` for the they/them set; `False` for she/her and he/him

Three built-in sets SHALL be predefined: `they_them`, `she_her`, `he_him`.

#### Scenario: Built-in sets are accessible

- **WHEN** code accesses `PRONOUN_SETS["they_them"]`
- **THEN** subject is `"they"`, object is `"them"`, possessive is `"their"`, uses_plural_verbs is `True`

#### Scenario: Built-in she/her set has singular verb flag

- **WHEN** code accesses `PRONOUN_SETS["she_her"]`
- **THEN** subject is `"she"`, uses_plural_verbs is `False`

---

### Requirement: CharacterState stores the player's chosen PronounSet

`CharacterState` SHALL have a `pronouns: PronounSet` field that defaults to `they_them`. The chosen set SHALL be serialised to persistent storage as a string key (e.g. `"she_her"`). On deserialisation, an unrecognised key SHALL fall back to `they_them` and log a warning.

#### Scenario: New character gets they/them by default

- **WHEN** a new character is created via `new_character()`
- **THEN** `character.pronouns` is the `they_them` built-in set

#### Scenario: Pronoun set round-trips through serialization

- **WHEN** `CharacterState.to_dict()` is called on a character with `she_her` pronouns
- **THEN** the resulting dict has `pronoun_set: "she_her"`
- **AND** `CharacterState.from_dict()` on that dict restores `she_her` pronouns

#### Scenario: Unknown pronoun key falls back to they_them

- **WHEN** `CharacterState.from_dict()` is called with `pronoun_set: "unknown_key"`
- **THEN** the character's `pronouns` is the `they_them` set
- **AND** a warning is logged

---

### Requirement: CharacterConfig may declare additional pronoun sets

`CharacterConfigSpec` SHALL accept an `extra_pronoun_sets` list of `PronounSetDefinition` objects. Each definition SHALL have: `name` (unique key), `display_name` (UI label), and all five pronoun fields plus `uses_plural_verbs`. Definitions in `extra_pronoun_sets` are merged with the built-in sets and are available as valid pronoun set choices.

#### Scenario: Custom pronoun set declared in CharacterConfig is valid

- **WHEN** a `CharacterConfig` declares `extra_pronoun_sets: [{name: xe_xir, display_name: "xe/xir", ...}]`
- **THEN** the content loads without error and `"xe_xir"` is a valid pronoun set key

#### Scenario: Duplicate pronoun set name is a load error

- **WHEN** `CharacterConfig` declares an `extra_pronoun_sets` entry with `name: "she_her"` (conflicts with built-in)
- **THEN** the content loader raises a `ContentLoadError` identifying the conflict

---

### Requirement: Pronoun placeholders are preprocessed into Jinja2 before compilation

Content templates MAY use curly-brace pronoun placeholders that are easier to write than raw Jinja2. Before a template string is compiled, a preprocessing pass SHALL replace:

| Placeholder                | Expands to                       | Notes                                     |
| -------------------------- | -------------------------------- | ----------------------------------------- |
| `{they}`                   | subject, lowercase               |                                           |
| `{them}`                   | object, lowercase                |                                           |
| `{their}`                  | possessive, lowercase            |                                           |
| `{theirs}`                 | possessive_standalone, lowercase |                                           |
| `{themselves}`             | reflexive, lowercase             |                                           |
| `{They}` / `{Them}` / etc. | subject/object/etc., capitalized | First letter upper                        |
| `{THEY}` / `{THEM}` / etc. | subject/object/etc., uppercased  | All caps                                  |
| `{is}`                     | correct verb form                | `"is"` or `"are"` per `uses_plural_verbs` |
| `{are}`                    | same as `{is}`                   | interchangeable                           |
| `{Is}` / `{Are}`           | verb form, capitalized           |                                           |
| `{was}`                    | `"was"` or `"were"`              |                                           |
| `{were}`                   | same as `{was}`                  | interchangeable                           |
| `{has}`                    | `"has"` or `"have"`              |                                           |
| `{have}`                   | same as `{has}`                  | interchangeable                           |

Capitalisation of the placeholder SHALL determine capitalisation of the output: lowercase → lowercase, `TitleCase` → capitalize filter, `UPPER` → upper filter.

Unrecognised `{word}` patterns that are not pronoun or verb forms SHALL be left unchanged (supporting literal brace syntax in other contexts).

#### Scenario: {they} renders correct subject pronoun for she/her player

- **WHEN** a template `"{they} found the treasure."` is rendered for a she/her player
- **THEN** the output is `"she found the treasure."`

#### Scenario: {They} renders capitalized subject pronoun

- **WHEN** a template `"{They} found the treasure."` is rendered for a they/them player
- **THEN** the output is `"They found the treasure."`

#### Scenario: {THEY} renders uppercase subject pronoun

- **WHEN** a template `"Praise {THEY}!"` is rendered for a he/him player
- **THEN** the output is `"Praise HIM!"` (object form, uppercased)

  Note: `{THEY}` resolves to `{subject}`, so output is `"HE"` not `"HIM"`.

#### Scenario: {is} and {are} are interchangeable and produce correct verb agreement

- **WHEN** `"{They} {is} ready."` is rendered for a they/them player
- **THEN** the output is `"They are ready."`
- **WHEN** `"{They} {are} ready."` is rendered for the same player
- **THEN** the output is also `"They are ready."`

#### Scenario: {is} produces singular form for she/her player

- **WHEN** `"{They} {is} ready."` is rendered for a she/her player
- **THEN** the output is `"She is ready."`

#### Scenario: Unrecognised placeholder is left unchanged

- **WHEN** a template string contains `"{json_value}"` where `json_value` is not a pronoun keyword
- **THEN** the preprocessing pass leaves the string unchanged
