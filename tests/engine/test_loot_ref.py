"""Tests for the enhanced loot table system.

Covers:
- LootEntry model: defaults, amount template string, requires optional
- LootGroup model: entries min_length, count defaults, template string, requires optional
- LootTableSpec: rejects empty groups, accepts valid List[LootGroup]
- EnemySpec.loot: accepts List[LootGroup]
- ItemDropEffect model_validator: exactly one of groups / loot_ref
- _resolve_loot_groups: all algorithm paths
- Integration: load LootTable fixture, run inline item_drop, enemy combat loot drops
- Load-error: unknown item refs in loot condition nodes
- Schema: loot-table kind includes groups structure
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from oscilla.engine.character import CharacterState
from oscilla.engine.loader import ContentLoadError, load_from_disk
from oscilla.engine.models.adventure import ItemDropEffect
from oscilla.engine.models.base import GrantRecord, Metadata
from oscilla.engine.models.enemy import EnemyManifest, EnemySpec
from oscilla.engine.models.loot_table import LootEntry, LootGroup, LootTableSpec
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.effects import run_effect

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"
LOOT_FIXTURE = FIXTURES / "loot-tables"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player(registry: ContentRegistry) -> CharacterState:
    """Build a fresh player from the loot-tables fixture registry."""
    assert registry.game is not None
    assert registry.character_config is not None
    return CharacterState.new_character(
        name="Tester",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )


def _make_minimal_group(item_ref: str = "test-item", count: int = 1) -> LootGroup:
    """Build a single-entry LootGroup with no conditions."""
    return LootGroup(
        count=count,
        entries=[LootEntry(item=item_ref, weight=1, amount=1)],
    )


def _make_registry_with_item(item_ref: str = "test-item") -> ContentRegistry:
    """Build a minimal registry containing one item (for condition evaluation)."""
    from oscilla.engine.models.item import ItemManifest, ItemSpec

    registry = ContentRegistry()
    item = ItemManifest(
        apiVersion="oscilla/v1",
        kind="Item",
        metadata=Metadata(name=item_ref),
        spec=ItemSpec(displayName="Test", description="x", category="material"),
    )
    registry.items.register(item)
    return registry


def _make_bare_player(item_in_inventory: str | None = None) -> CharacterState:
    """Build a CharacterState with minimal state, optionally with an item in stacks."""
    player = CharacterState(
        character_id=uuid4(),
        name="Tester",
        character_class=None,
        prestige_count=0,
        current_location=None,
    )
    if item_in_inventory:
        player.stacks[item_in_inventory] = 1
    return player


def _call_resolve(
    groups: List[LootGroup],
    player: CharacterState | None = None,
    registry: ContentRegistry | None = None,
) -> List[tuple[str, int]]:
    """Call _resolve_loot_groups with defaults suitable for unit testing."""
    from oscilla.engine.steps.effects import _resolve_loot_groups
    from oscilla.engine.templates import ExpressionContext, GameContext, PlayerContext

    if player is None:
        player = _make_bare_player()
    if registry is None:
        registry = ContentRegistry()
    ctx = ExpressionContext(
        player=PlayerContext.from_character(player),
        game=GameContext(season_hemisphere="northern", timezone=None),
    )
    return _resolve_loot_groups(groups=groups, player=player, registry=registry, ctx=ctx)


# ---------------------------------------------------------------------------
# 7.1 Unit: LootEntry model
# ---------------------------------------------------------------------------


def test_loot_entry_defaults() -> None:
    """LootEntry weight defaults to 1 and amount defaults to 1."""
    entry = LootEntry(item="sword")
    assert entry.weight == 1
    assert entry.amount == 1
    assert entry.requires is None


def test_loot_entry_accepts_template_amount() -> None:
    """LootEntry.amount accepts a Jinja2 template string."""
    entry = LootEntry(item="potion", amount="{{ player.stats['level'] }}")
    assert isinstance(entry.amount, str)


def test_loot_entry_requires_is_optional() -> None:
    """LootEntry.requires defaults to None."""
    entry = LootEntry(item="gem", weight=5, amount=3)
    assert entry.requires is None


def test_loot_entry_accepts_condition_requires() -> None:
    """LootEntry.requires accepts a valid condition dict."""
    entry = LootEntry(
        item="gem",
        requires={"type": "item", "name": "key"},  # type: ignore[arg-type]
    )
    assert entry.requires is not None


# ---------------------------------------------------------------------------
# 7.2 Unit: LootGroup model
# ---------------------------------------------------------------------------


def test_loot_group_count_defaults_to_one() -> None:
    """LootGroup.count defaults to 1."""
    group = LootGroup(entries=[LootEntry(item="sword")])
    assert group.count == 1


def test_loot_group_method_defaults_to_weighted() -> None:
    """LootGroup.method defaults to 'weighted'."""
    group = LootGroup(entries=[LootEntry(item="sword")])
    assert group.method == "weighted"


def test_loot_group_requires_is_optional() -> None:
    """LootGroup.requires defaults to None."""
    group = LootGroup(entries=[LootEntry(item="sword")])
    assert group.requires is None


def test_loot_group_accepts_template_count() -> None:
    """LootGroup.count accepts a Jinja2 template string."""
    group = LootGroup(
        count="{{ player.stats['level'] }}",
        entries=[LootEntry(item="coin")],
    )
    assert isinstance(group.count, str)


def test_loot_group_rejects_empty_entries() -> None:
    """LootGroup.entries must have at least one entry."""
    with pytest.raises(ValidationError):
        LootGroup(entries=[])


# ---------------------------------------------------------------------------
# 7.3 Unit: LootTableSpec
# ---------------------------------------------------------------------------


def test_loot_table_spec_rejects_empty_groups() -> None:
    """LootTableSpec.groups must have at least one group."""
    with pytest.raises(ValidationError):
        LootTableSpec(displayName="Empty", groups=[])


def test_loot_table_spec_accepts_valid_groups() -> None:
    """LootTableSpec.groups accepts a valid list of LootGroup."""
    spec = LootTableSpec(
        displayName="Valid Table",
        groups=[_make_minimal_group("sword")],
    )
    assert len(spec.groups) == 1
    assert spec.groups[0].entries[0].item == "sword"


def test_loot_table_spec_accepts_multiple_groups() -> None:
    """LootTableSpec.groups accepts multiple independent groups."""
    spec = LootTableSpec(
        displayName="Multi-Group",
        groups=[
            _make_minimal_group("sword"),
            _make_minimal_group("shield"),
        ],
    )
    assert len(spec.groups) == 2


# ---------------------------------------------------------------------------
# 7.4 Unit: EnemySpec.loot accepts List[LootGroup]
# ---------------------------------------------------------------------------


def test_enemy_spec_loot_accepts_list_of_groups() -> None:
    """EnemySpec.loot accepts a non-empty List[LootGroup]."""
    enemy = EnemyManifest(
        apiVersion="oscilla/v1",
        kind="Enemy",
        metadata=Metadata(name="goblin"),
        spec=EnemySpec(
            displayName="Goblin",
            hp=10,
            attack=1,
            defense=0,
            xp_reward=5,
            loot=[_make_minimal_group("gold-coin")],
        ),
    )
    assert len(enemy.spec.loot) == 1
    assert enemy.spec.loot[0].entries[0].item == "gold-coin"


def test_enemy_spec_loot_defaults_to_empty() -> None:
    """EnemySpec.loot defaults to an empty list — no loot for this enemy."""
    enemy = EnemyManifest(
        apiVersion="oscilla/v1",
        kind="Enemy",
        metadata=Metadata(name="dummy"),
        spec=EnemySpec(displayName="Dummy", hp=5, attack=0, defense=0, xp_reward=0),
    )
    assert enemy.spec.loot == []


# ---------------------------------------------------------------------------
# 7.5 Unit: ItemDropEffect model_validator
# ---------------------------------------------------------------------------


def test_item_drop_both_groups_and_loot_ref_raises() -> None:
    """Providing both groups and loot_ref must raise a ValidationError."""
    with pytest.raises(ValidationError, match="either"):
        ItemDropEffect(
            type="item_drop",
            groups=[_make_minimal_group()],
            loot_ref="some-table",
        )


def test_item_drop_neither_groups_nor_loot_ref_raises() -> None:
    """Providing neither groups nor loot_ref must raise a ValidationError."""
    with pytest.raises(ValidationError, match="either"):
        ItemDropEffect(type="item_drop")


def test_item_drop_inline_groups_is_valid() -> None:
    """ItemDropEffect with inline groups is valid."""
    effect = ItemDropEffect(type="item_drop", groups=[_make_minimal_group()])
    assert effect.groups is not None


def test_item_drop_loot_ref_only_is_valid() -> None:
    """ItemDropEffect with only loot_ref (no groups) is valid."""
    effect = ItemDropEffect(type="item_drop", loot_ref="some-table")
    assert effect.loot_ref == "some-table"
    assert effect.groups is None


def test_item_drop_empty_groups_list_raises() -> None:
    """ItemDropEffect with groups=[] raises because no inline source is provided."""
    with pytest.raises(ValidationError, match="either"):
        ItemDropEffect(type="item_drop", groups=[])


# ---------------------------------------------------------------------------
# 7.6 Unit: _resolve_loot_groups algorithm paths
# ---------------------------------------------------------------------------


def test_resolve_loot_groups_basic_drop() -> None:
    """Basic resolve: returns (item_ref, amount) tuples for drawn entries."""
    groups = [_make_minimal_group("sword", count=1)]
    results = _call_resolve(groups)
    assert results == [("sword", 1)]


def test_resolve_loot_groups_group_condition_skips_group() -> None:
    """A group whose requires condition evaluates to False is skipped entirely."""
    # Player has no milestones, so the milestone condition will fail.
    group = LootGroup(
        count=1,
        requires={"type": "milestone", "name": "rare-milestone"},  # type: ignore[arg-type]
        entries=[LootEntry(item="rare-item", weight=100)],
    )
    results = _call_resolve([group])
    assert results == []


def test_resolve_loot_groups_group_condition_passes_when_milestone_held() -> None:
    """A group whose requires condition passes yields entries."""
    player = _make_bare_player()
    player.milestones["unlocked"] = GrantRecord(tick=0, timestamp=0)
    group = LootGroup(
        count=1,
        requires={"type": "milestone", "name": "unlocked"},  # type: ignore[arg-type]
        entries=[LootEntry(item="bonus", weight=100)],
    )
    results = _call_resolve([group], player=player)
    assert results == [("bonus", 1)]


def test_resolve_loot_groups_entry_condition_filters_pool() -> None:
    """Entries whose requires condition fails are excluded from the draw pool."""
    registry = _make_registry_with_item("key-item")
    # Entry requires "key-item", which the player does not own.
    group = LootGroup(
        count=1,
        entries=[
            LootEntry(item="common", weight=100),
            LootEntry(
                item="key-gated",
                weight=100,
                requires={"type": "item", "name": "key-item"},  # type: ignore[arg-type]
            ),
        ],
    )
    # Run many iterations to confirm key-gated never appears.
    all_items: set[str] = set()
    player = _make_bare_player()
    for _ in range(50):
        results = _call_resolve([group], player=player, registry=registry)
        all_items.update(ref for ref, _ in results)
    assert "key-gated" not in all_items
    assert "common" in all_items


def test_resolve_loot_groups_entry_condition_passes_when_item_owned() -> None:
    """Entries whose requires condition passes are included in the pool."""
    registry = _make_registry_with_item("key-item")
    player = _make_bare_player(item_in_inventory="key-item")
    group = LootGroup(
        count=10,
        method="unique",
        entries=[
            LootEntry(item="common", weight=1),
            LootEntry(
                item="key-gated",
                weight=1,
                requires={"type": "item", "name": "key-item"},  # type: ignore[arg-type]
            ),
        ],
    )
    results = _call_resolve([group], player=player, registry=registry)
    items = {ref for ref, _ in results}
    # Both entries are in pool; unique k=10 clamped to pool size of 2.
    assert "common" in items
    assert "key-gated" in items


def test_resolve_loot_groups_empty_pool_is_skipped() -> None:
    """If all entries are filtered out by requires, the group is silently skipped."""
    registry = _make_registry_with_item("rare-key")
    player = _make_bare_player()  # does not own rare-key
    group = LootGroup(
        count=1,
        entries=[
            LootEntry(
                item="gated-item",
                weight=100,
                requires={"type": "item", "name": "rare-key"},  # type: ignore[arg-type]
            ),
        ],
    )
    results = _call_resolve([group], player=player, registry=registry)
    assert results == []


def test_resolve_loot_groups_method_weighted_allows_repeats() -> None:
    """method=weighted can return the same entry more than once (with replacement)."""
    group = LootGroup(
        count=30,
        method="weighted",
        entries=[LootEntry(item="coin", weight=100)],
    )
    results = _call_resolve([group])
    # All 30 draws must be "coin" since it is the only entry.
    assert len(results) == 30
    assert all(ref == "coin" for ref, _ in results)


def test_resolve_loot_groups_method_unique_no_repeats() -> None:
    """method=unique samples without replacement; each entry appears at most once."""
    group = LootGroup(
        count=3,
        method="unique",
        entries=[
            LootEntry(item="sword", weight=1),
            LootEntry(item="shield", weight=1),
            LootEntry(item="helm", weight=1),
        ],
    )
    results = _call_resolve([group])
    refs = [ref for ref, _ in results]
    assert len(refs) == len(set(refs))
    assert len(refs) == 3


def test_resolve_loot_groups_unique_count_clamped_to_pool_size() -> None:
    """method=unique with count > pool size is clamped to pool size."""
    group = LootGroup(
        count=10,
        method="unique",
        entries=[
            LootEntry(item="a", weight=1),
            LootEntry(item="b", weight=1),
        ],
    )
    results = _call_resolve([group])
    assert len(results) == 2
    refs = {ref for ref, _ in results}
    assert refs == {"a", "b"}


def test_resolve_loot_groups_integer_amount() -> None:
    """LootEntry.amount as an integer is applied correctly per draw."""
    group = LootGroup(
        count=1,
        entries=[LootEntry(item="gem", weight=100, amount=5)],
    )
    results = _call_resolve([group])
    assert results == [("gem", 5)]


def test_resolve_loot_groups_count_zero_skips_group() -> None:
    """A count of 0 results in no draws from the group."""
    group = LootGroup(
        count=0,
        entries=[LootEntry(item="missed", weight=100)],
    )
    results = _call_resolve([group])
    assert results == []


def test_resolve_loot_groups_multi_group_all_resolve() -> None:
    """Multiple groups each contribute their own drops to the result set."""
    groups = [
        LootGroup(count=1, entries=[LootEntry(item="sword", weight=100)]),
        LootGroup(count=1, entries=[LootEntry(item="potion", weight=100)]),
    ]
    results = _call_resolve(groups)
    items = {ref for ref, _ in results}
    assert items == {"sword", "potion"}


# ---------------------------------------------------------------------------
# 7.7 Integration: load LootTable fixture
# ---------------------------------------------------------------------------


def test_loot_table_fixture_loads_and_registers() -> None:
    """LootTable manifest loads and registers in the registry."""
    registry, _warnings = load_from_disk(LOOT_FIXTURE)
    tables = list(registry.loot_tables.all())
    assert len(tables) == 1
    lt = tables[0]
    assert lt.metadata.name == "test-loot-table"
    assert len(lt.spec.groups) == 2


def test_loot_table_fixture_group_structure() -> None:
    """Loaded LootTable has correct group and entry structure."""
    registry, _warnings = load_from_disk(LOOT_FIXTURE)
    lt = registry.loot_tables.require("test-loot-table", "LootTable")
    g1 = lt.spec.groups[0]
    assert g1.count == 1
    assert g1.method == "weighted"
    assert g1.entries[0].item == "test-item"
    assert g1.entries[0].amount == 1
    g2 = lt.spec.groups[1]
    assert g2.entries[0].item == "test-bonus-item"
    assert g2.entries[0].amount == 2


def test_loot_table_resolve_loot_groups() -> None:
    """registry.resolve_loot_groups returns the loot table's groups list."""
    registry, _warnings = load_from_disk(LOOT_FIXTURE)
    groups = registry.resolve_loot_groups("test-loot-table")
    assert groups is not None
    assert len(groups) == 2


