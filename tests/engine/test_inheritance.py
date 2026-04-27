"""Unit tests for manifest inheritance: merge, topo-sort, resolve, and loader integration."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import pytest

from oscilla.engine.loader import (
    _merge_spec_dicts,
    _RawManifest,
    _topo_sort_inheritance,
    load_from_disk,
    load_from_text,
    parse,
)

# ---------------------------------------------------------------------------
# _merge_spec_dicts tests
# ---------------------------------------------------------------------------


class TestMergeSpecDicts:
    """Test _merge_spec_dicts() merge semantics."""

    def test_replace_semantics(self) -> None:
        """Child field replaces base field."""
        base = {"displayName": "Base", "value": 10}
        child = {"displayName": "Child"}
        result = _merge_spec_dicts(base, child)
        assert result == {"displayName": "Child", "value": 10}

    def test_plus_list_extend(self) -> None:
        """Keys ending with '+' extend base lists."""
        base = {"skills": ["a", "b"]}
        child = {"skills+": ["c", "d"]}
        result = _merge_spec_dicts(base, child)
        assert result == {"skills": ["a", "b", "c", "d"]}

    def test_plus_dict_recursive_merge(self) -> None:
        """Keys ending with '+' recursively merge dicts including nested '+' keys."""
        base = {
            "equip": {
                "stat_modifiers": [{"stat": "hp", "amount": 1}],
                "slots": ["head"],
            }
        }
        child = {"equip+": {"stat_modifiers+": [{"stat": "str", "amount": 2}]}}
        result = _merge_spec_dicts(base, child)
        assert result == {
            "equip": {
                "stat_modifiers": [
                    {"stat": "hp", "amount": 1},
                    {"stat": "str", "amount": 2},
                ],
                "slots": ["head"],
            }
        }

    def test_plus_type_mismatch_falls_back_to_child(self) -> None:
        """If child '+' value type doesn't match base, child wins."""
        base = {"skills": ["a"]}
        child = {"skills+": {"not": "a list"}}
        result = _merge_spec_dicts(base, child)
        assert result == {"skills": {"not": "a list"}}

    def test_plus_with_no_base_value(self) -> None:
        """If '+' key has no corresponding base value, child value is used as-is."""
        base = {"other": "value"}
        child = {"skills+": ["a", "b"]}
        result = _merge_spec_dicts(base, child)
        assert result == {"other": "value", "skills": ["a", "b"]}

    def test_properties_plus_extend(self) -> None:
        """properties+: extends the base properties dict."""
        base = {"properties": {"damage_die": 4}}
        child = {"properties+": {"label": "sharp"}}
        result = _merge_spec_dicts(base, child)
        assert result == {"properties": {"damage_die": 4, "label": "sharp"}}

    def test_child_overrides_base_properties(self) -> None:
        """Without '+', child properties replaces base properties entirely."""
        base = {"properties": {"damage_die": 4}}
        child = {"properties": {"damage_die": 6}}
        result = _merge_spec_dicts(base, child)
        assert result == {"properties": {"damage_die": 6}}


# ---------------------------------------------------------------------------
# _topo_sort_inheritance tests
# ---------------------------------------------------------------------------


