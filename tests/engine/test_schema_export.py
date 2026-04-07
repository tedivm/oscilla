"""Tests for schema_export.py — JSON schema generation from manifest models."""

from __future__ import annotations

import pytest

from oscilla.engine.kinds import ALL_KINDS
from oscilla.engine.schema_export import export_all_schemas, export_schema, valid_kinds


def test_export_schema_returns_dict_for_each_kind() -> None:
    for kind_obj in ALL_KINDS:
        result = export_schema(kind_obj.slug)
        assert isinstance(result, dict)


def test_export_schema_raises_for_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown kind"):
        export_schema("not-a-real-kind")


def test_export_all_schemas_returns_all_kinds() -> None:
    all_schemas = export_all_schemas()
    expected = {k.slug for k in ALL_KINDS}
    assert set(all_schemas.keys()) == expected


def test_schema_has_required_headers() -> None:
    schema = export_schema("adventure")
    assert "$schema" in schema
    assert "$id" in schema
    assert "title" in schema


def test_schema_dollar_schema_is_json_schema_uri() -> None:
    schema = export_schema("adventure")
    assert "json-schema.org" in schema["$schema"]


def test_schema_dollar_id_contains_kind_name() -> None:
    schema = export_schema("adventure")
    assert "adventure" in schema["$id"]


def test_schema_title_is_string() -> None:
    schema = export_schema("region")
    assert isinstance(schema["title"], str)


def test_valid_kinds_returns_list() -> None:
    kinds = valid_kinds()
    assert isinstance(kinds, list)
    assert len(kinds) > 0


def test_valid_kinds_contains_adventure() -> None:
    kinds = valid_kinds()
    assert "adventure" in kinds


def test_valid_kinds_contains_region() -> None:
    kinds = valid_kinds()
    assert "region" in kinds


def test_export_schema_case_insensitive() -> None:
    """Kind slug lookup should be case-insensitive."""
    lower = export_schema("region")
    upper = export_schema("REGION")
    assert lower["$id"] == upper["$id"]


# ---------------------------------------------------------------------------
# Union schema tests
# ---------------------------------------------------------------------------


def test_export_union_schema_structure() -> None:
    """Union schema has the required JSON Schema metadata, title, and oneOf or anyOf."""
    from oscilla.engine.schema_export import export_union_schema

    schema = export_union_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema.get("title") == "Oscilla Manifest"
    # Pydantic may emit either oneOf or anyOf for a discriminated union; accept both.
    then_body = schema.get("then", schema)
    assert "oneOf" in then_body or "anyOf" in then_body


def test_export_union_schema_all_kinds_present() -> None:
    """Every registered kind appears somewhere in the union schema."""
    from oscilla.engine.schema_export import export_union_schema

    schema = export_union_schema()
    schema_str = str(schema).lower()
    for kind_slug in valid_kinds():
        # Slug may use hyphens (e.g., 'character-config') while the schema stores
        # the TitleCase kind name ('CharacterConfig'). Check both forms.
        normalized = kind_slug.replace("-", "")
        assert kind_slug in schema_str or normalized in schema_str, f"Kind {kind_slug!r} not found in union schema"


def test_export_schema_adventure_has_properties() -> None:
    schema = export_schema("adventure")
    # The schema should have 'properties' or '$defs' at minimum
    assert "properties" in schema or "$defs" in schema
