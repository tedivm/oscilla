"""Archetype manifest — persistent character archetypes granted and revoked via effects."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal


from oscilla.engine.models.base import BaseSpec, ManifestEnvelope

if TYPE_CHECKING:
    from oscilla.engine.models.adventure import Effect
    from oscilla.engine.models.game import PassiveEffect


class ArchetypeSpec(BaseSpec):
    """Spec block for an Archetype manifest.

    Archetypes are named persistent states held in CharacterState.archetypes.
    When added, gain_effects fire once; when removed, lose_effects fire once.
    passive_effects are re-evaluated every tick while the archetype is held.
    """

    displayName: str
    description: str = ""
    # Effects that fire once when the archetype is first granted.
    gain_effects: List["Effect"] = []
    # Effects that fire once when the archetype is removed.
    lose_effects: List["Effect"] = []
    # Continuous passive stat/skill grants while the archetype is held.
    passive_effects: List["PassiveEffect"] = []


class ArchetypeManifest(ManifestEnvelope):
    kind: Literal["Archetype"]
    spec: ArchetypeSpec


# ArchetypeSpec.gain_effects / lose_effects reference Effect from adventure.py,
# and passive_effects references PassiveEffect from game.py.  Both are defined
# after this module, so we rebuild with the concrete types here at module load.
from oscilla.engine.models.adventure import Effect as _Effect  # noqa: E402
from oscilla.engine.models.game import PassiveEffect as _PassiveEffect  # noqa: E402

ArchetypeSpec.model_rebuild(_types_namespace={"Effect": _Effect, "PassiveEffect": _PassiveEffect})