class TestTopoSortInheritance:
    """Test _topo_sort_inheritance() ordering and error detection."""

    def _raw(self, kind: str, name: str, base: str | None) -> _RawManifest:
        return _RawManifest(
            kind=kind,
            name=name,
            abstract=False,
            base=base,
            raw={"spec": {}},
            source=Path(f"<{name}>"),
        )

    def test_correct_ordering(self) -> None:
        """Grandchild is resolved after child, child after base."""
        deferred = [
            self._raw("Enemy", "goblin-king", "goblin-chief"),
            self._raw("Enemy", "goblin-chief", "goblin-base"),
        ]
        abstract_raws: Dict[Tuple[str, str], Dict[str, object]] = {("Enemy", "goblin-base"): {}}
        concrete_raws: Dict[Tuple[str, str], Dict[str, object]] = {}

        order, errors = _topo_sort_inheritance(deferred, abstract_raws, concrete_raws)
        assert not errors
        assert len(order) == 2
        assert order[0].name == "goblin-chief"
        assert order[1].name == "goblin-king"

    def test_circular_chain_error(self) -> None:
        """Two-manifest cycle is detected."""
        deferred = [
            self._raw("Enemy", "a", "b"),
            self._raw("Enemy", "b", "a"),
        ]
        _, errors = _topo_sort_inheritance(deferred, {}, {})
        assert len(errors) == 1
        assert "circular inheritance" in errors[0].message
        assert "a" in errors[0].message

    def test_missing_base_ref_error(self) -> None:
        """Unknown base name produces a hard error."""
        deferred = [self._raw("Enemy", "child", "nonexistent")]
        _, errors = _topo_sort_inheritance(deferred, {}, {})
        assert len(errors) == 1
        assert "nonexistent" in errors[0].message

    def test_kind_mismatch_error(self) -> None:
        """Base exists but under a different kind produces a precise error."""
        deferred = [self._raw("Enemy", "child", "iron-sword")]
        concrete_raws = {("Item", "iron-sword"): {}}
        _, errors = _topo_sort_inheritance(deferred, {}, concrete_raws)
        assert len(errors) == 1
        assert "kind mismatch" in errors[0].message


# ---------------------------------------------------------------------------
# load_from_text integration tests
# ---------------------------------------------------------------------------


