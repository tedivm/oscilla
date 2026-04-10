"""Content loader — scans, parses, validates, and builds the ContentRegistry."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Set, Tuple, cast

if TYPE_CHECKING:
    from oscilla.engine.models.time import GameTimeSpec
    from oscilla.engine.templates import GameTemplateEngine

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from oscilla.engine.models import MANIFEST_REGISTRY
from oscilla.engine.models.adventure import (
    _BUILTIN_OUTCOMES,
    AdventureManifest,
    ApplyBuffEffect,
    ArchetypeAddEffect,
    ArchetypeRemoveEffect,
    ChoiceStep,
    CombatStep,
    Effect,
    EmitTriggerEffect,
    EndAdventureEffect,
    ItemDropEffect,
    NarrativeStep,
    OutcomeBranch,
    PassiveStep,
    PrestigeEffect,
    SkillGrantEffect,
    StatChangeEffect,
    StatCheckStep,
    StatSetEffect,
    Step,
    UseItemEffect,
)
from oscilla.engine.models.archetype import ArchetypeManifest
from oscilla.engine.models.base import (
    AllCondition,
    AnyCondition,
    ArchetypeTicksElapsedCondition,
    Condition,
    HasAllArchetypesCondition,
    HasAnyArchetypeCondition,
    HasArchetypeCondition,
    ManifestEnvelope,
    NotCondition,
    QuestStageCondition,
)
from oscilla.engine.models.buff import BuffManifest
from oscilla.engine.models.character_config import CharacterConfigManifest
from oscilla.engine.models.game import GameManifest
from oscilla.engine.models.item import ItemManifest
from oscilla.engine.models.location import LocationManifest
from oscilla.engine.models.quest import QuestManifest
from oscilla.engine.models.recipe import RecipeManifest
from oscilla.engine.models.region import RegionManifest
from oscilla.engine.models.skill import SkillManifest
from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)
_yaml = YAML(typ="safe")


@dataclass
class LoadError:
    file: Path
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.message}"


@dataclass
class LoadWarning:
    """Non-fatal content issue surfaced by `oscilla validate`.

    Warnings indicate a likely authoring mistake that does not prevent the
    game from running (e.g. a label typo). The `suggestion` field provides a
    human-readable fix hint for both authors and AI tooling.
    """

    file: Path
    message: str
    suggestion: str = ""

    def __str__(self) -> str:
        base = f"{self.file}: {self.message}"
        return f"{base} — {self.suggestion}" if self.suggestion else base


class ContentLoadError(Exception):
    def __init__(self, errors: List[LoadError]) -> None:
        self.errors = errors
        lines = "\n".join(f"  {e}" for e in errors)
        super().__init__(f"{len(errors)} content error(s):\n{lines}")


def scan(content_dir: Path) -> List[Path]:
    """Return all .yaml / .yml files found recursively under content_dir, sorted."""
    return sorted(p for p in content_dir.rglob("*") if p.suffix in {".yaml", ".yml"})


def parse(paths: List[Path]) -> Tuple[List[ManifestEnvelope], List[LoadError]]:
    """Parse YAML files and validate against Pydantic models. Accumulates errors.

    Each path may contain multiple YAML documents separated by '---' dividers.
    Every document is validated independently. Errors include a document index
    suffix (e.g. '[doc 2]') for files with more than one document.
    """
    manifests: List[ManifestEnvelope] = []
    errors: List[LoadError] = []

    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(LoadError(file=path, message=f"File read error: {exc}"))
            continue

        try:
            # Wrap in list() to eagerly evaluate so parse errors are caught here.
            docs = list(_yaml.load_all(text))
        except YAMLError as exc:
            errors.append(LoadError(file=path, message=f"YAML parse error: {exc}"))
            continue

        for doc_index, raw in enumerate(docs):
            # Suffix added only when there is more than one document to keep
            # single-document error messages identical to the existing format.
            label = f"{path} [doc {doc_index + 1}]" if len(docs) > 1 else str(path)

            if not isinstance(raw, dict):
                errors.append(LoadError(file=path, message=f"{label}: Manifest must be a YAML mapping"))
                continue

            kind = raw.get("kind", "<missing>")
            model_cls = MANIFEST_REGISTRY.get(str(kind))
            if model_cls is None:
                errors.append(LoadError(file=path, message=f"{label}: Unknown kind: {kind!r}"))
                continue

            try:
                manifests.append(model_cls.model_validate(raw))
            except ValidationError as exc:
                for err in exc.errors():
                    loc = " → ".join(str(x) for x in err["loc"])
                    errors.append(LoadError(file=path, message=f"{label}: {loc}: {err['msg']}"))

    return manifests, errors


def _collect_step_enemy_refs(step: Step, refs: Set[str]) -> None:
    """Collect enemy refs from a step tree."""
    match step:
        case CombatStep(enemy=enemy):
            refs.add(enemy)
            for branch in [step.on_win, step.on_defeat, step.on_flee]:
                for sub in branch.steps:
                    _collect_step_enemy_refs(sub, refs)
        case ChoiceStep():
            for opt in step.options:
                for sub in opt.steps:
                    _collect_step_enemy_refs(sub, refs)
        case StatCheckStep():
            for branch in [step.on_pass, step.on_fail]:
                for sub in branch.steps:
                    _collect_step_enemy_refs(sub, refs)
        case _:
            pass


def _collect_goto_refs(branch: OutcomeBranch, gotos: Set[str]) -> None:
    if branch.goto:
        gotos.add(branch.goto)
    for sub in branch.steps:
        _collect_step_goto_refs(sub, gotos)


def _collect_step_goto_refs(step: Step, gotos: Set[str]) -> None:
    match step:
        case CombatStep():
            for branch in [step.on_win, step.on_defeat, step.on_flee]:
                _collect_goto_refs(branch, gotos)
        case ChoiceStep():
            for opt in step.options:
                if opt.goto:
                    gotos.add(opt.goto)
                for sub in opt.steps:
                    _collect_step_goto_refs(sub, gotos)
        case StatCheckStep():
            for branch in [step.on_pass, step.on_fail]:
                _collect_goto_refs(branch, gotos)
        case _:
            pass


def _collect_stat_effect_refs(effects: List[Effect], stat_refs: Set[str]) -> None:
    """Collect stat references from StatChangeEffect and StatSetEffect."""
    from oscilla.engine.models.adventure import StatChangeEffect, StatSetEffect

    for effect in effects:
        if isinstance(effect, (StatChangeEffect, StatSetEffect)):
            stat_refs.add(effect.stat)


def _collect_use_item_refs(effects: List[Effect], item_refs: Set[str]) -> None:
    """Collect item references from UseItemEffect."""
    for effect in effects:
        if isinstance(effect, UseItemEffect):
            item_refs.add(effect.item)


def _collect_branch_use_item_refs(branch: OutcomeBranch, item_refs: Set[str]) -> None:
    """Collect use_item refs from effects and sub-steps in an OutcomeBranch."""
    _collect_use_item_refs(branch.effects, item_refs)
    for sub in branch.steps:
        _collect_step_use_item_refs(sub, item_refs)


def _collect_step_use_item_refs(step: Step, item_refs: Set[str]) -> None:
    """Collect use_item refs from all effects in a Step."""
    match step:
        case NarrativeStep():
            _collect_use_item_refs(step.effects, item_refs)
        case CombatStep():
            for branch in [step.on_win, step.on_defeat, step.on_flee]:
                _collect_branch_use_item_refs(branch, item_refs)
        case ChoiceStep():
            for opt in step.options:
                _collect_use_item_refs(opt.effects, item_refs)
                for sub in opt.steps:
                    _collect_step_use_item_refs(sub, item_refs)
        case StatCheckStep():
            for branch in [step.on_pass, step.on_fail]:
                _collect_branch_use_item_refs(branch, item_refs)
        case _:
            pass


def _collect_branch_stat_refs(branch: OutcomeBranch, stat_refs: Set[str]) -> None:
    """Collect stat references from effects and sub-steps in an OutcomeBranch."""
    _collect_stat_effect_refs(branch.effects, stat_refs)
    for sub in branch.steps:
        _collect_step_stat_refs(sub, stat_refs)


def _collect_step_stat_refs(step: Step, stat_refs: Set[str]) -> None:
    """Collect stat references from all effects in a Step."""
    match step:
        case NarrativeStep():
            _collect_stat_effect_refs(step.effects, stat_refs)
        case CombatStep():
            for branch in [step.on_win, step.on_defeat, step.on_flee]:
                _collect_branch_stat_refs(branch, stat_refs)
        case ChoiceStep():
            for opt in step.options:
                _collect_stat_effect_refs(opt.effects, stat_refs)
                for sub in opt.steps:
                    _collect_step_stat_refs(sub, stat_refs)
        case StatCheckStep():
            for branch in [step.on_pass, step.on_fail]:
                _collect_branch_stat_refs(branch, stat_refs)
        case _:
            pass


def _collect_apply_buff_effects(effects: List[Effect], refs: List[ApplyBuffEffect]) -> None:
    """Collect all ApplyBuffEffect instances from an effect list."""
    for eff in effects:
        if isinstance(eff, ApplyBuffEffect):
            refs.append(eff)


def _collect_end_adventure_effects(effects: List[Effect], results: List[EndAdventureEffect]) -> None:
    """Collect all EndAdventureEffect instances from an effect list."""
    for eff in effects:
        if isinstance(eff, EndAdventureEffect):
            results.append(eff)


def _collect_branch_end_adventure(branch: OutcomeBranch, results: List[EndAdventureEffect]) -> None:
    _collect_end_adventure_effects(branch.effects, results)
    for sub in branch.steps:
        _collect_step_end_adventure(sub, results)


def _collect_step_end_adventure(step: Step, results: List[EndAdventureEffect]) -> None:
    match step:
        case NarrativeStep():
            _collect_end_adventure_effects(step.effects, results)
        case CombatStep():
            for branch in [step.on_win, step.on_defeat, step.on_flee]:
                _collect_branch_end_adventure(branch, results)
        case ChoiceStep():
            for opt in step.options:
                _collect_end_adventure_effects(opt.effects, results)
                for sub in opt.steps:
                    _collect_step_end_adventure(sub, results)
        case StatCheckStep():
            for branch in [step.on_pass, step.on_fail]:
                _collect_branch_end_adventure(branch, results)
        case _:
            pass


def _collect_prestige_effects(effects: List[Effect], results: List[PrestigeEffect]) -> None:
    """Collect all PrestigeEffect instances from an effect list."""
    for eff in effects:
        if isinstance(eff, PrestigeEffect):
            results.append(eff)


def _collect_step_prestige_effects(step: Step, results: List[PrestigeEffect]) -> None:
    match step:
        case NarrativeStep():
            _collect_prestige_effects(step.effects, results)
        case CombatStep():
            for branch in [step.on_win, step.on_defeat, step.on_flee]:
                _collect_prestige_effects(branch.effects, results)
                for sub in branch.steps:
                    _collect_step_prestige_effects(sub, results)
        case ChoiceStep():
            for opt in step.options:
                _collect_prestige_effects(opt.effects, results)
                for sub in opt.steps:
                    _collect_step_prestige_effects(sub, results)
        case StatCheckStep():
            for branch in [step.on_pass, step.on_fail]:
                _collect_prestige_effects(branch.effects, results)
                for sub in branch.steps:
                    _collect_step_prestige_effects(sub, results)
        case _:
            pass


def _validate_prestige_effects(manifests: List[ManifestEnvelope]) -> List[LoadError]:
    """Validate that PrestigeEffect is only used when the game.yaml has a prestige block."""
    errors: List[LoadError] = []
    game_manifests = [m for m in manifests if m.kind == "Game"]
    if not game_manifests:
        return errors
    game = cast(GameManifest, game_manifests[0])
    prestige_configured = game.spec.prestige is not None

    for m in manifests:
        if m.kind != "Adventure":
            continue
        adv = cast(AdventureManifest, m)
        found: List[PrestigeEffect] = []
        for step in adv.spec.steps:
            _collect_step_prestige_effects(step, found)
        if found and not prestige_configured:
            errors.append(
                LoadError(
                    file=Path(f"<{m.metadata.name}>"),
                    message="Adventure uses prestige effect but game.yaml has no prestige: block configured.",
                )
            )

    return errors


def _validate_outcome_refs(manifests: List[ManifestEnvelope]) -> List[LoadError]:
    """Validate that custom EndAdventureEffect outcome names are declared in game.yaml."""
    errors: List[LoadError] = []
    game_manifests = [m for m in manifests if m.kind == "Game"]
    if not game_manifests:
        return errors  # No game manifest to validate against; other validators will catch this.
    game = cast(GameManifest, game_manifests[0])
    declared_outcomes: Set[str] = set(game.spec.outcomes)

    for m in manifests:
        if m.kind != "Adventure":
            continue
        adv = cast(AdventureManifest, m)
        end_effects: List[EndAdventureEffect] = []
        for step in adv.spec.steps:
            _collect_step_end_adventure(step, end_effects)
        for eff in end_effects:
            if eff.outcome not in _BUILTIN_OUTCOMES and eff.outcome not in declared_outcomes:
                errors.append(
                    LoadError(
                        file=Path(f"<{m.metadata.name}>"),
                        message=(
                            f"end_adventure outcome {eff.outcome!r} is not a built-in outcome and is not declared "
                            f"in game.yaml outcomes list. Built-ins: {sorted(_BUILTIN_OUTCOMES)}"
                        ),
                    )
                )

    return errors


def _collect_skill_grant_effects(effects: List[Effect], refs: Set[str]) -> None:
    """Collect skill_grant effect skill name refs from an effect list."""
    for eff in effects:
        if isinstance(eff, SkillGrantEffect):
            refs.add(eff.skill)


def _collect_branch_skill_refs(
    branch: OutcomeBranch, skill_refs: Set[str], buff_effects: List[ApplyBuffEffect]
) -> None:
    _collect_skill_grant_effects(branch.effects, skill_refs)
    _collect_apply_buff_effects(branch.effects, buff_effects)
    for sub in branch.steps:
        _collect_step_skill_and_buff_refs(sub, skill_refs, buff_effects)


def _collect_step_skill_and_buff_refs(step: Step, skill_refs: Set[str], buff_effects: List[ApplyBuffEffect]) -> None:
    match step:
        case NarrativeStep():
            _collect_skill_grant_effects(step.effects, skill_refs)
            _collect_apply_buff_effects(step.effects, buff_effects)
        case CombatStep():
            for branch in [step.on_win, step.on_defeat, step.on_flee]:
                _collect_branch_skill_refs(branch, skill_refs, buff_effects)
        case ChoiceStep():
            for opt in step.options:
                _collect_skill_grant_effects(opt.effects, skill_refs)
                _collect_apply_buff_effects(opt.effects, buff_effects)
                for sub in opt.steps:
                    _collect_step_skill_and_buff_refs(sub, skill_refs, buff_effects)
        case StatCheckStep():
            for branch in [step.on_pass, step.on_fail]:
                _collect_branch_skill_refs(branch, skill_refs, buff_effects)
        case _:
            pass


def _validate_skill_refs(manifests: List[ManifestEnvelope]) -> List[LoadError]:
    """Validate that skill_ref fields in items, enemies, and effects point to known Skill manifests."""
    errors: List[LoadError] = []
    skill_names: Set[str] = {m.metadata.name for m in manifests if m.kind == "Skill"}

    for m in manifests:
        if m.kind == "Item":
            item = cast(ItemManifest, m)
            for skill_ref in item.spec.grants_skills_equipped + item.spec.grants_skills_held:
                if skill_ref not in skill_names:
                    errors.append(
                        LoadError(
                            file=Path(f"<{m.metadata.name}>"),
                            message=f"grants_skills_* references unknown skill: {skill_ref!r}",
                        )
                    )

        elif m.kind == "Enemy":
            from oscilla.engine.models.enemy import EnemyManifest

            enemy = cast(EnemyManifest, m)
            for entry in enemy.spec.skills:
                if entry.skill_ref not in skill_names:
                    errors.append(
                        LoadError(
                            file=Path(f"<{m.metadata.name}>"),
                            message=f"enemy skill entry references unknown skill: {entry.skill_ref!r}",
                        )
                    )

        elif m.kind == "Adventure":
            adv = cast(AdventureManifest, m)
            skill_grant_refs: Set[str] = set()
            buff_effects_adv: List[ApplyBuffEffect] = []
            for step in adv.spec.steps:
                _collect_step_skill_and_buff_refs(step, skill_grant_refs, buff_effects_adv)
            for ref in skill_grant_refs:
                if ref not in skill_names:
                    errors.append(
                        LoadError(
                            file=Path(f"<{m.metadata.name}>"),
                            message=f"skill_grant effect references unknown skill: {ref!r}",
                        )
                    )

        elif m.kind == "Skill":
            skill = cast(SkillManifest, m)
            skill_grant_refs_s: Set[str] = set()
            buff_effects_s: List[ApplyBuffEffect] = []
            for eff in skill.spec.use_effects:
                _collect_skill_grant_effects([eff], skill_grant_refs_s)
                _collect_apply_buff_effects([eff], buff_effects_s)
            for ref in skill_grant_refs_s:
                if ref not in skill_names:
                    errors.append(
                        LoadError(
                            file=Path(f"<{m.metadata.name}>"),
                            message=f"skill_grant in use_effects references unknown skill: {ref!r}",
                        )
                    )

    return errors


def _validate_buff_refs(manifests: List[ManifestEnvelope]) -> List[LoadError]:
    """Validate that buff_ref fields and variable override keys are consistent."""
    errors: List[LoadError] = []
    buff_names: Set[str] = {m.metadata.name for m in manifests if m.kind == "Buff"}

    # Build a map of buff name → declared variables for variable override key checks.
    buff_variables: Dict[str, Set[str]] = {}
    for m in manifests:
        if m.kind == "Buff":
            buff_m = cast(BuffManifest, m)
            buff_variables[m.metadata.name] = set(buff_m.spec.variables.keys())

    def _check_apply_buff(manifest_name: str, eff: ApplyBuffEffect) -> List[LoadError]:
        errs: List[LoadError] = []
        if eff.buff_ref not in buff_names:
            errs.append(
                LoadError(
                    file=Path(f"<{manifest_name}>"),
                    message=f"apply_buff references unknown buff: {eff.buff_ref!r}",
                )
            )
        elif eff.variables:
            # Validate variable override keys are declared in the buff spec.
            declared = buff_variables.get(eff.buff_ref, set())
            for key in eff.variables:
                if key not in declared:
                    errs.append(
                        LoadError(
                            file=Path(f"<{manifest_name}>"),
                            message=f"apply_buff {eff.buff_ref!r} variable override key {key!r} not declared in buff variables",
                        )
                    )
        return errs

    for m in manifests:
        if m.kind == "Item":
            item = cast(ItemManifest, m)
            for grant in item.spec.grants_buffs_equipped + item.spec.grants_buffs_held:
                if grant.buff_ref not in buff_names:
                    errors.append(
                        LoadError(
                            file=Path(f"<{m.metadata.name}>"),
                            message=f"grants_buffs_* references unknown buff: {grant.buff_ref!r}",
                        )
                    )
                elif grant.variables:
                    declared = buff_variables.get(grant.buff_ref, set())
                    for key in grant.variables:
                        if key not in declared:
                            errors.append(
                                LoadError(
                                    file=Path(f"<{m.metadata.name}>"),
                                    message=f"grants_buffs_* {grant.buff_ref!r} variable override key {key!r} not declared in buff variables",
                                )
                            )

        elif m.kind == "Skill":
            skill = cast(SkillManifest, m)
            for eff in skill.spec.use_effects:
                if isinstance(eff, ApplyBuffEffect):
                    errors.extend(_check_apply_buff(m.metadata.name, eff))

        elif m.kind == "Adventure":
            adv = cast(AdventureManifest, m)
            _: Set[str] = set()
            buff_effects_adv: List[ApplyBuffEffect] = []
            for step in adv.spec.steps:
                _collect_step_skill_and_buff_refs(step, _, buff_effects_adv)
            for eff in buff_effects_adv:
                errors.extend(_check_apply_buff(m.metadata.name, eff))

    return errors


def _collect_quest_stage_conditions_in_condition(condition: Condition) -> List[QuestStageCondition]:
    """Recursively collect all QuestStageCondition instances from a condition tree."""
    results: List[QuestStageCondition] = []
    match condition:
        case QuestStageCondition():
            results.append(condition)
        case AllCondition(conditions=children):
            for child in children:
                results.extend(_collect_quest_stage_conditions_in_condition(child))
        case AnyCondition(conditions=children):
            for child in children:
                results.extend(_collect_quest_stage_conditions_in_condition(child))
        case NotCondition(condition=child):
            results.extend(_collect_quest_stage_conditions_in_condition(child))
        case _:
            pass
    return results


def _collect_quest_stage_conditions_from_manifest(m: ManifestEnvelope) -> List[QuestStageCondition]:
    """Collect all QuestStageCondition instances from any manifest."""
    results: List[QuestStageCondition] = []

    def _add(cond: Condition | None) -> None:
        if cond is not None:
            results.extend(_collect_quest_stage_conditions_in_condition(cond))

    match m.kind:
        case "Location":
            loc = cast(LocationManifest, m)
            _add(loc.spec.unlock)
            _add(loc.spec.effective_unlock)
            for adv_entry in loc.spec.adventures:
                _add(adv_entry.requires)
        case "Region":
            region = cast(RegionManifest, m)
            _add(region.spec.unlock)
            _add(region.spec.effective_unlock)
        case "Adventure":
            adv = cast(AdventureManifest, m)
            _add(adv.spec.requires)
            for step in adv.spec.steps:
                match step:
                    case ChoiceStep():
                        for opt in step.options:
                            _add(opt.requires)
                    case PassiveStep():
                        _add(step.bypass)
        case "Game":
            game = cast(GameManifest, m)
            for pe in game.spec.passive_effects:
                _add(pe.condition)

    return results


def _collect_archetype_refs_in_condition(condition: Condition | None) -> Set[str]:
    """Recursively collect archetype name refs from a condition tree."""
    if condition is None:
        return set()
    refs: Set[str] = set()
    match condition:
        case HasArchetypeCondition(name=n):
            refs.add(n)
        case HasAllArchetypesCondition(names=ns):
            refs.update(ns)
        case HasAnyArchetypeCondition(names=ns):
            refs.update(ns)
        case ArchetypeTicksElapsedCondition(name=n):
            refs.add(n)
        case AllCondition(conditions=children):
            for child in children:
                refs.update(_collect_archetype_refs_in_condition(child))
        case AnyCondition(conditions=children):
            for child in children:
                refs.update(_collect_archetype_refs_in_condition(child))
        case NotCondition(condition=child):
            refs.update(_collect_archetype_refs_in_condition(child))
        case _:
            pass
    return refs


def _collect_archetype_refs_in_effects(effects: List[Effect]) -> Set[str]:
    """Collect archetype name refs from an effect list."""
    refs: Set[str] = set()
    for eff in effects:
        if isinstance(eff, ArchetypeAddEffect) or isinstance(eff, ArchetypeRemoveEffect):
            refs.add(eff.name)
    return refs


def _collect_archetype_refs_from_manifest(manifest: ManifestEnvelope) -> Set[str]:
    """Collect all archetype name refs from any manifest kind.

    Covers: adventure step conditions/effects, region/location unlock conditions,
    skill use_effects, item use_effects and equip requires, archetype
    gain_effects/lose_effects/passive_effects, game passive_effects.
    """
    refs: Set[str] = set()

    def _add_cond(cond: Condition | None) -> None:
        refs.update(_collect_archetype_refs_in_condition(cond))

    def _add_effects(effects: List[Effect]) -> None:
        refs.update(_collect_archetype_refs_in_effects(effects))

    def _add_branch(branch: OutcomeBranch) -> None:
        _add_effects(branch.effects)
        for sub in branch.steps:
            _add_step(sub)

    def _add_step(step: Step) -> None:
        match step:
            case NarrativeStep():
                _add_cond(step.requires)
                _add_effects(step.effects)
            case CombatStep():
                _add_cond(step.requires)
                for branch in [step.on_win, step.on_defeat, step.on_flee]:
                    _add_branch(branch)
            case ChoiceStep():
                _add_cond(step.requires)
                for opt in step.options:
                    _add_cond(opt.requires)
                    _add_effects(opt.effects)
                    for sub in opt.steps:
                        _add_step(sub)
            case StatCheckStep():
                _add_cond(step.condition)
                _add_cond(step.requires)
                for branch in [step.on_pass, step.on_fail]:
                    _add_branch(branch)
            case PassiveStep():
                _add_cond(step.bypass)
                _add_cond(step.requires)
            case _:
                pass

    match manifest.kind:
        case "Adventure":
            adv = cast(AdventureManifest, manifest)
            _add_cond(adv.spec.requires)
            for step in adv.spec.steps:
                _add_step(step)
        case "Region":
            region = cast(RegionManifest, manifest)
            _add_cond(region.spec.unlock)
            _add_cond(region.spec.effective_unlock)
        case "Location":
            loc = cast(LocationManifest, manifest)
            _add_cond(loc.spec.unlock)
            _add_cond(loc.spec.effective_unlock)
            for adv_entry in loc.spec.adventures:
                _add_cond(adv_entry.requires)
        case "Skill":
            skill = cast(SkillManifest, manifest)
            _add_effects(skill.spec.use_effects)
        case "Item":
            item = cast(ItemManifest, manifest)
            _add_effects(item.spec.use_effects)
            if item.spec.equip is not None:
                _add_cond(item.spec.equip.requires)
        case "Archetype":
            archetype = cast(ArchetypeManifest, manifest)
            _add_effects(archetype.spec.gain_effects)
            _add_effects(archetype.spec.lose_effects)
            for pe in archetype.spec.passive_effects:
                _add_cond(pe.condition)
        case "Game":
            game = cast(GameManifest, manifest)
            for pe in game.spec.passive_effects:
                _add_cond(pe.condition)

    return refs


def _validate_archetype_refs(manifests: List[ManifestEnvelope]) -> List[LoadError]:
    """Validate that archetype name refs in conditions and effects point to declared Archetype manifests."""
    errors: List[LoadError] = []
    archetype_names: Set[str] = {m.metadata.name for m in manifests if m.kind == "Archetype"}

    for m in manifests:
        refs = _collect_archetype_refs_from_manifest(m)
        for ref in sorted(refs):
            if ref not in archetype_names:
                errors.append(
                    LoadError(
                        file=Path(f"<{m.metadata.name}>"),
                        message=f"archetype ref {ref!r} not found in declared Archetype manifests",
                    )
                )

    return errors


def _validate_quest_stage_condition_refs(manifests: List[ManifestEnvelope]) -> List[LoadError]:
    """Validate that quest_stage condition quest and stage names exist in declared Quest manifests."""
    errors: List[LoadError] = []

    # Build lookup: quest_name → set of stage names
    quest_stages: Dict[str, Set[str]] = {}
    for m in manifests:
        if m.kind == "Quest":
            quest = cast(QuestManifest, m)
            quest_stages[m.metadata.name] = {s.name for s in quest.spec.stages}

    for m in manifests:
        conditions = _collect_quest_stage_conditions_from_manifest(m)
        for cond in conditions:
            if cond.quest not in quest_stages:
                errors.append(
                    LoadError(
                        file=Path(f"<{m.metadata.name}>"),
                        message=f"quest_stage condition references unknown quest: {cond.quest!r}",
                    )
                )
            elif cond.stage not in quest_stages[cond.quest]:
                errors.append(
                    LoadError(
                        file=Path(f"<{m.metadata.name}>"),
                        message=(
                            f"quest_stage condition references unknown stage {cond.stage!r} for quest {cond.quest!r}"
                        ),
                    )
                )

    return errors


def validate_references(manifests: List[ManifestEnvelope]) -> List[LoadError]:
    """Check all cross-references across manifests. Accumulates all errors."""
    names_by_kind: Dict[str, Set[str]] = defaultdict(set)
    for m in manifests:
        names_by_kind[m.kind].add(m.metadata.name)

    errors: List[LoadError] = []

    # Enforce singleton kinds
    game_count = sum(1 for m in manifests if m.kind == "Game")
    if game_count > 1:
        errors.append(
            LoadError(
                file=Path("<content>"), message=f"Multiple Game manifests found ({game_count}); only one is allowed."
            )
        )
    char_count = sum(1 for m in manifests if m.kind == "CharacterConfig")
    if char_count > 1:
        errors.append(
            LoadError(
                file=Path("<content>"),
                message=f"Multiple CharacterConfig manifests found ({char_count}); only one is allowed.",
            )
        )

    # Collect stat names and slot names for item and adventure validation
    stat_names: Set[str] = set()
    slot_names: Set[str] = set()
    for m in manifests:
        if m.kind == "CharacterConfig":
            cc = cast(CharacterConfigManifest, m)
            for s in cc.spec.public_stats + cc.spec.hidden_stats:
                stat_names.add(s.name)
            for slot in cc.spec.equipment_slots:
                slot_names.add(slot.name)

    for m in manifests:
        match m.kind:
            case "Item":
                item = cast(ItemManifest, m)
                if item.spec.equip is not None:
                    # Validate equip slot names against CharacterConfig equipment_slots
                    for slot_name in item.spec.equip.slots:
                        if slot_names and slot_name not in slot_names:
                            errors.append(
                                LoadError(
                                    file=Path(f"<{m.metadata.name}>"),
                                    message=f"equip slot {slot_name!r} is not defined in CharacterConfig equipment_slots",
                                )
                            )
                    # Validate stat_modifier stat names
                    for modifier in item.spec.equip.stat_modifiers:
                        if stat_names and modifier.stat not in stat_names:
                            errors.append(
                                LoadError(
                                    file=Path(f"<{m.metadata.name}>"),
                                    message=f"equip stat_modifier references unknown stat {modifier.stat!r}",
                                )
                            )

            case "Location":
                loc = cast(LocationManifest, m)
                if loc.spec.region not in names_by_kind["Region"]:
                    errors.append(
                        LoadError(file=Path(f"<{m.metadata.name}>"), message=f"Unknown region: {loc.spec.region!r}")
                    )
                for entry in loc.spec.adventures:
                    if entry.ref not in names_by_kind["Adventure"]:
                        errors.append(
                            LoadError(
                                file=Path(f"<{m.metadata.name}>"), message=f"Unknown adventure in pool: {entry.ref!r}"
                            )
                        )

            case "Adventure":
                adv: AdventureManifest = cast(AdventureManifest, m)
                # Collect enemy references
                enemy_refs: Set[str] = set()
                for step in adv.spec.steps:
                    _collect_step_enemy_refs(step, enemy_refs)
                for ref in enemy_refs:
                    if ref not in names_by_kind["Enemy"]:
                        errors.append(LoadError(file=Path(f"<{m.metadata.name}>"), message=f"Unknown enemy: {ref!r}"))

                # Collect stat effect references and validate them
                stat_refs: Set[str] = set()
                for step in adv.spec.steps:
                    _collect_step_stat_refs(step, stat_refs)
                for ref in stat_refs:
                    if ref not in stat_names:
                        errors.append(
                            LoadError(file=Path(f"<{m.metadata.name}>"), message=f"Unknown stat in effect: {ref!r}")
                        )

                # Validate stat effect types match character config
                from oscilla.engine.models.adventure import StatChangeEffect, StatSetEffect

                char_config = next(
                    (cast(CharacterConfigManifest, m) for m in manifests if m.kind == "CharacterConfig"), None
                )
                if char_config:
                    stat_types = {s.name: s.type for s in char_config.spec.public_stats + char_config.spec.hidden_stats}

                    def validate_stat_effects(effects_list: List[Effect]) -> None:
                        for effect in effects_list:
                            if isinstance(effect, StatChangeEffect):
                                stat_type = stat_types.get(effect.stat)
                                if stat_type == "int":
                                    # amount type is already validated as int by Pydantic; no further check needed
                                    pass
                                elif stat_type == "bool":
                                    errors.append(
                                        LoadError(
                                            file=Path(f"<{m.metadata.name}>"),
                                            message=f"stat_change not valid for bool stat {effect.stat!r}, use stat_set instead",
                                        )
                                    )
                            elif isinstance(effect, StatSetEffect):
                                stat_type = stat_types.get(effect.stat)
                                if stat_type == "int" and not isinstance(effect.value, int):
                                    errors.append(
                                        LoadError(
                                            file=Path(f"<{m.metadata.name}>"),
                                            message=f"stat_set on int stat {effect.stat!r} requires int value, got {type(effect.value).__name__}",
                                        )
                                    )
                                elif stat_type == "bool" and not isinstance(effect.value, bool):
                                    errors.append(
                                        LoadError(
                                            file=Path(f"<{m.metadata.name}>"),
                                            message=f"stat_set on bool stat {effect.stat!r} requires bool value, got {type(effect.value).__name__}",
                                        )
                                    )

                    def validate_step_stat_effects(step: Step) -> None:
                        match step:
                            case NarrativeStep():
                                validate_stat_effects(step.effects)
                            case CombatStep():
                                for branch in [step.on_win, step.on_defeat, step.on_flee]:
                                    validate_stat_effects(branch.effects)
                                    for sub in branch.steps:
                                        validate_step_stat_effects(sub)
                            case ChoiceStep():
                                for opt in step.options:
                                    validate_stat_effects(opt.effects)
                                    for sub in opt.steps:
                                        validate_step_stat_effects(sub)
                            case StatCheckStep():
                                for branch in [step.on_pass, step.on_fail]:
                                    validate_stat_effects(branch.effects)
                                    for sub in branch.steps:
                                        validate_step_stat_effects(sub)
                            case _:
                                pass

                    for step in adv.spec.steps:
                        validate_step_stat_effects(step)

                # Validate goto targets resolve (already checked at model level for top-level labels,
                # but re-verify here for cross-reference completeness)
                label_set: Set[str] = set()
                for step in adv.spec.steps:
                    lbl = step.label
                    if lbl:
                        label_set.add(lbl)
                goto_refs: Set[str] = set()
                for step in adv.spec.steps:
                    _collect_step_goto_refs(step, goto_refs)
                for ref in goto_refs:
                    if ref not in label_set:
                        errors.append(
                            LoadError(file=Path(f"<{m.metadata.name}>"), message=f"Unresolved goto label: {ref!r}")
                        )

                # Validate UseItemEffect.item references exist in Item registry
                use_item_refs: Set[str] = set()
                for step in adv.spec.steps:
                    _collect_step_use_item_refs(step, use_item_refs)
                for ref in use_item_refs:
                    if ref not in names_by_kind["Item"]:
                        errors.append(
                            LoadError(
                                file=Path(f"<{m.metadata.name}>"),
                                message=f"use_item effect references unknown item: {ref!r}",
                            )
                        )

            case "Recipe":
                recipe = cast(RecipeManifest, m)
                for ing in recipe.spec.inputs:
                    if ing.item not in names_by_kind["Item"]:
                        errors.append(
                            LoadError(
                                file=Path(f"<{m.metadata.name}>"), message=f"Unknown recipe input item: {ing.item!r}"
                            )
                        )
                if recipe.spec.output.item not in names_by_kind["Item"]:
                    errors.append(
                        LoadError(
                            file=Path(f"<{m.metadata.name}>"),
                            message=f"Unknown recipe output item: {recipe.spec.output.item!r}",
                        )
                    )

            case "Region":
                region = cast(RegionManifest, m)
                if region.spec.parent is not None and region.spec.parent not in names_by_kind["Region"]:
                    errors.append(
                        LoadError(
                            file=Path(f"<{m.metadata.name}>"), message=f"Unknown parent region: {region.spec.parent!r}"
                        )
                    )

            case "CharacterConfig":
                cc_m = cast(CharacterConfigManifest, m)
                # Validate skill_resource binding stat references.
                for binding in cc_m.spec.skill_resources:
                    if binding.stat not in stat_names:
                        errors.append(
                            LoadError(
                                file=Path(f"<{m.metadata.name}>"),
                                message=f"skill_resources binding references unknown stat: {binding.stat!r}",
                            )
                        )
                    if binding.max_stat not in stat_names:
                        errors.append(
                            LoadError(
                                file=Path(f"<{m.metadata.name}>"),
                                message=f"skill_resources binding max_stat references unknown stat: {binding.max_stat!r}",
                            )
                        )

    # Cross-manifest skill and buff reference validation.
    errors.extend(_validate_skill_refs(manifests))
    errors.extend(_validate_buff_refs(manifests))
    errors.extend(_validate_outcome_refs(manifests))
    errors.extend(_validate_prestige_effects(manifests))
    errors.extend(_validate_quest_stage_condition_refs(manifests))
    errors.extend(_validate_archetype_refs(manifests))

    return errors


def build_effective_conditions(manifests: List[ManifestEnvelope]) -> Tuple[List[ManifestEnvelope], List[LoadError]]:
    """Compile each location's effective_unlock from its full region ancestor chain."""
    regions: Dict[str, RegionManifest] = {}
    for m in manifests:
        if m.kind == "Region":
            regions[m.metadata.name] = cast(RegionManifest, m)

    errors: List[LoadError] = []

    def collect_ancestor_conditions(region_name: str, visited: Set[str]) -> List[Condition]:
        if region_name in visited:
            errors.append(LoadError(file=Path("<content>"), message=f"Circular region parent: {region_name!r}"))
            return []
        visited.add(region_name)
        region = regions.get(region_name)
        if region is None:
            return []
        chain: List[Condition] = []
        if region.spec.parent:
            chain.extend(collect_ancestor_conditions(region.spec.parent, visited))
        if region.spec.unlock:
            chain.append(region.spec.unlock)
        return chain

    for m in manifests:
        if m.kind != "Location":
            continue
        loc = cast(LocationManifest, m)
        chain = collect_ancestor_conditions(loc.spec.region, set())
        if loc.spec.unlock:
            chain.append(loc.spec.unlock)
        loc.spec.effective_unlock = AllCondition(type="all", conditions=chain) if chain else None

    # Also set effective_unlock on regions themselves (for region-level condition checking)
    for m in manifests:
        if m.kind != "Region":
            continue
        region = cast(RegionManifest, m)
        chain = collect_ancestor_conditions(region.metadata.name, set()) if region.spec.parent else []
        if region.spec.unlock:
            chain.append(region.spec.unlock)
        region.spec.effective_unlock = AllCondition(type="all", conditions=chain) if chain else None

    return manifests, errors


