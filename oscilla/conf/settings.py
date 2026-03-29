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