def test_resolve_loot_groups_returns_none_for_unknown_ref() -> None:
    """resolve_loot_groups returns None for an unknown reference."""
    registry, _warnings = load_from_disk(LOOT_FIXTURE)
    result = registry.resolve_loot_groups("nonexistent-table")
    assert result is None


# ---------------------------------------------------------------------------
# 7.8 Integration: run inline item_drop effect end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inline_loot_groups_add_items_to_inventory() -> None:
    """item_drop with inline groups runs end-to-end and adds items to the player."""
    registry, _warnings = load_from_disk(LOOT_FIXTURE)
    player = _make_player(registry)
    tui = AsyncMock()
    effect = ItemDropEffect(
        type="item_drop",
        groups=[LootGroup(count=1, entries=[LootEntry(item="test-item", weight=100, amount=3)])],
    )

    await run_effect(effect=effect, player=player, registry=registry, tui=tui)

    assert player.stacks.get("test-item", 0) == 3


@pytest.mark.asyncio
async def test_loot_ref_resolves_and_drops_items() -> None:
    """item_drop with loot_ref resolves the named LootTable and awards items."""
    registry, _warnings = load_from_disk(LOOT_FIXTURE)
    player = _make_player(registry)
    tui = AsyncMock()
    effect = ItemDropEffect(type="item_drop", loot_ref="test-loot-table")

    await run_effect(effect=effect, player=player, registry=registry, tui=tui)

    # Both groups fire: test-item (1) and test-bonus-item (2).
    assert player.stacks.get("test-item", 0) >= 1
    assert player.stacks.get("test-bonus-item", 0) >= 2


