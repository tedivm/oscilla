from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from .cache import CacheSettings
from .db import DatabaseSettings

# Default games path: the `content/` directory at the project root is the library root.
# Override via GAMES_PATH env var to point at a different game library.
_DEFAULT_GAMES_PATH = Path(__file__).parent.parent.parent / "content"
_DEFAULT_FRONTEND_BUILD_PATH = Path("frontend/build")


class Settings(DatabaseSettings, CacheSettings):
    # Multiple inheritance with pydantic-settings does not automatically merge
    # model_config from parent classes, so we must declare it explicitly here.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "oscilla"
    debug: bool = False
    games_path: Path = Field(
        default=_DEFAULT_GAMES_PATH,
        description="Path to the game library root directory containing game package subdirectories.",
    )
    frontend_build_path: Path = Field(
        default=_DEFAULT_FRONTEND_BUILD_PATH,
        description="Path to the SvelteKit static build output. Mounted at /app by the web server.",
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

    # Auth
    stale_session_threshold_minutes: int = Field(
        default=10,
        description="Minutes after which a web session lock is considered stale and eligible for takeover.",
    )
    jwt_secret: SecretStr = Field(
        description="Secret key for JWT signing and itsdangerous HMAC tokens. Must be a long random string.",
    )
    access_token_expire_minutes: int = Field(
        default=15,
        description="Lifetime of JWT access tokens in minutes.",
    )
    refresh_token_expire_days: int = Field(
        default=30,
        description="Lifetime of opaque refresh tokens in days.",
    )
    email_verify_token_expire_hours: int = Field(
        default=24,
        description="Lifetime of email verification tokens in hours.",
    )
    password_reset_token_expire_hours: int = Field(
        default=1,
        description="Lifetime of password reset tokens in hours.",
    )
    require_email_verification: bool = Field(
        default=False,
        description="When True, unverified accounts cannot access game content.",
    )

    # SMTP
    smtp_host: str | None = Field(
        default=None,
        description="SMTP server hostname. Required when email features are used.",
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port.",
    )
    smtp_user: str | None = Field(
        default=None,
        description="SMTP authentication username.",
    )
    smtp_password: SecretStr | None = Field(
        default=None,
        description="SMTP authentication password.",
    )
    smtp_from_address: str | None = Field(
        default=None,
        description="From address used on all outbound emails.",
    )
    smtp_use_tls: bool = Field(
        default=True,
        description="Use STARTTLS when connecting to the SMTP server.",
    )

    # Application
    base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL of the application, used to build absolute links in emails.",
    )