def _collect_all_template_strings(
    manifests: List[ManifestEnvelope],
) -> List[tuple[str, str, str]]:
    """Walk manifest trees and collect (template_id, template_str, context_type) triples.

    context_type is 'combat' for strings inside CombatStep branches; 'adventure' otherwise.
    template_id is a stable human-readable path for error messages.
    """
    from oscilla.engine.models.adventure import ChoiceStep, CombatStep, NarrativeStep, StatCheckStep

    results: List[tuple[str, str, str]] = []

    def _is_template(value: object) -> bool:
        if not isinstance(value, str):
            return False
        return "{{" in value or "{%" in value or bool(re.search(r"\{[A-Za-z]+\}", value))

    def _walk_effects(effects: List[Effect], path: str, context_type: str) -> None:
        for effect in effects:
            if isinstance(effect, StatChangeEffect) and _is_template(effect.amount):
                results.append((f"__effect_statchange_{id(effect)}", effect.amount, context_type))  # type: ignore[arg-type]
            elif isinstance(effect, ItemDropEffect) and _is_template(effect.count):
                results.append((f"__effect_itemdrop_{id(effect)}", effect.count, context_type))  # type: ignore[arg-type]

    def _walk_branch(branch: OutcomeBranch, path: str, context_type: str) -> None:
        _walk_effects(branch.effects, path, context_type)
        for i, substep in enumerate(branch.steps):
            _walk_step(substep, f"{path}.steps[{i}]", context_type)

    def _walk_step(step: Step, path: str, context_type: str) -> None:
        if isinstance(step, NarrativeStep):
            if _is_template(step.text):
                # Use id(step) so the same key is reproduced in run_narrative at runtime.
                results.append((f"__narrative_{id(step)}", step.text, context_type))
            _walk_effects(step.effects, path, context_type)
        elif isinstance(step, ChoiceStep):
            for j, option in enumerate(step.options):
                # ChoiceOption has effects and substeps like OutcomeBranch but is a distinct type.
                _walk_effects(option.effects, f"{path}.options[{j}]", context_type)
                for k, substep in enumerate(option.steps):
                    _walk_step(substep, f"{path}.options[{j}].steps[{k}]", context_type)
        elif isinstance(step, CombatStep):
            _walk_branch(step.on_win, f"{path}.on_victory", "combat")
            _walk_branch(step.on_defeat, f"{path}.on_defeat", "combat")
            if step.on_flee:
                _walk_branch(step.on_flee, f"{path}.on_flee", "combat")
        elif isinstance(step, StatCheckStep):
            _walk_branch(step.on_pass, f"{path}.on_success", context_type)
            _walk_branch(step.on_fail, f"{path}.on_failure", context_type)

    for manifest in manifests:
        if manifest.kind != "Adventure":
            continue
        adv_manifest = cast(AdventureManifest, manifest)
        name = adv_manifest.metadata.name
        for i, step in enumerate(adv_manifest.spec.steps):
            _walk_step(step, f"{name}:step[{i}]", "adventure")

    return results