class TestLoadFromTextInheritance:
    """Integration tests for inheritance via load_from_text()."""

    def test_single_level_inheritance(self) -> None:
        """Child inherits missing required fields from concrete base."""
        yaml_text = """\
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-base
spec:
  displayName: Goblin
  stats:
    hp: 10
    strength: 3
---
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-scout
  base: goblin-base
spec:
  displayName: Goblin Scout
  stats:
    hp: 8
---
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test
spec:
  public_stats:
    - name: hp
      type: int
    - name: strength
      type: int
---
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test
spec:
  displayName: Test
  outcomes: []
  triggers: {}
"""
        registry, warnings = load_from_text(yaml_text)
        assert "goblin-scout" in {e.metadata.name for e in registry.enemies.all()}
        scout = registry.enemies.get("goblin-scout")
        assert scout is not None
        assert scout.spec.displayName == "Goblin Scout"
        assert scout.spec.stats["hp"] == 8
        # Child's stats dict replaces base's entirely (no '+' used)
        assert "strength" not in scout.spec.stats

    def test_chained_inheritance_depth_3(self) -> None:
        """Three-level chain: grandchild inherits from child which inherits from base."""
        yaml_text = """\
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-base
spec:
  displayName: Goblin
  stats:
    hp: 10
    strength: 3
---
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-chief
  base: goblin-base
spec:
  displayName: Goblin Chief
  stats:
    hp: 20
---
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-king
  base: goblin-chief
spec:
  displayName: Goblin King
  stats:
    hp: 30
---
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test
spec:
  public_stats:
    - name: hp
      type: int
    - name: strength
      type: int
---
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test
spec:
  displayName: Test
  outcomes: []
  triggers: {}
"""
        registry, warnings = load_from_text(yaml_text)
        king = registry.enemies.get("goblin-king")
        assert king is not None
        assert king.spec.displayName == "Goblin King"
        assert king.spec.stats["hp"] == 30
        # Each child's stats dict replaces its parent's entirely
        assert "strength" not in king.spec.stats

    def test_abstract_base_with_concrete_child(self) -> None:
        """Abstract base is not registered; child inherits from it."""
        yaml_text = """\
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-base
  abstract: true
spec:
  displayName: Goblin
  stats:
    hp: 10
    strength: 3
---
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-scout
  base: goblin-base
spec:
  displayName: Goblin Scout
---
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test
spec:
  public_stats:
    - name: hp
      type: int
    - name: strength
      type: int
---
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test
spec:
  displayName: Test
  outcomes: []
  triggers: {}
"""
        registry, warnings = load_from_text(yaml_text)
        # Abstract base should NOT be in the registry
        assert registry.enemies.get("goblin-base") is None
        # Child should be registered with inherited fields
        scout = registry.enemies.get("goblin-scout")
        assert scout is not None
        assert scout.spec.displayName == "Goblin Scout"
        # Abstract base provides all stats; child doesn't override stats
        assert scout.spec.stats["hp"] == 10
        assert scout.spec.stats["strength"] == 3

    def test_concrete_base_with_child(self) -> None:
        """Concrete base is both registered and available as a base."""
        yaml_text = """\
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: base-enemy
spec:
  displayName: Base Enemy
  stats:
    hp: 10
    strength: 3
---
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: derived-enemy
  base: base-enemy
spec:
  displayName: Derived Enemy
---
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test
spec:
  public_stats:
    - name: hp
      type: int
    - name: strength
      type: int
---
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test
spec:
  displayName: Test
  outcomes: []
  triggers: {}
"""
        registry, warnings = load_from_text(yaml_text)
        base = registry.enemies.get("base-enemy")
        assert base is not None
        derived = registry.enemies.get("derived-enemy")
        assert derived is not None
        assert derived.spec.displayName == "Derived Enemy"
        # Base provides all stats; child doesn't override stats
        assert derived.spec.stats["hp"] == 10
        assert derived.spec.stats["strength"] == 3

    def test_missing_base_ref_is_hard_error(self) -> None:
        """Missing base reference raises ContentLoadError."""
        yaml_text = """\
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: child
  base: nonexistent
spec:
  displayName: Child
  stats:
    hp: 10
    strength: 3
---
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test
spec:
  public_stats:
    - name: hp
      type: int
    - name: strength
      type: int
---
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test
spec:
  displayName: Test
  outcomes: []
  triggers: {}
"""
        from oscilla.engine.loader import ContentLoadError

        with pytest.raises(ContentLoadError):
            load_from_text(yaml_text)

    def test_circular_chain_is_hard_error(self) -> None:
        """Circular inheritance raises ContentLoadError."""
        yaml_text = """\
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: a
  base: b
spec:
  displayName: A
  stats:
    hp: 10
    strength: 3
---
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: b
  base: a
spec:
  displayName: B
  stats:
    hp: 10
    strength: 3
---
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test
spec:
  public_stats:
    - name: hp
      type: int
    - name: strength
      type: int
---
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test
spec:
  displayName: Test
  outcomes: []
  triggers: {}
"""
        from oscilla.engine.loader import ContentLoadError

        with pytest.raises(ContentLoadError):
            load_from_text(yaml_text)

    def test_plus_extend_on_list_field(self) -> None:
        """Child can use '+' to extend list fields from base."""
        yaml_text = """\
apiVersion: oscilla/v1
kind: Item
metadata:
  name: base-sword
spec:
  displayName: Base Sword
  category: weapon
  grants_skills_equipped:
    - basic-slash
---
apiVersion: oscilla/v1
kind: Item
metadata:
  name: silver-sword
  base: base-sword
spec:
  displayName: Silver Sword
  grants_skills_equipped+:
    - silver-strike
---
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: basic-slash
spec:
  displayName: Slash
  contexts:
    - combat
---
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: silver-strike
spec:
  displayName: Silver Strike
  contexts:
    - combat
---
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test
spec:
  displayName: Test
  outcomes: []
  triggers: {}
"""
        registry, warnings = load_from_text(yaml_text)
        sword = registry.items.get("silver-sword")
        assert sword is not None
        assert sword.spec.grants_skills_equipped == ["basic-slash", "silver-strike"]


# ---------------------------------------------------------------------------
# Template context — `this` variable tests
# ---------------------------------------------------------------------------


