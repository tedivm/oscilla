"""Update all callers of the old load() function to use load_from_disk()."""

import pathlib
import re

files = [
    "tests/test_cli_content.py",
    "tests/fixtures/content/trigger_tests/__init__.py",
    "tests/engine/conftest.py",
    "tests/engine/test_loader.py",
    "tests/engine/test_derived_stats.py",
    "tests/engine/test_adventure_outcomes.py",
    "tests/engine/test_pronoun_system.py",
    "tests/engine/test_adventure_ticks.py",
    "tests/engine/test_quest_stage_condition.py",
    "tests/engine/test_loot_ref.py",
    "tests/engine/test_derived_stat_validation.py",
    "tests/engine/test_item_enhancements.py",
    "tests/engine/test_character_persistence.py",
    "tests/engine/test_template_integration.py",
    "tests/engine/test_combat_skills.py",
    "tests/engine/test_stat_effects.py",
    "tests/engine/test_skill_integration.py",
    "tests/services/test_character_service.py",
    "oscilla/cli_content.py",
    "oscilla/cli.py",
]

for fpath in files:
    p = pathlib.Path(fpath)
    text = p.read_text()

    # Replace standalone 'load' in import list (not followed by underscore)
    new_text = re.sub(r"(?<=import )load(?=[,\s\n]|$)", "load_from_disk", text)
    new_text = re.sub(r"(?<=, )load(?=[,\s\n]|$)", "load_from_disk", new_text)

    # Replace actual load( calls (standalone, not load_from_disk or load_games or load_all)
    new_text = re.sub(r"\bload\(", "load_from_disk(", new_text)

    # Fix any double-replacements
    new_text = new_text.replace("load_from_disk_from_disk", "load_from_disk")
    new_text = new_text.replace("load_from_diskgames", "load_games")
    new_text = new_text.replace("load_from_disk_games", "load_games")
    new_text = new_text.replace("load_from_disk_all", "load_all")

    if new_text != text:
        p.write_text(new_text)
        print(f"Updated: {fpath}")
    else:
        print(f"No change: {fpath}")
