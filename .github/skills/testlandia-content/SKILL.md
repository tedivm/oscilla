---
name: testlandia-content
description: "Add or modify content for the Testlandia development and QA environment. Use when: developing test content, creating manifests for engine feature validation, adding test adventures/items/enemies, testing game mechanics, QA validation scenarios, debugging content issues. FOR HUMAN MANUAL TESTING ONLY - automated unit/integration testing is out of scope. Includes built-in validation, content structure guidance, and test-friendly naming conventions. SELF-UPDATING: Always validates against current system and updates itself when outdated."
---

# Testlandia Content Development

> **🔄 SELF-UPDATING SKILL 🔄**
> This skill may become outdated as the system evolves. It always checks current system documentation and code before proceeding, and updates itself when discrepancies are found. System knowledge takes priority over this skill's static knowledge.

> **🚨 HUMAN MANUAL QA ONLY 🚨**
> Testlandia is strictly for human manual quality assurance and engine testing. **DO NOT** create narrative content, stories, creative writing, or attempt to be "cute" with content. This is a technical testing environment for manual validation, not automated unit/integration testing. Unit tests belong in the `tests/` directory, not Testlandia.

A comprehensive workflow for adding and managing content in the Testlandia development and QA environment. This skill ensures proper content structure, validation, and testing practices.

## Overview

**CRITICAL: Testlandia is a manual QA/testing platform for human testers ONLY. Do not create narrative content, stories, quests, or any "cute" creative writing. Focus purely on functional testing that requires human interaction and validation.**

**Scope Boundaries:**

- ✅ **Manual testing content**: Adventures, items, enemies for human testers to interact with
- ✅ **Engine feature validation**: Content that exercises specific game engine features
- ✅ **QA scenario creation**: Test cases that require human judgment and interaction
- ❌ **Unit testing**: Belongs in `tests/` directory, not Testlandia
- ❌ **Integration testing**: Automated testing is handled separately
- ❌ **Creative content**: No storytelling or narrative development

Testlandia is a developer sandbox environment designed for manually exercising engine features **by human testers**. It provides a structured environment for manual testing of:

- Adventure mechanics and step types
- Combat system features
- Item and equipment systems
- Character progression and stats
- Condition evaluation logic
- Game engine edge cases
- Any other features that developers may think of

**Human Testing Focus**: All content is designed for interactive human validation, not automated testing pipelines.

**Content Guidelines:**

- Use technical, descriptive language only
- Name everything with test-purpose prefixes (`test-`, `debug-`, `qa-`)
- Focus on engine feature validation requiring human interaction
- Do not engage in creative narrative, character development, or world-building
- Content must be manually testable by human QA testers
- **Not for automated testing** - unit/integration tests belong in `tests/` directory

## Pre-Flight Check

**CRITICAL: This skill may be outdated. Always verify against current system before proceeding.**

**This skill location: `.github/skills/testlandia-content/SKILL.md`** - Update this file when system discrepancies found.

Before adding content, verify the environment and validate skill knowledge:

1. **Check current system documentation**
2. **Verify skill knowledge against actual system**
3. **Check current location and directory structure**
4. **Validate existing content is working**
5. **Review Testlandia's current content organization**
6. **Update this skill if discrepancies found**

Run these commands to gather context:

```bash
pwd
ls -la content/testlandia/
uv run oscilla validate --game testlandia

# Check for current documentation
ls docs/authors/
ls docs/dev/

# Examine actual manifest structures in use
find content/testlandia -name '*.yaml' -type f | head -5 | xargs cat
```

## Content Categories

Testlandia organizes content by functional area in the `content/testlandia/regions/` directory:

