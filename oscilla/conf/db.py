from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str | None = Field(
        default=None,
        description=(
            "Full async-driver database URL. When unset, auto-derived from games_path "
            "as sqlite+aiosqlite:///<games_path.parent>/saves.db."
        ),
    )
    games_path: Path = Field(
        default=Path("content"),
        description="Path to the game library root directory containing game package subdirectories.",
    )

    @model_validator(mode="after")
    def derive_sqlite_url(self) -> "DatabaseSettings":
        if self.database_url is None:
            db_path = self.games_path.parent / "saves.db"
            self.database_url = f"sqlite+aiosqlite:///{db_path.resolve()}"
        return self