def _validate_templates(
    manifests: List[ManifestEnvelope],
    engine: "GameTemplateEngine",
) -> List[LoadError]:
    """Precompile all template strings found in manifests and return any errors."""
    from oscilla.engine.templates import TemplateValidationError

    errors: List[LoadError] = []
    triples = _collect_all_template_strings(manifests)
    for template_id, template_str, context_type in triples:
        try:
            engine.precompile_and_validate(template_str, template_id, context_type)
        except TemplateValidationError as exc:
            errors.append(LoadError(file=Path(template_id), message=str(exc)))
    return errors


def _validate_pronoun_set_names(
    manifests: List[ManifestEnvelope],
) -> List[LoadError]:
    """Validate that extra_pronoun_sets in CharacterConfig do not conflict with built-in names."""
    from oscilla.engine.templates import PRONOUN_SETS

    errors: List[LoadError] = []
    for m in manifests:
        if m.kind != "CharacterConfig":
            continue
        cc = cast(CharacterConfigManifest, m)
        for ps_def in cc.spec.extra_pronoun_sets:
            if ps_def.name in PRONOUN_SETS:
                errors.append(
                    LoadError(
                        file=Path(f"<{m.metadata.name}>"),
                        message=(
                            f"extra_pronoun_sets name {ps_def.name!r} conflicts with a built-in "
                            "pronoun set; choose a different key."
                        ),
                    )
                )
    return errors


