"""Content loader — scans, parses, validates, and builds the ContentRegistry."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Set, Tuple, cast

if TYPE_CHECKING:
    from oscilla.engine.templates import GameTemplateEngine

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from oscilla.engine.models import MANIFEST_REGISTRY
from oscilla.engine.models.adventure import (
    AdventureManifest,
    ApplyBuffEffect,
    ChoiceStep,
    CombatStep,
    Effect,
    ItemDropEffect,
    NarrativeStep,
    OutcomeBranch,
    SkillGrantEffect,
    StatChangeEffect,
    StatCheckStep,
    Step,
    UseItemEffect,
    XpGrantEffect,
)
from oscilla.engine.models.base import AllCondition, Condition, ManifestEnvelope, normalise_condition
from oscilla.engine.models.buff import BuffManifest
from oscilla.engine.models.character_config import CharacterConfigManifest
from oscilla.engine.models.item import ItemManifest
from oscilla.engine.models.location import LocationManifest
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


class ContentLoadError(Exception):
    def __init__(self, errors: List[LoadError]) -> None:
        self.errors = errors
        lines = "\n".join(f"  {e}" for e in errors)
        super().__init__(f"{len(errors)} content error(s):\n{lines}")


def scan(content_dir: Path) -> List[Path]:
    """Return all .yaml / .yml files found recursively under content_dir, sorted."""
    return sorted(p for p in content_dir.rglob("*") if p.suffix in {".yaml", ".yml"})


def _normalise_manifest_conditions(raw: Dict[str, object]) -> Dict[str, object]:
    """Recursively normalise condition fields in a raw manifest dict."""
    spec = raw.get("spec")
    if not isinstance(spec, dict):
        return raw

    kind = raw.get("kind")

    if kind == "Region":
        if "unlock" in spec and spec["unlock"] is not None:
            spec["unlock"] = normalise_condition(spec["unlock"])

    elif kind == "Location":
        if "unlock" in spec and spec["unlock"] is not None:
            spec["unlock"] = normalise_condition(spec["unlock"])
        for entry in spec.get("adventures", []):
            if isinstance(entry, dict) and "requires" in entry and entry["requires"] is not None:
                entry["requires"] = normalise_condition(entry["requires"])

    elif kind == "Adventure":
        steps = spec.get("steps", [])
        if isinstance(steps, list):
            spec["steps"] = [_normalise_step(s) for s in steps]
        if "requires" in spec and spec["requires"] is not None:
            spec["requires"] = normalise_condition(spec["requires"])

    return raw


def _normalise_step(step: object) -> object:
    """Normalise condition fields within an adventure step dict."""
    if not isinstance(step, dict):
        return step
    step_type = step.get("type")

    if step_type == "stat_check":
        if "condition" in step and step["condition"] is not None:
            step["condition"] = normalise_condition(step["condition"])
        for branch_key in ("on_pass", "on_fail"):
            if branch_key in step and isinstance(step[branch_key], dict):
                step[branch_key] = _normalise_branch(step[branch_key])

    elif step_type == "combat":
        for branch_key in ("on_win", "on_defeat", "on_flee"):
            if branch_key in step and isinstance(step[branch_key], dict):
                step[branch_key] = _normalise_branch(step[branch_key])

    elif step_type == "choice":
        for opt in step.get("options", []):
            if not isinstance(opt, dict):
                continue
            if "requires" in opt and opt["requires"] is not None:
                opt["requires"] = normalise_condition(opt["requires"])
            if "steps" in opt and isinstance(opt["steps"], list):
                opt["steps"] = [_normalise_step(s) for s in opt["steps"]]

    elif step_type == "narrative":
        pass  # no conditions in narrative steps

    return step


def _normalise_branch(branch: Dict[str, object]) -> Dict[str, object]:
    if "steps" in branch and isinstance(branch["steps"], list):
        branch["steps"] = [_normalise_step(s) for s in branch["steps"]]
    return branch


def parse(paths: List[Path]) -> Tuple[List[ManifestEnvelope], List[LoadError]]:
    """Parse YAML files and validate against Pydantic models. Accumulates errors."""
    manifests: List[ManifestEnvelope] = []
    errors: List[LoadError] = []

    for path in paths:
        try:
            raw = _yaml.load(path.read_text(encoding="utf-8"))
        except YAMLError as exc:
            errors.append(LoadError(file=path, message=f"YAML parse error: {exc}"))
            continue
        except OSError as exc:
            errors.append(LoadError(file=path, message=f"File read error: {exc}"))
            continue

        if not isinstance(raw, dict):
            errors.append(LoadError(file=path, message="Manifest must be a YAML mapping"))
            continue

        kind = raw.get("kind", "<missing>")
        model_cls = MANIFEST_REGISTRY.get(str(kind))
        if model_cls is None:
            errors.append(LoadError(file=path, message=f"Unknown kind: {kind!r}"))
            continue

        # Normalise bare YAML condition keys before Pydantic validation
        try:
            raw = _normalise_manifest_conditions(raw)
        except ValueError as exc:
            errors.append(LoadError(file=path, message=f"Condition normalisation error: {exc}"))
            continue

        try:
            manifests.append(model_cls.model_validate(raw))
        except ValidationError as exc:
            for err in exc.errors():
                loc = " → ".join(str(x) for x in err["loc"])
                errors.append(LoadError(file=path, message=f"{loc}: {err['msg']}"))

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
            if isinstance(effect, XpGrantEffect) and _is_template(effect.amount):
                results.append((f"__effect_xp_{id(effect)}", effect.amount, context_type))  # type: ignore[arg-type]
            elif isinstance(effect, StatChangeEffect) and _is_template(effect.amount):
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


def load(content_dir: Path) -> ContentRegistry:
    """Orchestrate scan → parse → validate_references → build_effective_conditions → template validation.

    Raises ContentLoadError with all accumulated errors if any are found.
    """
    from oscilla.engine.templates import GameTemplateEngine

    t0 = time.perf_counter()
    paths = scan(content_dir)
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
    template_engine = GameTemplateEngine(stat_names=stat_names)

    pronoun_errors = _validate_pronoun_set_names(manifests)
    template_errors = _validate_templates(manifests, template_engine)
    if pronoun_errors or template_errors:
        raise ContentLoadError(pronoun_errors + template_errors)

    registry = ContentRegistry.build(manifests, template_engine=template_engine)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info("Content loaded in %.1f ms (%d manifests)", elapsed_ms, len(manifests))
    return registry


def load_games(library_root: Path) -> Dict[str, ContentRegistry]:
    """Load all game packages found directly under library_root.

    Each immediate subdirectory containing a ``game.yaml`` file is treated as a
    game package and passed to :func:`load`.  Subdirectories without ``game.yaml``
    are silently skipped so the library root can contain non-game files.

    Raises ContentLoadError with errors prefixed by package name if any game
    fails to load.
    """
    games: Dict[str, ContentRegistry] = {}
    accumulated: List[LoadError] = []

    for subdir in sorted(library_root.iterdir()):
        if not subdir.is_dir():
            continue
        if not (subdir / "game.yaml").exists():
            logger.debug("Skipping %s — no game.yaml found", subdir.name)
            continue
        try:
            registry = load(subdir)
        except ContentLoadError as exc:
            for err in exc.errors:
                accumulated.append(LoadError(file=err.file, message=f"[{subdir.name}] {err.message}"))
            continue

        package_key = subdir.name
        games[package_key] = registry
        logger.info("Loaded game package %r from %s", package_key, subdir)

    if accumulated:
        raise ContentLoadError(accumulated)

    return games
