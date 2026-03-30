"""Tests for DatabaseSettings path derivation logic."""

from pathlib import Path
from unittest.mock import patch

from oscilla.conf.db import DatabaseSettings


def test_derives_oscilla_db_filename(tmp_path: Path) -> None:
    """When DATABASE_URL is not set, the derived URL contains oscilla.db."""
    with patch("oscilla.conf.db.platformdirs.user_data_path", return_value=tmp_path):
        db_settings = DatabaseSettings()
    assert db_settings.database_url is not None
    assert "oscilla.db" in db_settings.database_url


def test_does_not_derive_saves_db(tmp_path: Path) -> None:
    """When DATABASE_URL is not set, the derived URL does not contain saves.db."""
    with patch("oscilla.conf.db.platformdirs.user_data_path", return_value=tmp_path):
        db_settings = DatabaseSettings()
    assert db_settings.database_url is not None
    assert "saves.db" not in db_settings.database_url


def test_derived_url_under_user_data_dir(tmp_path: Path) -> None:
    """When DATABASE_URL is not set, the derived URL path is under user_data_path('oscilla')."""
    with patch("oscilla.conf.db.platformdirs.user_data_path", return_value=tmp_path):
        db_settings = DatabaseSettings()
    assert db_settings.database_url is not None
    assert str(tmp_path) in db_settings.database_url


def test_explicit_database_url_not_overridden() -> None:
    """When database_url is explicitly set, derive_sqlite_url does not change it."""
    explicit_url = "sqlite+aiosqlite:///foo.db"
    db_settings = DatabaseSettings(database_url=explicit_url)
    assert db_settings.database_url == explicit_url


def test_games_path_does_not_affect_db_url(tmp_path: Path) -> None:
    """Changing games_path does not affect the derived database URL."""
    custom_library = tmp_path / "my-library"
    custom_library.mkdir()
    data_dir = tmp_path / "data"
    with patch("oscilla.conf.db.platformdirs.user_data_path", return_value=data_dir):
        db_settings = DatabaseSettings(games_path=custom_library)
    assert db_settings.database_url is not None
    assert str(custom_library) not in db_settings.database_url
    assert str(data_dir) in db_settings.database_url


def test_data_directory_is_created(tmp_path: Path) -> None:
    """After constructing DatabaseSettings(), the data directory exists on disk."""
    data_dir = tmp_path / "oscilla"
    with patch("oscilla.conf.db.platformdirs.user_data_path", return_value=data_dir):
        DatabaseSettings()
    assert data_dir.exists()
    assert data_dir.is_dir()
