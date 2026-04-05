"""Content graph construction — format-agnostic node/edge structure.

Graph building is a pure function over ContentRegistry. Rendering to DOT,
Mermaid, or ASCII is handled by oscilla/engine/graph_renderers.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from oscilla.engine.models.adventure import AdventureManifest
    from oscilla.engine.models.base import ManifestEnvelope
    from oscilla.engine.registry import ContentRegistry


@dataclass
class GraphNode:
    id: str  # Globally unique; convention: "kind:name", e.g. "region:combat"
    label: str  # Human-readable display label
    kind: str  # "region", "location", "adventure", "step", "enemy", "item", …
    attrs: Dict[str, str] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str  # GraphNode.id
    target: str  # GraphNode.id
    label: str = ""
    edge_type: str = ""  # "parent", "contains", "references", "flow", "outcome"


@dataclass
class ContentGraph:
    title: str
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)

    def has_node(self, node_id: str) -> bool:
        return any(n.id == node_id for n in self.nodes)


def build_world_graph(registry: "ContentRegistry") -> ContentGraph:
    """Build the region → location → adventure-pool hierarchy graph."""
    graph = ContentGraph(title="World Map")

    # Root game node
    game_name = registry.game.spec.displayName if registry.game else "Game"
    root_id = "game:root"
    graph.add_node(GraphNode(id=root_id, label=game_name, kind="game"))

    # Regions
    for region in registry.regions.all():
        rid = f"region:{region.metadata.name}"
        unlock_label = _condition_summary(region.spec.unlock)
        graph.add_node(
            GraphNode(
                id=rid,
                label=region.spec.displayName,
                kind="region",
                attrs={"unlock": unlock_label},
            )
        )
        parent_id = f"region:{region.spec.parent}" if region.spec.parent else root_id
        graph.add_edge(
            GraphEdge(
                source=parent_id,
                target=rid,
                edge_type="contains",
                label="sub-region" if region.spec.parent else "",
            )
        )

    # Locations
    for loc in registry.locations.all():
        lid = f"location:{loc.metadata.name}"
        graph.add_node(
            GraphNode(
                id=lid,
                label=loc.spec.displayName,
                kind="location",
                attrs={"unlock": _condition_summary(loc.spec.unlock)},
            )
        )
        region_id = f"region:{loc.spec.region}"
        graph.add_edge(GraphEdge(source=region_id, target=lid, edge_type="contains"))

        # Adventure pool entries
        for entry in loc.spec.adventures:
            adv = registry.adventures.get(entry.ref)
            adv_label = adv.spec.displayName if adv else entry.ref
            aid = f"adventure:{entry.ref}"
            if not graph.has_node(aid):
                graph.add_node(GraphNode(id=aid, label=adv_label, kind="adventure"))
            req_label = f"w:{entry.weight}" + (f", req:{_condition_summary(entry.requires)}" if entry.requires else "")
            graph.add_edge(
                GraphEdge(
                    source=lid,
                    target=aid,
                    edge_type="references",
                    label=req_label,
                )
            )

    return graph


def build_adventure_graph(
    manifest: "AdventureManifest",
    registry: "ContentRegistry",
) -> ContentGraph:
    """Build the step-flow graph for a single adventure.

    Nodes are individual steps; edges represent execution flow including choice
    branches, goto jumps, and combat outcome forks.
    """
    from oscilla.engine.models.adventure import ChoiceStep, CombatStep, NarrativeStep, PassiveStep, StatCheckStep

    title = manifest.spec.displayName
    graph = ContentGraph(title=f"Adventure Flow: {title}")

    start_id = "start"
    graph.add_node(GraphNode(id=start_id, label="start", kind="start"))

    counter: List[int] = [0]  # mutable counter for step IDs across recursion

    def step_id() -> str:
        counter[0] += 1
        return f"step:{counter[0]}"

    def _add_step(step: object, prev_id: str, edge_label: str = "") -> str:
        """Add a step node and edge from prev_id. Returns this step's node id."""
        sid = step_id()
        match step:
            case NarrativeStep():
                text_preview = (step.text or "")[:40].replace("\n", " ")
                graph.add_node(
                    GraphNode(
                        id=sid,
                        label=f"narrative: {text_preview!r}",
                        kind="narrative",
                        attrs={"label": step.label or ""},
                    )
                )
            case CombatStep():
                graph.add_node(
                    GraphNode(
                        id=sid,
                        label=f"combat: {step.enemy}",
                        kind="combat",
                        attrs={"enemy": step.enemy, "label": step.label or ""},
                    )
                )
                # Combat outcome branches
                for branch_name, branch in [
                    ("on_win", step.on_win),
                    ("on_defeat", step.on_defeat),
                    ("on_flee", step.on_flee),
                ]:
                    if branch.goto:
                        goto_id = f"goto:{branch.goto}"
                        if not graph.has_node(goto_id):
                            graph.add_node(GraphNode(id=goto_id, label=f"→ {branch.goto}", kind="goto"))
                        graph.add_edge(GraphEdge(source=sid, target=goto_id, edge_type="outcome", label=branch_name))
                    elif branch.steps:
                        sub_prev = sid
                        for sub_step in branch.steps:
                            sub_prev = _add_step(sub_step, sub_prev, branch_name)
                    else:
                        end_id = f"end:{branch_name}:{counter[0]}"
                        graph.add_node(GraphNode(id=end_id, label=f"(end → {branch_name})", kind="end"))
                        graph.add_edge(GraphEdge(source=sid, target=end_id, edge_type="outcome", label=branch_name))
            case ChoiceStep():
                graph.add_node(
                    GraphNode(
                        id=sid,
                        label=f"choice: {step.prompt[:40]!r}",
                        kind="choice",
                        attrs={"label": step.label or ""},
                    )
                )
                for opt in step.options:
                    if opt.goto:
                        goto_id = f"goto:{opt.goto}"
                        if not graph.has_node(goto_id):
                            graph.add_node(GraphNode(id=goto_id, label=f"→ {opt.goto}", kind="goto"))
                        graph.add_edge(GraphEdge(source=sid, target=goto_id, edge_type="flow", label=opt.label[:30]))
                    elif opt.steps:
                        opt_prev = sid
                        for sub_step in opt.steps:
                            opt_prev = _add_step(sub_step, opt_prev, opt.label[:20])
                    else:
                        fall_id = f"fall:{counter[0]}"
                        graph.add_node(GraphNode(id=fall_id, label="(continue)", kind="continue"))
                        graph.add_edge(GraphEdge(source=sid, target=fall_id, edge_type="flow", label=opt.label[:30]))
            case StatCheckStep():
                cond_summary = _condition_summary(step.condition)
                graph.add_node(
                    GraphNode(
                        id=sid,
                        label=f"stat_check: {cond_summary}",
                        kind="stat_check",
                        attrs={"label": step.label or ""},
                    )
                )
                for branch_name, branch in [("on_pass", step.on_pass), ("on_fail", step.on_fail)]:
                    if branch.goto:
                        goto_id = f"goto:{branch.goto}"
                        if not graph.has_node(goto_id):
                            graph.add_node(GraphNode(id=goto_id, label=f"→ {branch.goto}", kind="goto"))
                        graph.add_edge(GraphEdge(source=sid, target=goto_id, edge_type="flow", label=branch_name))
                    elif branch.steps:
                        sub_prev = sid
                        for sub_step in branch.steps:
                            sub_prev = _add_step(sub_step, sub_prev, branch_name)
            case PassiveStep():
                eff_count = len(step.effects)
                graph.add_node(
                    GraphNode(
                        id=sid,
                        label=f"passive ({eff_count} effects)",
                        kind="passive",
                        attrs={"label": step.label or ""},
                    )
                )
        graph.add_edge(GraphEdge(source=prev_id, target=sid, edge_type="flow", label=edge_label))
        return sid

    prev = start_id
    for step in manifest.spec.steps:
        prev = _add_step(step, prev)

    return graph