@pytest.mark.asyncio
async def test_multi_group_drop_awards_items_from_all_groups() -> None:
    """Multiple groups in one item_drop all fire and contribute to inventory."""
    registry, _warnings = load_from_disk(LOOT_FIXTURE)
    player = _make_player(registry)
    tui = AsyncMock()
    effect = ItemDropEffect(
        type="item_drop",
        groups=[
            LootGroup(count=1, entries=[LootEntry(item="test-item", weight=100, amount=1)]),
            LootGroup(count=1, entries=[LootEntry(item="test-bonus-item", weight=100, amount=1)]),
        ],
    )

    await run_effect(effect=effect, player=player, registry=registry, tui=tui)

    assert player.stacks.get("test-item", 0) == 1
    assert player.stacks.get("test-bonus-item", 0) == 1


# ---------------------------------------------------------------------------
# 7.9 Integration: enemy with loot groups — auto-applied on combat win
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enemy_loot_groups_applied_automatically_on_combat_win() -> None:
    """Enemy.spec.loot groups are automatically resolved and applied when the enemy dies."""
    from oscilla.engine.models.adventure import CombatStep, OutcomeBranch
    from oscilla.engine.pipeline import AdventureOutcome
    from oscilla.engine.steps.combat import run_combat
    from tests.engine.conftest import MockTUI

    registry, _warnings = load_from_disk(LOOT_FIXTURE)
    player = _make_player(registry)
    # Player needs enough HP to survive; test-loot-enemy has attack=0.
    player.stats["hp"] = 20
    tui = MockTUI(menu_responses=[1, 1, 1, 1, 1, 1, 1, 1, 1, 1])  # Always choose first (attack)

    step = CombatStep(
        type="combat",
        enemy="test-loot-enemy",
        on_win=OutcomeBranch(effects=[], steps=[], goto=None),
        on_defeat=OutcomeBranch(effects=[], steps=[], goto=None),
        on_flee=OutcomeBranch(effects=[], steps=[], goto=None),
    )

    async def mock_outcome(branch: OutcomeBranch) -> AdventureOutcome:
        return AdventureOutcome.COMPLETED

    await run_combat(step=step, player=player, registry=registry, tui=tui, run_outcome_branch=mock_outcome)

    # test-loot-enemy.spec.loot: [{entries: [{item: test-item, amount: 1}]}]
    assert player.stacks.get("test-item", 0) >= 1