def _validate_labels(manifests: List[ManifestEnvelope]) -> List[LoadWarning]:
    """Check item labels against declared item_labels in the Game manifest.

    Emits a LoadWarning for each item label that is not declared in
    GameSpec.item_labels. Uses Levenshtein distance to suggest the closest
    declared label when distance ≤ 2 (single-character typos and transpositions).
    """
    from oscilla.engine.string_utils import levenshtein

    warnings: List[LoadWarning] = []

    game_manifest = next((m for m in manifests if m.kind == "Game"), None)
    if game_manifest is None:
        return warnings

    game = cast(GameManifest, game_manifest)
    declared_labels = {lbl.name for lbl in game.spec.item_labels}

    for m in manifests:
        if m.kind != "Item":
            continue
        item = cast(ItemManifest, m)
        for label in item.spec.labels:
            if label in declared_labels:
                continue
            # Find closest match for suggestion.
            best_match: str | None = None
            best_dist: int = 3  # threshold: distance ≤ 2 gives a suggestion
            for declared in declared_labels:
                dist = levenshtein(label, declared)
                if dist < best_dist:
                    best_dist = dist
                    best_match = declared
            if best_match is not None:
                suggestion = f"Did you mean '{best_match}'?"
            else:
                suggestion = f"Add '{label}' to item_labels in game.yaml to declare it."
            warnings.append(
                LoadWarning(
                    file=Path(f"<{m.metadata.name}>"),
                    message=f"item label {label!r} is not declared in GameSpec.item_labels",
                    suggestion=suggestion,
                )
            )

    return warnings


