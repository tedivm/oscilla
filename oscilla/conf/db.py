from pathlib import Path

import platformdirs
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str | None = Field(
        default=None,
        description=(
            "Full async-driver database URL. When unset, auto-derived as "
            "sqlite+aiosqlite:///<user_data_path('oscilla')>/oscilla.db."
        ),
    )
    games_path: Path = Field(
        default=Path("content"),
        description="Path to the game library root directory containing game package subdirectories.",
    )

    @model_validator(mode="after")
    def derive_sqlite_url(self) -> "DatabaseSettings":
        if self.database_url is None:
            data_dir = platformdirs.user_data_path("oscilla")
            data_dir.mkdir(parents=True, exist_ok=True)
            self.database_url = f"sqlite+aiosqlite:///{data_dir / 'oscilla.db'}"
        return self