# ---------------------------------------------------------------------------
# 7.10 Load-error: unknown item ref in LootEntry.requires condition
# ---------------------------------------------------------------------------


def test_unknown_item_in_loot_entry_requires_raises_load_error(tmp_path: Path) -> None:
    """A LootEntry.requires condition referencing an unknown item produces a LoadError."""
    (tmp_path / "game.yaml").write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: Game
            metadata:
              name: test-game
            spec:
              displayName: Test
        """)
    )
    (tmp_path / "character_config.yaml").write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: CharacterConfig
            metadata:
              name: default
            spec:
              stats: []
        """)
    )
    (tmp_path / "bad-entry-cond.yaml").write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: Adventure
            metadata:
              name: bad-entry-cond
            spec:
              displayName: Bad Adventure
              steps:
                - type: narrative
                  text: "You search."
                  effects:
                    - type: item_drop
                      groups:
                        - count: 1
                          entries:
                            - item: some-item
                              weight: 100
                              requires:
                                type: item
                                name: ghost-item-does-not-exist
        """)
    )

    with pytest.raises(ContentLoadError) as exc_info:
        load_from_disk(tmp_path)

    messages = [e.message for e in exc_info.value.errors]
    assert any("ghost-item-does-not-exist" in m for m in messages)


# ---------------------------------------------------------------------------
# 7.11 Load-error: unknown item ref in LootGroup.requires (item condition)
# ---------------------------------------------------------------------------


def test_unknown_item_in_loot_group_requires_raises_load_error(tmp_path: Path) -> None:
    """A LootGroup.requires with an unknown item ref in an item condition produces a LoadError."""
    (tmp_path / "game.yaml").write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: Game
            metadata:
              name: test-game
            spec:
              displayName: Test
        """)
    )
    (tmp_path / "character_config.yaml").write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: CharacterConfig
            metadata:
              name: default
            spec:
              stats: []
        """)
    )
    (tmp_path / "bad-group-cond.yaml").write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: LootTable
            metadata:
              name: bad-group-cond-table
            spec:
              displayName: Bad Table
              groups:
                - count: 1
                  requires:
                    type: item
                    name: phantom-item-does-not-exist
                  entries:
                    - item: any-item
                      weight: 100
        """)
    )

    with pytest.raises(ContentLoadError) as exc_info:
        load_from_disk(tmp_path)

    messages = [e.message for e in exc_info.value.errors]
    assert any("phantom-item-does-not-exist" in m for m in messages)


