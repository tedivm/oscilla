from pathlib import Path

from pydantic import Field

from .cache import CacheSettings
from .db import DatabaseSettings

# Default games path: the `content/` directory at the project root is the library root.
# Override via GAMES_PATH env var to point at a different game library.
_DEFAULT_GAMES_PATH = Path(__file__).parent.parent.parent / "content"


class Settings(DatabaseSettings, CacheSettings):
    project_name: str = "oscilla"
    debug: bool = False
    games_path: Path = Field(
        default=_DEFAULT_GAMES_PATH,
        description="Path to the game library root directory containing game package subdirectories.",
    )

    # Graph node color overrides. Each key maps a manifest kind slug to a hex color.
    # Override any individual color via its environment variable, e.g.:
    #   OSCILLA_GRAPH_COLOR_REGION=#5db85d
    graph_color_game: str = Field(default="#4a90d9", description="Graph node color for game kind.")
    graph_color_region: str = Field(default="#7cb87c", description="Graph node color for region kind.")
    graph_color_location: str = Field(default="#e8c56d", description="Graph node color for location kind.")
    graph_color_adventure: str = Field(default="#d98c4a", description="Graph node color for adventure kind.")
    graph_color_enemy: str = Field(default="#c94040", description="Graph node color for enemy kind.")
    graph_color_item: str = Field(default="#9b6dc0", description="Graph node color for item kind.")
    graph_color_skill: str = Field(default="#5ab8c0", description="Graph node color for skill kind.")
    graph_color_buff: str = Field(default="#a0c055", description="Graph node color for buff kind.")
    graph_color_quest: str = Field(default="#d06fbf", description="Graph node color for quest kind.")
    graph_color_recipe: str = Field(default="#c77a40", description="Graph node color for recipe kind.")
    graph_color_loot_table: str = Field(default="#8a9ba8", description="Graph node color for loot-table kind.")
    graph_color_start: str = Field(default="#aaaaaa", description="Graph node color for start nodes.")
    graph_color_end: str = Field(default="#666666", description="Graph node color for end nodes.")
    graph_color_narrative: str = Field(default="#d0e8f8", description="Graph node color for narrative step nodes.")
    graph_color_combat: str = Field(default="#f8d0d0", description="Graph node color for combat step nodes.")
    graph_color_choice: str = Field(default="#f8f8d0", description="Graph node color for choice step nodes.")
    graph_color_stat_check: str = Field(default="#d8d0f8", description="Graph node color for stat_check step nodes.")
    graph_color_passive: str = Field(default="#d0f8d8", description="Graph node color for passive step nodes.")
