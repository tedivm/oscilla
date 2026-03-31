"""Content loader — scans, parses, validates, and builds the ContentRegistry."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import Dict, List, Set, Tuple, cast

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from oscilla.engine.models import MANIFEST_REGISTRY
from oscilla.engine.models.adventure import (
    AdventureManifest,
    ChoiceStep,
    CombatStep,
    Effect,
    NarrativeStep,
    OutcomeBranch,
    StatCheckStep,
    Step,
    UseItemEffect,
)
from oscilla.engine.models.base import AllCondition, Condition, ManifestEnvelope, normalise_condition
from oscilla.engine.models.character_config import CharacterConfigManifest
from oscilla.engine.models.item import ItemManifest
from oscilla.engine.models.location import LocationManifest
from oscilla.engine.models.recipe import RecipeManifest
from oscilla.engine.models.region import RegionManifest
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


def load(content_dir: Path) -> ContentRegistry:
    """Orchestrate scan → parse → validate_references → build_effective_conditions.

    Raises ContentLoadError with all accumulated errors if any are found.
    """
    t0 = time.perf_counter()
    paths = scan(content_dir)
    manifests, parse_errors = parse(paths)

    ref_errors = validate_references(manifests) if manifests else []
    manifests, compile_errors = build_effective_conditions(manifests)

    all_errors = parse_errors + ref_errors + compile_errors
    if all_errors:
        raise ContentLoadError(all_errors)

    registry = ContentRegistry.build(manifests)
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
