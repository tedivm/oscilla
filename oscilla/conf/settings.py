from pathlib import Path

from pydantic import Field

from .cache import CacheSettings
from .db import DatabaseSettings

# Default content path: the `content/` directory at the project root.
# Override via CONTENT_PATH env var to point at a third-party content package.
_DEFAULT_CONTENT_PATH = Path(__file__).parent.parent.parent / "content"


class Settings(DatabaseSettings, CacheSettings):
    project_name: str = "oscilla"
    debug: bool = False
    content_path: Path = Field(
        default=_DEFAULT_CONTENT_PATH,
        description="Path to the content directory containing YAML manifests.",
    )