def build_deps_graph(
    registry: "ContentRegistry",
    focus: str | None = None,
    include_kinds: set[str] | None = None,
    exclude_kinds: set[str] | None = None,
) -> ContentGraph:
    """Build the cross-manifest dependency graph.

    When focus is provided (format: "kind:name", e.g. "item:rusty-sword"),
    returns only the 1-hop neighborhood of that node.

    include_kinds: if provided, only nodes of these kinds are included.
    exclude_kinds: if provided, nodes of these kinds are removed.
    The focus node is always included regardless of kind filters.
    """
    from oscilla.engine.models.adventure import ApplyBuffEffect, CombatStep, ItemDropEffect, SkillGrantEffect

    graph = ContentGraph(title="Content Dependency Graph")

    def _node(kind: str, name: str, label: str) -> str:
        nid = f"{kind}:{name}"
        if not graph.has_node(nid):
            graph.add_node(GraphNode(id=nid, label=label, kind=kind))
        return nid

    def _edge(src: str, tgt: str, lbl: str, etype: str) -> None:
        graph.add_edge(GraphEdge(source=src, target=tgt, label=lbl, edge_type=etype))

    # Regions → parent region
    for region in registry.regions.all():
        rid = _node("region", region.metadata.name, region.spec.displayName)
        if region.spec.parent:
            prid = _node("region", region.spec.parent, region.spec.parent)
            _edge(rid, prid, "parent", "parent")

    # Locations → region
    for loc in registry.locations.all():
        lid = _node("location", loc.metadata.name, loc.spec.displayName)
        rid = _node("region", loc.spec.region, loc.spec.region)
        _edge(lid, rid, "in region", "contains")

        # Adventures in pool
        for entry in loc.spec.adventures:
            aid = _node("adventure", entry.ref, entry.ref)
            _edge(lid, aid, f"pool w:{entry.weight}", "references")

    # Adventures → enemies, items (via effects), loot tables
    for adv in registry.adventures.all():
        aid = _node("adventure", adv.metadata.name, adv.spec.displayName)
        for step in _walk_all_steps(adv.spec.steps):
            match step:
                case CombatStep():
                    eid = _node("enemy", step.enemy, step.enemy)
                    _edge(aid, eid, "combat", "references")
        for effect in _walk_all_effects(adv.spec.steps):
            if isinstance(effect, ItemDropEffect):
                if effect.loot_ref:
                    tgt = _node("loot-table", effect.loot_ref, effect.loot_ref)
                    _edge(aid, tgt, "drops", "references")
                elif effect.loot:
                    for loot_entry in effect.loot:
                        iid = _node("item", loot_entry.item, loot_entry.item)
                        _edge(aid, iid, "drops", "references")
            elif isinstance(effect, SkillGrantEffect):
                sid = _node("skill", effect.skill, effect.skill)
                _edge(aid, sid, "grants", "references")
            elif isinstance(effect, ApplyBuffEffect):
                bid = _node("buff", effect.buff_ref, effect.buff_ref)
                _edge(aid, bid, "applies", "references")

    # Enemies → loot
    for enemy in registry.enemies.all():
        eid = _node("enemy", enemy.metadata.name, enemy.spec.displayName)
        for loot_entry in enemy.spec.loot:
            iid = _node("item", loot_entry.item, loot_entry.item)
            _edge(eid, iid, "loot", "references")
        for skill_entry in enemy.spec.skills:
            sid = _node("skill", skill_entry.skill_ref, skill_entry.skill_ref)
            _edge(eid, sid, "uses", "references")

    # Recipes → items
    for recipe in registry.recipes.all():
        rid = _node("recipe", recipe.metadata.name, recipe.spec.displayName)
        out_id = _node("item", recipe.spec.output.item, recipe.spec.output.item)
        _edge(rid, out_id, "produces", "references")
        for ingredient in recipe.spec.inputs:
            iid = _node("item", ingredient.item, ingredient.item)
            _edge(rid, iid, "requires", "references")

    # LootTables → items
    for lt in registry.loot_tables.all():
        lid = _node("loot-table", lt.metadata.name, lt.metadata.name)
        for loot_entry in lt.spec.loot:
            iid = _node("item", loot_entry.item, loot_entry.item)
            _edge(lid, iid, "drops", "references")

    # Quests → milestones (advance_on entries)
    for quest in registry.quests.all():
        qid = _node("quest", quest.metadata.name, quest.spec.displayName)
        for stage in quest.spec.stages:
            for ms in stage.advance_on:
                mid = _node("milestone", ms, ms)
                _edge(qid, mid, "advances on", "references")

    if focus is not None:
        graph = _filter_to_neighborhood(graph, focus)

    # Apply kind filters after focus so the focus node's context is preserved.
    if include_kinds is not None or exclude_kinds is not None:
        kept_ids = {
            n.id
            for n in graph.nodes
            if (include_kinds is None or n.kind in include_kinds)
            and (exclude_kinds is None or n.kind not in exclude_kinds)
            or n.id == focus  # always keep the focus node itself
        }
        filtered = ContentGraph(title=graph.title)
        for node in graph.nodes:
            if node.id in kept_ids:
                filtered.add_node(node)
        for edge in graph.edges:
            if edge.source in kept_ids and edge.target in kept_ids:
                filtered.add_edge(edge)
        graph = filtered

    return graph