def _validate_passive_effects(manifests: List[ManifestEnvelope]) -> List[LoadWarning]:
    """Emit warnings for passive effects that use unsupported condition types.

    Passive effects are evaluated without a registry (to avoid recursion), so:
    - item_held_label and any_item_equipped conditions will always evaluate False.
    - character_stat conditions with stat_source: effective cannot access gear bonuses.
    """
    from oscilla.engine.models.base import AnyItemEquippedCondition, CharacterStatCondition, ItemHeldLabelCondition

    warnings: List[LoadWarning] = []

    game_manifest = next((m for m in manifests if m.kind == "Game"), None)
    if game_manifest is None:
        return warnings

    game = cast(GameManifest, game_manifest)

    def _check_condition(condition: object, passive_index: int) -> List[LoadWarning]:
        """Recursively check a condition tree for unsupported passive condition types."""
        from oscilla.engine.models.base import AllCondition, AnyCondition, NotCondition

        found: List[LoadWarning] = []
        if condition is None:
            return found
        if isinstance(condition, ItemHeldLabelCondition):
            found.append(
                LoadWarning(
                    file=Path("<game>"),
                    message=f"passive_effects[{passive_index}] uses item_held_label condition which requires a registry and will always evaluate False in passive context",
                    suggestion="Use a stat or milestone condition instead, or accept that this passive effect will never activate.",
                )
            )
        elif isinstance(condition, AnyItemEquippedCondition):
            found.append(
                LoadWarning(
                    file=Path("<game>"),
                    message=f"passive_effects[{passive_index}] uses any_item_equipped condition which requires a registry and will always evaluate False in passive context",
                    suggestion="Use a stat or milestone condition instead, or accept that this passive effect will never activate.",
                )
            )
        elif isinstance(condition, CharacterStatCondition) and condition.stat_source == "effective":
            found.append(
                LoadWarning(
                    file=Path("<game>"),
                    message=f"passive_effects[{passive_index}] uses character_stat with stat_source: effective which cannot access gear bonuses in passive context",
                    suggestion="Set stat_source: base to compare against raw stats, which is always available.",
                )
            )
        elif isinstance(condition, AllCondition):
            for sub in condition.conditions:
                found.extend(_check_condition(sub, passive_index))
        elif isinstance(condition, AnyCondition):
            for sub in condition.conditions:
                found.extend(_check_condition(sub, passive_index))
        elif isinstance(condition, NotCondition):
            found.extend(_check_condition(condition.condition, passive_index))
        return found

    for idx, passive in enumerate(game.spec.passive_effects):
        warnings.extend(_check_condition(passive.condition, idx))

    return warnings


