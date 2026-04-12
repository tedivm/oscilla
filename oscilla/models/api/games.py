"""API response models for game discovery endpoints."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from oscilla.engine.registry import ContentRegistry


class GameFeatureFlags(BaseModel):
    """Feature flags derived from a live ContentRegistry.

    Each flag is True only when the registry actually contains manifests for
    that feature — not merely when it is declared in game.yaml. This prevents
    stale flags from reaching the frontend.
    """

    has_skills: bool = Field(description="True when the game has at least one skill manifest.")
    has_quests: bool = Field(description="True when the game has at least one quest manifest.")
    has_archetypes: bool = Field(description="True when the game has at least one archetype manifest.")
    has_ingame_time: bool = Field(description="True when the game declares an in-game time system.")
    has_recipes: bool = Field(description="True when the game has at least one recipe manifest.")
    has_loot_tables: bool = Field(description="True when the game has at least one loot-table manifest.")

    @classmethod
    def from_registry(cls, registry: "ContentRegistry") -> "GameFeatureFlags":
        """Compute feature flags from a loaded ContentRegistry."""
        has_ingame_time = registry.game is not None and registry.game.spec.time is not None
        return cls(
            has_skills=len(registry.skills) > 0,
            has_quests=len(registry.quests) > 0,
            has_archetypes=len(registry.archetypes) > 0,
            has_ingame_time=has_ingame_time,
            has_recipes=len(registry.recipes) > 0,
            has_loot_tables=len(registry.loot_tables) > 0,
        )


class GameRead(BaseModel):
    """Read model for a single loaded game."""

    name: str = Field(description="Machine-readable game name.")
    display_name: str = Field(description="Human-readable game display name.")
    description: str | None = Field(default=None, description="Short game description.")
    features: GameFeatureFlags = Field(description="Feature flags derived from the live content registry.")

    @classmethod
    def from_registry(cls, registry: "ContentRegistry") -> "GameRead":
        """Build a GameRead from a loaded ContentRegistry."""
        assert registry.game is not None
        game_spec = registry.game.spec
        return cls(
            name=registry.game.metadata.name,
            display_name=game_spec.displayName,
            description=game_spec.description or None,
            features=GameFeatureFlags.from_registry(registry=registry),
        )