| Category                 | Purpose                                                                      | Location                       |
| ------------------------ | ---------------------------------------------------------------------------- | ------------------------------ |
| **adventure-mechanics/** | Passive steps, repeat controls, custom outcomes, adventure pipeline features | `regions/adventure-mechanics/` |
| **character/**           | Character progression, leveling, stats testing, prestige system              | `regions/character/`           |
| **choices/**             | Decision trees, condition-based branching, narrative flow                    | `regions/choices/`             |
| **combat/**              | Battle mechanics, enemy AI, skill/buff systems                               | `regions/combat/`              |
| **conditions/**          | Logic evaluation, milestone tracking, stat checks                            | `regions/conditions/`          |
| **items/**               | Equipment, inventory, consumables, crafting materials                        | `regions/items/`               |
| **quests/**              | Quest activation, stage progression, failure states, quest_stage conditions  | `regions/quests/`              |
| **skills/**              | Skill system, buffs, combat abilities, cooldowns                             | `regions/skills/`              |
| **template-system/**     | Jinja templates, pronoun system, variable text                               | `regions/template-system/`     |

## Creating New Regions

**When to Create a New Region:**

Create a new region when testing functionality that differs significantly from existing categories:

- ✅ **New engine feature**: Testing functionality not covered by existing regions
- ✅ **Distinct test domain**: Feature requires isolated testing environment
- ✅ **Complex feature testing**: Multiple related test scenarios that form a cohesive testing domain
- ❌ **Single test case**: Use existing regions for isolated tests
- ❌ **Minor variations**: Extend existing regions rather than creating new ones

**New Region Creation Process:**

1. **Create directory structure**:

   ```
   content/testlandia/regions/[new-region-name]/
   ├── [region-name].yaml          # Region manifest (required)
   ├── locations/                  # Adventure locations (optional)
   ├── items/                      # Items specific to this region (optional)
   ├── enemies/                    # Enemies specific to this region (optional)
   └── [other-content-types]/      # Other content as needed (optional)
   ```

2. **Create Region manifest** (`[region-name].yaml`):

   ```yaml
   apiVersion: game/v1
   kind: Region
   metadata:
     name: [region-name] # Must match directory name
   spec:
     displayName: "Test: [Region Purpose]"
     description: "QA testing region for [specific functionality]. Validates [engine features]."
   ```

3. **Apply naming conventions**:
   - Use lowercase with hyphens (`feature-testing`, `new-mechanic-qa`)
   - Include test purpose prefix when appropriate (`test-`, `qa-`, `debug-`)
   - Avoid generic names (`misc`, `other`, `random`)
   - **NEVER** use creative names (`wonderland`, `mystery-realm`)

4. **Validate new region**: Follow Step 6 validation process below

**Examples of Valid New Regions:**

- `recipe-crafting/` - For testing crafting system mechanics
- `quest-tracking/` - For testing quest progression and milestone systems
- `persistence-validation/` - For testing save/load functionality

## Content Development Process

### Step 1: Verify System Knowledge & Determine Content Category

**First, validate this skill's knowledge against the current system:**

1. Check current documentation: `docs/authors/content-authoring.md`
2. Review actual manifest schemas in `oscilla/engine/models/`
3. Examine existing Testlandia content for current patterns
4. **If discrepancies found, update this skill immediately** at `.github/skills/testlandia-content/SKILL.md`

Then determine content requirements from context:

- **Primary function**: Identify engine feature being tested from proposal/environment
- **Content type**: Infer manifest type needed (Adventure, Item, Enemy, Quest, etc.)
- **Test scenario**: Extract specific behavior validation requirements
- **Expected outcome**: Determine what should happen when content executes

**Core Technical Focus**: Testlandia is for QA testing only - create functional validation content, not narrative.

### Step 2: Choose Proper Location

Based on the content category, determine the correct subdirectory structure:

**For Adventures:**

```
content/testlandia/regions/{category}/locations/{location-name}/
├── {location-name}.yaml          # LocationManifest
└── adventures/
    └── {adventure-name}.yaml     # AdventureManifest
```

**For Items:**

```
content/testlandia/regions/{category}/items/
└── {item-name}.yaml              # ItemManifest
```

**For Enemies:**

```
content/testlandia/regions/{category}/enemies/
└── {enemy-name}.yaml             # EnemyManifest
```

### Step 3: Apply Test-Friendly Naming

Use descriptive names that indicate the test purpose:

**Good Examples:**

- `test-basic-sword` (simple weapon testing)
- `stat-mutation-adventure` (tests stat modification)
- `level-down-scenario` (tests negative XP mechanics)
- `debug-condition-evaluation` (tests nested logic evaluation)
- `qa-combat-round-validation` (validates combat mechanics)

**Naming Rules:**

- Use lowercase with hyphens (`test-item-name`)
- **ALWAYS** include test purpose prefix (`test-`, `debug-`, `qa-`, `validate-`)
- Match filename to `metadata.name` field
- Avoid generic names (`item1`, `adventure`, `test`)
- **NEVER** use creative or story-based names (`excalibur`, `dragon-quest`, `magic-forest`)

### Step 4: Create Manifest with Proper Structure

All manifests follow the envelope format:

```yaml
apiVersion: game/v1
kind: [ManifestType]
metadata:
  name: descriptive-test-name
spec:
  displayName: "Test: [Feature Name]"
  description: "QA test for [specific engine feature]. Expected behavior: [technical description]."
  # ... kind-specific fields
```

**Content Writing Guidelines:**

- Use technical language only (`"QA test for stat mutation"`, not `"A magical journey"`)
- Start descriptions with `"QA test for..."` or `"Validation test for..."`
- Explain expected technical behavior, not story elements
- Display names should start with `"Test:"` or `"Debug:"` prefixes

### Step 5: Implement Content Logic

**For Adventures**, include comprehensive test coverage:

```yaml
spec:
  steps:
    - type: narrative
      text: "QA TEST: [feature name]. This test validates [specific engine behavior]. Expected result: [technical outcome]."

    # Include test steps that exercise the target feature.
    # Available step types: narrative, choice, combat, stat_check, passive
    # Use 'passive' for automatic effect application (no player input):
    - type: passive
      effects:
        - type: xp_grant
          amount: 50

    # End the adventure via an effect on a narrative step, or a choice option:
    - type: narrative
      text: "Test complete."
      choices:
        - label: "Finish."
          effects:
            - type: end_adventure
              outcome: completed # Options: "completed", "defeated", "fled", or any custom outcome declared in game.yaml
```

**Text Content Rules:**

- Start all narrative text with `"QA TEST:"` or `"DEBUG:"`
- Use clinical, technical language only
- Explain what is being tested and expected outcomes
- **NO creative writing, storytelling, or character interactions**

**For Items**, specify test-relevant properties:

```yaml
spec:
  displayName: "Test: Basic Consumable"
  description: "QA test for item functionality and inventory management validation."
  item_type: consumable
  max_stack_size: 10
  effects:
    - type: heal
      amount: 25
```

**For Enemies**, include combat testing scenarios:

```yaml
spec:
  displayName: "Test: Combat Dummy"
  description: "QA test enemy for combat mechanics validation. Predictable stats for consistent testing."
  max_hp: 50
  attack_damage: 10
  xp_reward: 25
```

### Step 6: Run Validation

**Always validate before completing**:

```bash
# Validate specific game content
uv run oscilla validate --game testlandia

# If validation passes, run quick manual test
uv run oscilla game --game testlandia
```

## Quality Assurance Checklist

Before marking content complete, verify:

- [ ] **System knowledge current**: Checked docs/authors/ and oscilla/engine/models/ for latest schemas
- [ ] **Skill accuracy verified**: Confirmed this skill's templates match current system requirements
- [ ] **Updated skill if needed**: Modified this skill file if discrepancies were found
- [ ] **Validation passes**: No errors from `uv run oscilla validate --game testlandia`
- [ ] **Proper structure**: Content follows envelope format with correct `apiVersion`, `kind`, `metadata`
- [ ] **Clear purpose**: Description explains what feature is being tested
- [ ] **Test coverage**: Content exercises the intended engine functionality
- [ ] **No broken references**: All referenced items, enemies, adventures exist
- [ ] **Appropriate location**: Content is in the correct category subdirectory
- [ ] **Manual verification**: Content can be accessed and functions as expected in-game

## Troubleshooting

**Common Issues:**

1. **Validation errors**: Check YAML syntax, required fields, and reference names
2. **Content not appearing**: Verify file location and naming match directory structure
3. **Reference errors**: Ensure all referenced content exists and names match exactly
4. **Type mismatches**: Check stat types in character_config.yaml match usage

**Debug Commands:**

```bash
# Detailed validation output
uv run oscilla validate --game testlandia -v

# Check game structure
ls -R content/testlandia/regions/

# Verify content loading
uv run oscilla game --game testlandia --character-name test-char

# Validate skill knowledge against system
grep -r "apiVersion\|kind:" content/testlandia/ | head -10
ls oscilla/engine/models/
cat docs/authors/content-authoring.md | head -100
```

## Content Templates

**⚠️ WARNING: These templates may be outdated. Always verify against current system first.**

To validate template accuracy, check:

1. `oscilla/engine/models/` for current Pydantic schemas
2. `docs/authors/content-authoring.md` for latest manifest documentation
3. Working examples in `content/testlandia/` for current patterns

If templates below don't match the system, **update this skill immediately**.

### Basic Adventure Template

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: test-[feature-name]
spec:
  displayName: "Test: [Feature Name]"
  description: "QA validation for [specific engine feature]. Expected behavior: [technical description]."
  steps:
    - type: narrative
      text: "QA TEST: [Feature Name]. This test validates [engine behavior]. Expected outcome: [result]."

    - type: narrative
      text: "Test complete."
      effects:
        - type: end_adventure
          outcome: completed
```

### Passive Step Template

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: test-[feature-name]
spec:
  displayName: "Test: [Feature Name]"
  description: "QA validation for passive step behavior."
  steps:
    # Passive step fires its effects automatically with no player input.
    - type: passive
      text: "QA TEST: Effect applies automatically."
      effects:
        - type: stat_change
          stat: hp
          amount: -10
      # Optional: skip effects when bypass condition is met
      bypass:
        type: character_stat
        name: dexterity
        gte: 12
      bypass_text: "Your reflexes save you."

    - type: narrative
      text: "Done."
```

### One-Shot / Repeat Controls Template

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: test-one-shot
spec:
  displayName: "Test: One-Shot"
  description: "QA test for repeatable: false — disappears after first completion."
  repeatable: false # mutually exclusive with max_completions
  # max_completions: 3   # hard cap per iteration (alternative to repeatable: false)
  # cooldown_days: 1      # calendar-day cooldown
  # cooldown_adventures: 3  # cooldown measured in total adventures completed
  steps:
    - type: narrative
      text: "QA TEST: This adventure is one-shot."
      choices:
        - label: "Complete it."
          effects:
            - type: end_adventure
              outcome: completed
```

### Basic Item Template

```yaml
apiVersion: game/v1
kind: Item
metadata:
  name: test-[item-purpose]
spec:
  displayName: "Test: [Item Purpose]"
  description: "QA test item for [specific functionality] validation."
  item_type: [consumable|equipment|material]
  max_stack_size: 1
```

### Basic Enemy Template

```yaml
apiVersion: game/v1
kind: Enemy
metadata:
  name: test-[enemy-type]
spec:
  displayName: "Test: [Enemy Type]"
  description: "QA combat opponent for [specific mechanics] validation."
  max_hp: 30
  attack_damage: 5
  xp_reward: 15
```

## Advanced Features

### Stat Mutation Testing

For testing stat modification effects:

```yaml
# In adventure steps
- type: passive
  effects:
    - type: stat_change
      stat: "strength" # Must exist in character_config.yaml
      amount: 2

    - type: stat_set
      stat: "is_blessed"
      value: true

    - type: heal
      amount: 15 # or amount: "full" to restore to max_hp
```

### Condition Testing

For testing complex condition evaluation:

```yaml
# In adventure steps
- type: stat_check
  condition:
    type: all
    conditions:
      - type: level
        operator: gte
        value: 3
      - type: milestone
        name: "test-milestone-unlocked"
  on_pass:
    steps:
      - type: narrative
        text: "QA RESULT: Condition evaluation passed. Test successful."
  on_fail:
    steps:
      - type: narrative
        text: "QA RESULT: Condition evaluation failed. Test outcome as expected."
```

### Quest Stage Condition Testing

For testing quest-gated content with `quest_stage` conditions:

```yaml
# requires field on a location pool entry
requires:
  type: quest_stage
  quest: test-some-quest
  stage: searching
```

### Quest Failure Testing

For testing quest failure via `fail_condition` or the `quest_fail` effect:

```yaml
# In an adventure that forces a quest to fail
- type: passive
  effects:
    - type: quest_fail
      quest_ref: test-some-quest
```

## Integration Points

This skill integrates with:

- **Content validation**: Built-in validation commands
- **Game engine testing**: Direct integration with Testlandia environment
- **Development workflow**: Follows established content authoring patterns
- **QA processes**: Provides structured testing scenarios

Always run validation after changes and test manually in the game environment to ensure content functions correctly.

## Self-Update Protocol

**This skill file location: `.github/skills/testlandia-content/SKILL.md`**

**This skill must stay current with the evolving system. When discrepancies are found:**

1. **Immediately update this skill file** with correct information
2. **Update templates** to match current manifest schemas
3. **Correct field names, types, and structure** based on actual system
4. **Verify changes** by testing with actual content
5. **Document the update** in a brief comment at the top of the skill

**Self-Update Commands:**

```bash
# Edit this skill file directly
code .github/skills/testlandia-content/SKILL.md

# Or use replace_string_in_file tool with:
# filePath: /path/to/workspace/.github/skills/testlandia-content/SKILL.md
```

**Priority Order for Knowledge Sources:**

1. Current system code (`oscilla/engine/models/`)
2. Current documentation (`docs/authors/`, `docs/dev/`)
3. Working Testlandia content examples
4. This skill's built-in knowledge (lowest priority)

**Never assume this skill is correct if it conflicts with the actual system.**