def test_unknown_loot_ref_raises_load_error(tmp_path: Path) -> None:
    """An item_drop with a loot_ref that does not resolve produces a LoadError."""
    (tmp_path / "game.yaml").write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: Game
            metadata:
              name: test-game
            spec:
              displayName: Test
        """)
    )
    (tmp_path / "character_config.yaml").write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: CharacterConfig
            metadata:
              name: default
            spec:
              stats: []
        """)
    )
    (tmp_path / "bad-loot-ref.yaml").write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: Adventure
            metadata:
              name: bad-loot-ref
            spec:
              displayName: Bad Adventure
              steps:
                - type: narrative
                  text: "You search the area."
                  effects:
                    - type: item_drop
                      loot_ref: nonexistent-table
        """)
    )

    with pytest.raises(ContentLoadError) as exc_info:
        load_from_disk(tmp_path)

    messages = [e.message for e in exc_info.value.errors]
    assert any("nonexistent-table" in m for m in messages)


# ---------------------------------------------------------------------------
# 7.12 Schema: loot-table kind includes groups structure
# ---------------------------------------------------------------------------


def test_loot_table_schema_includes_groups() -> None:
    """The exported loot-table JSON schema includes the 'groups' field."""
    from oscilla.engine.schema_export import export_schema

    schema = export_schema("loot-table")
    schema_str = str(schema)
    assert "groups" in schema_str


def test_loot_table_schema_includes_loot_group() -> None:
    """The exported loot-table JSON schema references LootGroup."""
    from oscilla.engine.schema_export import export_schema

    schema = export_schema("loot-table")
    schema_str = str(schema)
    assert "LootGroup" in schema_str


def test_loot_table_schema_includes_entries() -> None:
    """The exported loot-table JSON schema includes the 'entries' field."""
    from oscilla.engine.schema_export import export_schema

    schema = export_schema("loot-table")
    schema_str = str(schema)
    assert "entries" in schema_str


def test_loot_table_schema_includes_method() -> None:
    """The exported loot-table JSON schema includes the 'method' field."""
    from oscilla.engine.schema_export import export_schema

    schema = export_schema("loot-table")
    schema_str = str(schema)
    assert "method" in schema_str