class TestThisInRenderFormula:
    """Test `this` in render_formula() with CombatFormulaContext (6.1)."""

    def test_this_in_render_formula_basic(self) -> None:
        """this.get('damage_die') works in render_formula()."""
        from oscilla.engine.templates import CombatFormulaContext, render_formula

        ctx = CombatFormulaContext(
            player={"strength": 10},
            enemy_stats={"hp": 50},
            combat_stats={},
            turn_number=1,
            this={"damage_die": 8},
        )
        result = render_formula("{{ this.get('damage_die', 4) }}", ctx)
        assert result == 8

    def test_this_in_render_formula_with_player_stat(self) -> None:
        """this combined with player stats in formula."""
        from oscilla.engine.templates import CombatFormulaContext, render_formula

        ctx = CombatFormulaContext(
            player={"strength": 5},
            enemy_stats={"hp": 50},
            combat_stats={},
            turn_number=1,
            this={"damage_die": 6},
        )
        result = render_formula("{{ this.get('damage_die', 4) * player['strength'] }}", ctx)
        assert result == 30

    def test_this_in_render_formula_empty_default(self) -> None:
        """this defaults to empty dict when not provided."""
        from oscilla.engine.templates import CombatFormulaContext, render_formula

        ctx = CombatFormulaContext(
            player={"strength": 10},
            enemy_stats={"hp": 50},
            combat_stats={},
            turn_number=1,
        )
        result = render_formula("{{ this.get('damage_die', 4) }}", ctx)
        assert result == 4


# ---------------------------------------------------------------------------
# Integration tests — full pipeline
# ---------------------------------------------------------------------------


class TestLoadFromDiskInheritance:
    """Test full load_from_disk() with inherited manifests (7.1)."""

    def test_load_from_disk_with_inherited_enemies(self, tmp_path: Path) -> None:
        """load_from_disk loads inherited enemy manifests from disk."""
        # Write base enemy
        (tmp_path / "base.yaml").write_text(
            "apiVersion: oscilla/v1\n"
            "kind: Enemy\n"
            "metadata:\n"
            "  name: goblin-base\n"
            "spec:\n"
            "  displayName: Goblin\n"
            "  stats:\n"
            "    hp: 10\n"
            "    strength: 3\n",
            encoding="utf-8",
        )
        # Write child enemy
        (tmp_path / "child.yaml").write_text(
            "apiVersion: oscilla/v1\n"
            "kind: Enemy\n"
            "metadata:\n"
            "  name: goblin-scout\n"
            "  base: goblin-base\n"
            "spec:\n"
            "  displayName: Goblin Scout\n"
            "  stats:\n"
            "    hp: 8\n",
            encoding="utf-8",
        )
        # Write required game manifests
        (tmp_path / "game.yaml").write_text(
            "apiVersion: oscilla/v1\n"
            "kind: Game\n"
            "metadata:\n"
            "  name: test\n"
            "spec:\n"
            "  displayName: Test\n"
            "  outcomes: []\n"
            "  triggers: {}\n",
            encoding="utf-8",
        )
        (tmp_path / "charconfig.yaml").write_text(
            "apiVersion: oscilla/v1\n"
            "kind: CharacterConfig\n"
            "metadata:\n"
            "  name: test\n"
            "spec:\n"
            "  public_stats:\n"
            "    - name: hp\n"
            "      type: int\n"
            "    - name: strength\n"
            "      type: int\n",
            encoding="utf-8",
        )

        registry, warnings = load_from_disk(tmp_path)
        scout = registry.enemies.get("goblin-scout")
        assert scout is not None
        assert scout.spec.displayName == "Goblin Scout"
        assert scout.spec.stats["hp"] == 8
        # Base is also registered (it's concrete, not abstract)
        base = registry.enemies.get("goblin-base")
        assert base is not None
        assert base.spec.displayName == "Goblin"


class TestParseReturnType:
    """Test parse() return type change doesn't break existing callers (7.2)."""

    def test_parse_returns_3_tuple(self, tmp_path: Path) -> None:
        """parse() returns (manifests, errors, warnings) 3-tuple."""
        (tmp_path / "game.yaml").write_text(
            "apiVersion: oscilla/v1\n"
            "kind: Game\n"
            "metadata:\n"
            "  name: test\n"
            "spec:\n"
            "  displayName: Test\n"
            "  outcomes: []\n"
            "  triggers: {}\n",
            encoding="utf-8",
        )
        (tmp_path / "charconfig.yaml").write_text(
            "apiVersion: oscilla/v1\n"
            "kind: CharacterConfig\n"
            "metadata:\n"
            "  name: test\n"
            "spec:\n"
            "  public_stats:\n"
            "    - name: hp\n"
            "      type: int\n",
            encoding="utf-8",
        )
        result = parse([tmp_path / "game.yaml", tmp_path / "charconfig.yaml"])
        assert isinstance(result, tuple)
        assert len(result) == 3
        manifests, errors, warnings = result
        assert isinstance(manifests, list)
        assert isinstance(errors, list)
        assert isinstance(warnings, list)
        assert len(manifests) == 2
        assert len(errors) == 0


