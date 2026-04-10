"""Tests for ArchetypeSpec and ArchetypeManifest model construction (task 8.1)."""

from __future__ import annotations

import pytest

from oscilla.engine.models.adventure import StatChangeEffect
from oscilla.engine.models.archetype import ArchetypeManifest, ArchetypeSpec
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.game import PassiveEffect


def _make_archetype(name: str = "test-archetype", **spec_kwargs: object) -> ArchetypeManifest:
    return ArchetypeManifest(
        apiVersion="oscilla/v1",
        kind="Archetype",
        metadata=Metadata(name=name),
        spec=ArchetypeSpec(displayName="Test Archetype", **spec_kwargs),
    )


def test_archetype_manifest_minimal_construction() -> None:
    """displayName is required; all other fields should default cleanly."""
    m = _make_archetype()
    assert m.kind == "Archetype"
    assert m.spec.displayName == "Test Archetype"
    assert m.spec.description == ""
    assert m.spec.gain_effects == []
    assert m.spec.lose_effects == []
    assert m.spec.passive_effects == []


def test_archetype_spec_displayname_required() -> None:
    with pytest.raises(Exception):
        ArchetypeSpec()  # type: ignore[call-arg]


def test_archetype_spec_with_gain_effects() -> None:
    gain = StatChangeEffect(type="stat_change", stat="strength", amount=5)
    spec = ArchetypeSpec(displayName="Warrior", gain_effects=[gain])
    assert len(spec.gain_effects) == 1
    assert spec.gain_effects[0] == gain


def test_archetype_spec_with_lose_effects() -> None:
    lose = StatChangeEffect(type="stat_change", stat="strength", amount=-5)
    spec = ArchetypeSpec(displayName="Former Warrior", lose_effects=[lose])
    assert len(spec.lose_effects) == 1


def test_archetype_spec_with_passive_effects() -> None:
    passive = PassiveEffect(stat_modifiers=[], skill_grants=["sword-mastery"])
    spec = ArchetypeSpec(displayName="Knight", passive_effects=[passive])
    assert len(spec.passive_effects) == 1
    assert spec.passive_effects[0].skill_grants == ["sword-mastery"]


def test_archetype_manifest_from_dict() -> None:
    """Validate round-trip through model_validate from a dict."""
    data = {
        "apiVersion": "oscilla/v1",
        "kind": "Archetype",
        "metadata": {"name": "mage"},
        "spec": {
            "displayName": "Mage",
            "description": "A wielder of arcane power.",
        },
    }
    m = ArchetypeManifest.model_validate(data)
    assert m.metadata.name == "mage"
    assert m.spec.displayName == "Mage"
    assert m.spec.description == "A wielder of arcane power."