def _collect_step_item_drop_effects(step: Step, effects: List[ItemDropEffect]) -> None:
    """Collect all ItemDropEffect instances recursively from a step tree."""
    match step:
        case NarrativeStep():
            for eff in step.effects:
                if isinstance(eff, ItemDropEffect):
                    effects.append(eff)
        case CombatStep():
            for branch in [step.on_win, step.on_defeat, step.on_flee]:
                for eff in branch.effects:
                    if isinstance(eff, ItemDropEffect):
                        effects.append(eff)
                for sub in branch.steps:
                    _collect_step_item_drop_effects(sub, effects)
        case ChoiceStep():
            for opt in step.options:
                for eff in opt.effects:
                    if isinstance(eff, ItemDropEffect):
                        effects.append(eff)
                for sub in opt.steps:
                    _collect_step_item_drop_effects(sub, effects)
        case StatCheckStep():
            for branch in [step.on_pass, step.on_fail]:
                for eff in branch.effects:
                    if isinstance(eff, ItemDropEffect):
                        effects.append(eff)
                for sub in branch.steps:
                    _collect_step_item_drop_effects(sub, effects)
        case _:
            pass


def _validate_loot_refs(registry: "ContentRegistry") -> List[LoadError]:
    """Verify every loot_ref in ItemDropEffect resolves to a known table or enemy."""
    errors: List[LoadError] = []
    for adv_manifest in registry.adventures.all():
        item_drop_effects: List[ItemDropEffect] = []
        for step in adv_manifest.spec.steps:
            _collect_step_item_drop_effects(step, item_drop_effects)
        for effect in item_drop_effects:
            if effect.loot_ref is None:
                continue
            entries = registry.resolve_loot_entries(effect.loot_ref)
            if entries is None:
                errors.append(
                    LoadError(
                        file=Path(f"<{adv_manifest.metadata.name}>"),
                        message=(f"loot_ref {effect.loot_ref!r} not found in loot_tables or enemies registry."),
                    )
                )
    return errors


