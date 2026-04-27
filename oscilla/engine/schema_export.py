"""Export JSON Schema for Oscilla manifest kinds.

Pydantic v2's model_json_schema() generates a JSON Schema (draft 7/2020-12)
from the model's field definitions, validators, and annotations. The output
can be used with yaml-language-server directives, VS Code settings.json,
or any JSON Schema-aware editor.

Usage example (yaml-language-server directive in a YAML file):
    # yaml-language-server: $schema=./schemas/adventure.json
"""

from __future__ import annotations

from typing import Any, Dict

from oscilla.engine.kinds import ALL_KINDS

# Maps CLI kind slug → manifest model class.
# Derived from ALL_KINDS registry — add new kinds there, not here.
_MANIFEST_MODELS: Dict[str, Any] = {k.slug: k.model_class for k in ALL_KINDS}


def export_schema(kind: str) -> Dict[str, Any]:
    """Return the JSON Schema dict for one manifest kind.

    Raises ValueError for unknown kind slugs.
    """
    kind_normalized = kind.lower()
    model = _MANIFEST_MODELS.get(kind_normalized)
    if model is None:
        raise ValueError(f"Unknown kind {kind!r}. Valid: {', '.join(sorted(_MANIFEST_MODELS))}")
    schema: Dict[str, Any] = dict(model.model_json_schema())
    # Annotate the schema with a standard $id and $schema header for editor tooling.
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://oscilla.dev/schemas/{kind_normalized}.json"
    schema["title"] = f"Oscilla {kind_normalized.title()} Manifest"
    return schema


def export_all_schemas() -> Dict[str, Dict[str, Any]]:
    """Return a dict of kind → JSON Schema for all manifest kinds."""
    return {kind: export_schema(kind) for kind in _MANIFEST_MODELS}


def export_union_schema() -> Dict[str, Any]:
    """Return a JSON Schema that accepts any valid Oscilla manifest.

    The schema is a 'kind'-discriminated oneOf union of all registered manifest
    kind models wrapped in an if/then guard on apiVersion: oscilla/v1. The guard
    makes the schema a no-op for non-Oscilla YAML files, enabling the **/*.yaml
    project-wide glob without generating spurious validation errors in files that
    don't belong to Oscilla.

    The yaml-language-server uses the kind discriminator to narrow validation to
    the correct model branch while the author is editing.
    """
    from typing import Annotated, Union

    from pydantic import Field, RootModel

    from oscilla.engine.models.adventure import AdventureManifest
    from oscilla.engine.models.archetype import ArchetypeManifest
    from oscilla.engine.models.buff import BuffManifest
    from oscilla.engine.models.character_config import CharacterConfigManifest
    from oscilla.engine.models.enemy import EnemyManifest
    from oscilla.engine.models.game import GameManifest
    from oscilla.engine.models.item import ItemManifest
    from oscilla.engine.models.location import LocationManifest
    from oscilla.engine.models.loot_table import LootTableManifest
    from oscilla.engine.models.quest import QuestManifest
    from oscilla.engine.models.recipe import RecipeManifest
    from oscilla.engine.models.region import RegionManifest
    from oscilla.engine.models.skill import SkillManifest

    # The discriminator field is 'kind'; every manifest model uses Literal["<KindName>"]
    # for its kind field, so Pydantic can generate a proper discriminated oneOf.
    AnyManifest = RootModel[
        Annotated[
            Union[
                AdventureManifest,
                ArchetypeManifest,
                BuffManifest,
                CharacterConfigManifest,
                EnemyManifest,
                GameManifest,
                ItemManifest,
                LocationManifest,
                LootTableManifest,
                QuestManifest,
                RecipeManifest,
                RegionManifest,
                SkillManifest,
            ],
            Field(discriminator="kind"),
        ]
    ]

    inner_schema: Dict[str, Any] = dict(AnyManifest.model_json_schema())

    # Post-process: inject '+' sibling fields for list/dict properties in each spec def.
    _inject_plus_fields(inner_schema)

    # Wrap in if/then so the schema is a no-op for files that lack apiVersion: oscilla/v1.
    # $defs must stay at the top level so $ref paths resolve correctly.
    then_body = {k: v for k, v in inner_schema.items() if k != "$defs"}

    # Add abstract permissive arm: when metadata.abstract is true, allow any spec content.
    # This is prepended to the oneOf so it takes priority for abstract manifests.
    if "oneOf" in then_body:
        abstract_arm: Dict[str, Any] = {
            "properties": {
                "metadata": {
                    "properties": {"abstract": {"const": True}},
                    "required": ["abstract"],
                }
            },
            "required": ["metadata"],
            "additionalProperties": True,
        }
        then_body["oneOf"].insert(0, abstract_arm)

    schema: Dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://oscilla.tedivm.com/schemas/manifest.json",
        "title": "Oscilla Manifest",
        "if": {
            "properties": {"apiVersion": {"const": "oscilla/v1"}},
            "required": ["apiVersion"],
        },
        "then": then_body,
    }
    if "$defs" in inner_schema:
        schema["$defs"] = inner_schema["$defs"]
    return schema


def _inject_plus_fields(schema: Dict[str, Any]) -> None:
    """Walk $defs and inject '<field>+' sibling properties for list/dict fields.

    For every property in a spec model whose type is 'array' or '$ref' to an object,
    inject a sibling '<fieldname>+' property with the same type and a description note
    about extending inherited values.
    """
    defs = schema.get("$defs", {})
    for def_name, def_schema in defs.items():
        props = def_schema.get("properties", {})
        if not isinstance(props, dict):
            continue
        to_add: Dict[str, Any] = {}
        for prop_name, prop_schema in list(props.items()):
            if not isinstance(prop_schema, dict):
                continue
            prop_type = prop_schema.get("type")
            ref = prop_schema.get("$ref")
            # Inject '+' for arrays and objects (refs to other defs are objects).
            if prop_type == "array" or ref is not None:
                plus_name = f"{prop_name}+"
                desc = prop_schema.get("description", "")
                plus_schema = dict(prop_schema)
                plus_schema["description"] = (
                    f"{desc} (extends the inherited list/dict rather than replacing it)".strip()
                )
                to_add[plus_name] = plus_schema
        if to_add:
            props.update(to_add)


def valid_kinds() -> list[str]:
    return sorted(_MANIFEST_MODELS)