class TestLoadFromTextMultiDoc:
    """Test load_from_text() multi-document YAML with inheritance (7.3)."""

    def test_multi_doc_with_inheritance_and_error(self) -> None:
        """Multi-doc YAML with inheritance properly labels errors by document."""
        yaml_text = (
            "apiVersion: oscilla/v1\n"
            "kind: Enemy\n"
            "metadata:\n"
            "  name: goblin-base\n"
            "spec:\n"
            "  displayName: Goblin\n"
            "  stats:\n"
            "    hp: 10\n"
            "    strength: 3\n"
            "---\n"
            "apiVersion: oscilla/v1\n"
            "kind: Enemy\n"
            "metadata:\n"
            "  name: goblin-scout\n"
            "  base: nonexistent-base\n"
            "spec:\n"
            "  displayName: Goblin Scout\n"
            "  stats:\n"
            "    hp: 8\n"
            "---\n"
            "apiVersion: oscilla/v1\n"
            "kind: CharacterConfig\n"
            "metadata:\n"
            "  name: test\n"
            "spec:\n"
            "  public_stats:\n"
            "    - name: hp\n"
            "      type: int\n"
            "    - name: strength\n"
            "      type: int\n"
            "---\n"
            "apiVersion: oscilla/v1\n"
            "kind: Game\n"
            "metadata:\n"
            "  name: test\n"
            "spec:\n"
            "  displayName: Test\n"
            "  outcomes: []\n"
            "  triggers: {}\n"
        )
        from oscilla.engine.loader import ContentLoadError

        with pytest.raises(ContentLoadError) as exc_info:
            load_from_text(yaml_text)
        # Error should reference the missing base
        assert "nonexistent-base" in str(exc_info.value)


class TestSchemaExportInheritance:
    """Test JSON Schema export includes + fields and abstract arm (7.4)."""

    def test_union_schema_has_abstract_arm(self) -> None:
        """Union schema includes a permissive arm for abstract manifests."""
        from oscilla.engine.schema_export import export_union_schema

        schema = export_union_schema()
        then_body = schema.get("then", schema)
        one_of = then_body.get("oneOf", [])
        # The first arm should be the abstract permissive arm
        assert len(one_of) > 0
        abstract_arm = one_of[0]
        # Check it has the abstract: true constraint
        props = abstract_arm.get("properties", {})
        metadata_props = props.get("metadata", {})
        assert metadata_props.get("properties", {}).get("abstract", {}).get("const") is True

    def test_union_schema_has_plus_fields_in_enemy(self) -> None:
        """Union schema $defs includes '+' sibling fields for EnemySpec."""
        from oscilla.engine.schema_export import export_union_schema

        schema = export_union_schema()
        defs = schema.get("$defs", {})
        enemy_spec = defs.get("EnemySpec", {})
        props = enemy_spec.get("properties", {})
        # skills is an array field, so skills+ should be present
        assert "skills+" in props, f"skills+ not found in EnemySpec properties: {list(props.keys())}"
        # loot is an array field, so loot+ should be present
        assert "loot+" in props, f"loot+ not found in EnemySpec properties: {list(props.keys())}"

    def test_union_schema_has_plus_fields_in_item(self) -> None:
        """Union schema $defs includes '+' sibling fields for ItemSpec."""
        from oscilla.engine.schema_export import export_union_schema

        schema = export_union_schema()
        defs = schema.get("$defs", {})
        item_spec = defs.get("ItemSpec", {})
        props = item_spec.get("properties", {})
        # grants_skills_equipped is a list field, so grants_skills_equipped+ should be present
        assert "grants_skills_equipped+" in props, (
            f"grants_skills_equipped+ not found in ItemSpec properties: {list(props.keys())}"
        )