def _validate_trigger_adventures(registry: "ContentRegistry") -> List[LoadWarning]:
    """Return load warnings for trigger_adventures validation.

    Checks:
    - Each key in trigger_adventures is a known trigger name.
    - Each adventure ref in every list resolves to a registered adventure.
    - emit_trigger effect names validate against triggers.custom.
    - No duplicate on_stat_threshold names.
    """
    warnings: List[LoadWarning] = []
    if registry.game is None:
        return warnings

    spec = registry.game.spec

    # Build allowed trigger key set.
    built_in_outcomes = {"completed", "defeated", "fled"}
    all_outcomes = built_in_outcomes | set(spec.outcomes)
    allowed_keys: Set[str] = {"on_character_create"}
    allowed_keys |= {f"on_outcome_{o}" for o in all_outcomes}
    if spec.triggers.on_game_rejoin is not None:
        allowed_keys.add("on_game_rejoin")
    for threshold in spec.triggers.on_stat_threshold:
        allowed_keys.add(threshold.name)
    for custom in spec.triggers.custom:
        allowed_keys.add(custom)

    for trigger_key, adv_refs in spec.trigger_adventures.items():
        # Specific warning for deprecated on_level_up key.
        if trigger_key == "on_level_up":
            warnings.append(
                LoadWarning(
                    file=Path("<game.yaml>"),
                    message="trigger_adventures key 'on_level_up' is no longer a built-in trigger.",
                    suggestion=(
                        "Use on_stat_threshold entries for your 'level' (or equivalent) stat and wire "
                        "the threshold names in trigger_adventures instead."
                    ),
                )
            )
            continue
        if trigger_key not in allowed_keys:
            warnings.append(
                LoadWarning(
                    file=Path("<game.yaml>"),
                    message=(
                        f"trigger_adventures key {trigger_key!r} is not a known trigger name. "
                        f"Allowed: {sorted(allowed_keys)}"
                    ),
                    suggestion=(
                        f"Remove or rename {trigger_key!r} to a valid trigger. "
                        "Valid keys: on_character_create, on_outcome_<name>, "
                        "on_game_rejoin, <threshold.name>, or a declared custom trigger name."
                    ),
                )
            )
        for ref in adv_refs:
            if registry.adventures.get(ref) is None:
                warnings.append(
                    LoadWarning(
                        file=Path("<game.yaml>"),
                        message=f"trigger_adventures[{trigger_key!r}] references unknown adventure {ref!r}.",
                        suggestion=f"Ensure adventure {ref!r} is defined in the content package.",
                    )
                )

    # Duplicate threshold names.
    threshold_names = [t.name for t in spec.triggers.on_stat_threshold]
    seen: Set[str] = set()
    for name in threshold_names:
        if name in seen:
            warnings.append(
                LoadWarning(
                    file=Path("<game.yaml>"),
                    message=f"Duplicate on_stat_threshold name {name!r} in game.yaml triggers.",
                    suggestion=f"Each on_stat_threshold entry must have a unique name. Rename one of the {name!r} entries.",
                )
            )
        seen.add(name)

    # on_stat_threshold stat names must refer to a known stat (stored or derived).
    if registry.character_config is not None:
        all_stat_defs = registry.character_config.spec.public_stats + registry.character_config.spec.hidden_stats
        all_known_stat_names: Set[str] = {s.name for s in all_stat_defs}
        for threshold in spec.triggers.on_stat_threshold:
            if threshold.stat not in all_known_stat_names:
                warnings.append(
                    LoadWarning(
                        file=Path("<game.yaml>"),
                        message=f"on_stat_threshold entry references unknown stat {threshold.stat!r}.",
                        suggestion=(
                            f"Declare a stat named {threshold.stat!r} in CharacterConfig public_stats "
                            "or hidden_stats, or correct the stat name."
                        ),
                    )
                )

    # emit_trigger effects must reference declared custom triggers.
    declared_custom: Set[str] = set(spec.triggers.custom)
    for adv_manifest in registry.adventures.all():
        emit_effects: List[EmitTriggerEffect] = []
        for step in adv_manifest.spec.steps:
            _collect_step_emit_trigger_effects(step, emit_effects)
        for effect in emit_effects:
            if effect.trigger not in declared_custom:
                warnings.append(
                    LoadWarning(
                        file=Path(f"<{adv_manifest.metadata.name}>"),
                        message=(
                            f"emit_trigger effect uses trigger name {effect.trigger!r} "
                            "which is not declared in game.yaml triggers.custom."
                        ),
                        suggestion=(
                            f"Add {effect.trigger!r} to game.yaml spec.triggers.custom, "
                            f"or change the effect to use a declared custom trigger name."
                        ),
                    )
                )

    return warnings


def _collect_step_emit_trigger_effects(step: "Step", effects: "List[EmitTriggerEffect]") -> None:
    """Recursively collect EmitTriggerEffect instances from a step tree."""
    match step:
        case NarrativeStep():
            for eff in step.effects:
                if isinstance(eff, EmitTriggerEffect):
                    effects.append(eff)
        case ChoiceStep():
            for opt in step.options:
                for sub in opt.steps:
                    _collect_step_emit_trigger_effects(sub, effects)
                for eff in opt.effects:
                    if isinstance(eff, EmitTriggerEffect):
                        effects.append(eff)
        case CombatStep():
            for branch in [step.on_win, step.on_defeat, step.on_flee]:
                for eff in branch.effects:
                    if isinstance(eff, EmitTriggerEffect):
                        effects.append(eff)
                for sub in branch.steps:
                    _collect_step_emit_trigger_effects(sub, effects)
        case StatCheckStep():
            for branch in [step.on_pass, step.on_fail]:
                for eff in branch.effects:
                    if isinstance(eff, EmitTriggerEffect):
                        effects.append(eff)
                for sub in branch.steps:
                    _collect_step_emit_trigger_effects(sub, effects)
        case PassiveStep():
            for eff in step.effects:
                if isinstance(eff, EmitTriggerEffect):
                    effects.append(eff)
        case _:
            pass


def _build_trigger_index(game: GameManifest) -> Dict[str, List[str]]:
    """Build the runtime lookup table from trigger_adventures."""
    return dict(game.spec.trigger_adventures)


def _build_stat_threshold_index(game: GameManifest) -> Dict[str, List[tuple[int, str]]]:
    """Build stat → [(threshold, trigger_name)] lookup for detection in effect handlers."""
    index: Dict[str, List[tuple[int, str]]] = {}
    for entry in game.spec.triggers.on_stat_threshold:
        index.setdefault(entry.stat, []).append((entry.threshold, entry.name))
    # Sort ascending so we can check all thresholds on a stat in one pass.
    for lst in index.values():
        lst.sort()
    return index


def _validate_no_derived_stat_writes(
    registry: "ContentRegistry",
    warnings: List[LoadWarning],
    errors: List[LoadError],
) -> None:
    """Reject stat_change and stat_set effects that target a derived stat."""
    char_config = registry.character_config
    if char_config is None:
        return
    all_stats = char_config.spec.public_stats + char_config.spec.hidden_stats
    derived_names: Set[str] = {s.name for s in all_stats if s.derived is not None}
    if not derived_names:
        return

    for adventure_manifest in registry.adventures.all():
        adventure_ref = adventure_manifest.metadata.name
        for step in adventure_manifest.spec.steps:
            _check_step_for_derived_writes(
                step=step,
                derived_names=derived_names,
                adventure_ref=adventure_ref,
                errors=errors,
            )


def _check_step_for_derived_writes(
    step: Step,
    derived_names: Set[str],
    adventure_ref: str,
    errors: List[LoadError],
) -> None:
    """Recursively check all effects in a step for writes to derived stats."""
    effects_to_check: List[Effect] = []
    match step:
        case NarrativeStep():
            effects_to_check.extend(step.effects)
        case PassiveStep():
            effects_to_check.extend(step.effects)
        case ChoiceStep():
            for choice in step.options:
                for eff in choice.effects:
                    if isinstance(eff, (StatChangeEffect, StatSetEffect)) and eff.stat in derived_names:
                        errors.append(
                            LoadError(
                                file=Path(f"<{adventure_ref}>"),
                                message=(
                                    f"Effect targets derived stat {eff.stat!r} in adventure {adventure_ref!r}. "
                                    "Derived stats cannot be modified directly."
                                ),
                            )
                        )
        case CombatStep():
            for branch in [step.on_win, step.on_defeat, step.on_flee]:
                for eff in branch.effects:
                    if isinstance(eff, (StatChangeEffect, StatSetEffect)) and eff.stat in derived_names:
                        errors.append(
                            LoadError(
                                file=Path(f"<{adventure_ref}>"),
                                message=(
                                    f"Effect targets derived stat {eff.stat!r} in adventure {adventure_ref!r}. "
                                    "Derived stats cannot be modified directly."
                                ),
                            )
                        )
        case _:
            pass
    for eff in effects_to_check:
        if isinstance(eff, (StatChangeEffect, StatSetEffect)) and eff.stat in derived_names:
            errors.append(
                LoadError(
                    file=Path(f"<{adventure_ref}>"),
                    message=(
                        f"Effect targets derived stat {eff.stat!r} in adventure {adventure_ref!r}. "
                        "Derived stats cannot be modified directly."
                    ),
                )
            )