def _filter_to_neighborhood(graph: ContentGraph, focus_id: str) -> ContentGraph:
    """Return a new ContentGraph containing only the focus node and its direct neighbors."""
    connected_ids = {focus_id}
    for edge in graph.edges:
        if edge.source == focus_id:
            connected_ids.add(edge.target)
        if edge.target == focus_id:
            connected_ids.add(edge.source)

    filtered = ContentGraph(title=f"Dependencies of {focus_id}")
    for node in graph.nodes:
        if node.id in connected_ids:
            filtered.add_node(node)
    for edge in graph.edges:
        if edge.source in connected_ids and edge.target in connected_ids:
            filtered.add_edge(edge)
    return filtered


def _condition_summary(condition: object) -> str:
    """Return a short human-readable summary of a condition for graph labels."""
    if condition is None:
        return "always"
    ctype = getattr(condition, "type", "?")
    match ctype:
        case "level":
            return f"level≥{getattr(condition, 'value', '?')}"
        case "milestone":
            return f"milestone:{getattr(condition, 'name', '?')}"
        case "all":
            return "all(…)"
        case "any":
            return "any(…)"
        case _:
            return ctype


def _walk_all_steps(steps: list) -> list:
    """Recursively collect all steps including those nested in branches."""
    from oscilla.engine.models.adventure import ChoiceStep, CombatStep, StatCheckStep

    result = []
    for step in steps:
        result.append(step)
        match step:
            case CombatStep():
                for branch in [step.on_win, step.on_defeat, step.on_flee]:
                    result.extend(_walk_all_steps(branch.steps))
            case ChoiceStep():
                for opt in step.options:
                    result.extend(_walk_all_steps(opt.steps))
            case StatCheckStep():
                for branch in [step.on_pass, step.on_fail]:
                    result.extend(_walk_all_steps(branch.steps))
    return result


