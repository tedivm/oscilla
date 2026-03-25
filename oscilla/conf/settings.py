from .db import DatabaseSettings
from .cache import CacheSettings


class Settings(DatabaseSettings, CacheSettings):
    project_name: str = "oscilla"
    debug: bool = False