def _build_derived_eval_order(
    char_config: CharacterConfigManifest,
    errors: List[LoadError],
) -> "List[Any]":
    """Topologically sort derived stats so dependencies are evaluated before dependents.

    Uses DFS with cycle detection. Any cycle (including self-reference) appends a
    LoadError and returns an empty list to halt derived stat processing.
    Non-derived stats are excluded; the result contains only derived stats in safe order.
    """
    from oscilla.engine.models.character_config import StatDefinition

    all_stats = char_config.spec.public_stats + char_config.spec.hidden_stats
    derived_map: Dict[str, StatDefinition] = {s.name: s for s in all_stats if s.derived is not None}
    if not derived_map:
        return []

    def _deps(stat_def: StatDefinition) -> Set[str]:
        assert stat_def.derived is not None
        # Extract references to other derived stats from the formula string.
        return {
            name
            for name in derived_map
            if f'player.stats["{name}"]' in stat_def.derived or f"player.stats['{name}']" in stat_def.derived
        }

    sorted_stats: List[StatDefinition] = []
    visited: Set[str] = set()
    in_stack: Set[str] = set()
    cycle_found = False

    def visit(name: str) -> bool:
        nonlocal cycle_found
        if name in in_stack:
            errors.append(
                LoadError(
                    file=Path("<CharacterConfig>"),
                    message=(
                        f"Circular dependency detected in derived stats involving {name!r}. "
                        "Derived stat formulas must not form cycles."
                    ),
                )
            )
            cycle_found = True
            return False
        if name in visited:
            return True
        in_stack.add(name)
        stat_def = derived_map[name]
        for dep in _deps(stat_def):
            if not visit(dep):
                return False
        in_stack.discard(name)
        visited.add(name)
        sorted_stats.append(stat_def)
        return True

    for name in derived_map:
        if name not in visited:
            if not visit(name):
                return []

    return sorted_stats


def load(content_path: Path) -> Tuple[ContentRegistry, List[LoadWarning]]:
    """Orchestrate scan → parse → validate_references → build_effective_conditions → template validation.

    content_path may be either a directory (scanned recursively for .yaml/.yml files)
    or a path to a single YAML file (all documents in that file are used directly).
    Single-file mode is the path taken by compiled content archives.

    Returns a tuple of (ContentRegistry, warnings). Warnings are non-fatal issues
    that are surfaced in `oscilla validate` output but do not prevent the game from running.

    Raises ContentLoadError with all accumulated errors if any hard errors are found.
    """
    from oscilla.engine.templates import GameTemplateEngine

    t0 = time.perf_counter()
    # Single-file mode: treat the file itself as the complete manifest list.
    if content_path.is_file():
        paths = [content_path]
    else:
        paths = scan(content_path)
    manifests, parse_errors = parse(paths)

    ref_errors = validate_references(manifests) if manifests else []
    manifests, compile_errors = build_effective_conditions(manifests)

    all_errors = parse_errors + ref_errors + compile_errors
    if all_errors:
        raise ContentLoadError(all_errors)

    # Template validation: extract stat names from CharacterConfig for the mock context.
    char_config = next((m for m in manifests if m.kind == "CharacterConfig"), None)
    stat_names: List[str] = []
    if char_config is not None:
        cc = cast(CharacterConfigManifest, char_config)
        all_stats = cc.spec.public_stats + cc.spec.hidden_stats
        stat_names = [s.name for s in all_stats]

    # Detect if the game manifest has an in-game time system configured so the
    # template engine can provide a mock InGameTimeView during validation.
    game_manifest = next((m for m in manifests if m.kind == "Game"), None)
    has_ingame_time = False
    if game_manifest is not None:
        from oscilla.engine.models.game import GameManifest

        gm = cast(GameManifest, game_manifest)
        has_ingame_time = gm.spec.time is not None

    template_engine = GameTemplateEngine(stat_names=stat_names, has_ingame_time=has_ingame_time)

    # Validate derived stat definitions and precompile their formulas.
    derived_errors: List[LoadError] = []
    derived_eval_order: List[Any] = []
    if char_config is not None:
        cc = cast(CharacterConfigManifest, char_config)
        derived_eval_order = _build_derived_eval_order(cc, derived_errors)
        # Precompile derived stat formulas using the template engine so formula
        # errors are caught at load time rather than runtime.
        for stat_def in derived_eval_order:
            assert stat_def.derived is not None
            template_id = f"__derived_{stat_def.name}"
            try:
                template_engine.precompile_and_validate(
                    raw=stat_def.derived,
                    template_id=template_id,
                    context_type="adventure",
                )
            except Exception as exc:
                derived_errors.append(
                    LoadError(
                        file=Path("<CharacterConfig>"),
                        message=f"Derived stat {stat_def.name!r} formula failed validation: {exc}",
                    )
                )

    pronoun_errors = _validate_pronoun_set_names(manifests)
    template_errors = _validate_templates(manifests, template_engine)
    if pronoun_errors or template_errors or derived_errors:
        raise ContentLoadError(pronoun_errors + template_errors + derived_errors)

    registry = ContentRegistry.build(manifests, template_engine=template_engine)
    registry.derived_eval_order = derived_eval_order

    loot_ref_errors = _validate_loot_refs(registry)
    derived_write_errors: List[LoadError] = []
    _validate_no_derived_stat_writes(registry=registry, warnings=[], errors=derived_write_errors)
    all_post_errors = loot_ref_errors + derived_write_errors
    if all_post_errors:
        raise ContentLoadError(all_post_errors)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info("Content loaded in %.1f ms (%d manifests)", elapsed_ms, len(manifests))

    # Collect non-fatal warnings.
    warnings: List[LoadWarning] = []
    warnings.extend(_validate_labels(manifests))
    warnings.extend(_validate_passive_effects(manifests))
    warnings.extend(_validate_trigger_adventures(registry))

    # Build runtime trigger indexes after validation.
    if registry.game is not None:
        registry.trigger_index = _build_trigger_index(registry.game)
        registry.stat_threshold_index = _build_stat_threshold_index(registry.game)

    return registry, warnings


def compute_epoch_offset(spec: "GameTimeSpec") -> int:
    """Compute the tick offset corresponding to the epoch's named position.

    The offset is added to game_ticks before computing cycle positions, so that
    tick 0 displays as the epoch's named position rather than the start of the
    first cycle.

    Returns 0 when no epoch positions are declared or when no cycles are configured.
    """
    if not spec.cycles or not spec.epoch:
        return 0

    # Build name/alias → CycleSpec mapping.
    by_name: Dict[str, Any] = {}
    for cycle in spec.cycles:
        by_name[cycle.name] = cycle
        if hasattr(cycle, "aliases"):
            for alias in cycle.aliases:
                by_name[alias] = cycle

    def _ticks_per_unit(name: str) -> int:
        c = by_name[name]
        if c.type == "ticks":
            return 1
        parent = by_name[c.parent]
        return int(c.count * _ticks_per_unit(parent.name))

    offset = 0
    for cycle_name, value in spec.epoch.items():
        epoch_cycle = by_name.get(cycle_name)
        if epoch_cycle is None:
            continue
        # Resolve value to a 0-based index.
        if isinstance(value, str):
            labels = epoch_cycle.labels if epoch_cycle.type == "cycle" else []
            idx = labels.index(value) if value in labels else 0
        else:
            idx = max(0, int(value) - 1)  # 1-based author input → 0-based
        # Contribution of this epoch entry to the total offset.
        if epoch_cycle.type == "ticks":
            tpu_parent = 1
        else:
            tpu_parent = _ticks_per_unit(by_name[epoch_cycle.parent].name)
        offset += idx * tpu_parent

    return offset


def load_games(library_root: Path) -> Tuple[Dict[str, ContentRegistry], Dict[str, List[LoadWarning]]]:
    """Load all game packages found directly under library_root.

    Each immediate subdirectory containing a ``game.yaml`` file is treated as a
    game package and passed to :func:`load`.  Subdirectories without ``game.yaml``
    are silently skipped so the library root can contain non-game files.

    Returns a tuple of (games dict, per-game warnings dict).

    Raises ContentLoadError with errors prefixed by package name if any game
    fails to load.
    """
    games: Dict[str, ContentRegistry] = {}
    all_warnings: Dict[str, List[LoadWarning]] = {}
    accumulated: List[LoadError] = []

    for subdir in sorted(library_root.iterdir()):
        if not subdir.is_dir():
            continue
        if not (subdir / "game.yaml").exists():
            logger.debug("Skipping %s — no game.yaml found", subdir.name)
            continue
        try:
            registry, warnings = load(subdir)
        except ContentLoadError as exc:
            for err in exc.errors:
                accumulated.append(LoadError(file=err.file, message=f"[{subdir.name}] {err.message}"))
            continue

        package_key = subdir.name
        games[package_key] = registry
        all_warnings[package_key] = warnings
        logger.info("Loaded game package %r from %s", package_key, subdir)

    if accumulated:
        raise ContentLoadError(accumulated)

    return games, all_warnings
