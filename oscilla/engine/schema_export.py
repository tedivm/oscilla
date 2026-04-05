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


def valid_kinds() -> list[str]:
    return sorted(_MANIFEST_MODELS)