def _walk_all_effects(steps: list) -> list:
    """Recursively collect all effects from all steps and their branches."""
    from oscilla.engine.models.adventure import ChoiceStep, CombatStep, NarrativeStep, PassiveStep, StatCheckStep

    result = []
    for step in steps:
        match step:
            case NarrativeStep():
                result.extend(step.effects)
            case PassiveStep():
                result.extend(step.effects)
            case CombatStep():
                for branch in [step.on_win, step.on_defeat, step.on_flee]:
                    result.extend(branch.effects)
                    result.extend(_walk_all_effects(branch.steps))
            case ChoiceStep():
                for opt in step.options:
                    result.extend(opt.effects)
                    result.extend(_walk_all_effects(opt.steps))
            case StatCheckStep():
                for branch in [step.on_pass, step.on_fail]:
                    result.extend(branch.effects)
                    result.extend(_walk_all_effects(branch.steps))
    return result


def build_manifest_xrefs(
    manifest: "ManifestEnvelope",
    registry: "ContentRegistry",
) -> Dict[str, list]:
    """Return outbound and inbound cross-references for a manifest.

    Used by ``content show`` to list what a manifest references and what
    references it.
    """
    from oscilla.engine.models.adventure import AdventureManifest
    from oscilla.engine.models.location import LocationManifest
    from oscilla.engine.models.region import RegionManifest

    refs: list = []
    ref_by: list = []

    name = manifest.metadata.name

    match manifest:
        case RegionManifest():
            if manifest.spec.parent:
                refs.append(f"region:{manifest.spec.parent} (parent)")
            for loc in registry.locations.all():
                if loc.spec.region == name:
                    ref_by.append(f"location:{loc.metadata.name}")
        case LocationManifest():
            refs.append(f"region:{manifest.spec.region}")
            for entry in manifest.spec.adventures:
                refs.append(f"adventure:{entry.ref} (pool, weight={entry.weight})")
        case AdventureManifest():
            for step in _walk_all_steps(manifest.spec.steps):
                from oscilla.engine.models.adventure import CombatStep

                if isinstance(step, CombatStep):
                    refs.append(f"enemy:{step.enemy}")
            for effect in _walk_all_effects(manifest.spec.steps):
                from oscilla.engine.models.adventure import ItemDropEffect, SkillGrantEffect

                if isinstance(effect, ItemDropEffect):
                    if effect.loot_ref:
                        refs.append(f"loot-table:{effect.loot_ref}")
                    elif effect.loot:
                        for loot_entry in effect.loot:
                            refs.append(f"item:{loot_entry.item}")
                if isinstance(effect, SkillGrantEffect):
                    refs.append(f"skill:{effect.skill}")
            # referenced_by: find locations that include this adventure in their pool
            for loc in registry.locations.all():
                for pool_entry in loc.spec.adventures:
                    if pool_entry.ref == name:
                        ref_by.append(f"location:{loc.metadata.name}")

    return {"references": refs, "referenced_by": ref_by}
