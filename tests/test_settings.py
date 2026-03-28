"""Tests for settings configuration."""

import pytest

from oscilla.conf.cache import CacheSettings
from oscilla.conf.settings import Settings
from oscilla.settings import settings


def test_settings_exists() -> None:
    """Test that settings instance exists."""
    assert settings is not None


def test_settings_is_settings_class() -> None:
    """Test that settings is an instance of Settings."""
    assert isinstance(settings, Settings)


def test_settings_has_project_name() -> None:
    """Test that settings has project_name attribute."""
    assert hasattr(settings, "project_name")
    assert settings.project_name is not None
    assert len(settings.project_name) > 0


def test_settings_has_debug() -> None:
    """Test that settings has debug attribute."""
    assert hasattr(settings, "debug")
    assert isinstance(settings.debug, bool)


def test_settings_class_exists() -> None:
    """Test that Settings class exists."""
    assert Settings is not None


def test_settings_inherits_from_cache_settings() -> None:
    """Test that Settings inherits from CacheSettings."""
    assert issubclass(Settings, CacheSettings)


def test_settings_can_be_instantiated() -> None:
    """Test that Settings can be instantiated."""
    test_settings = Settings()
    assert test_settings is not None
    assert isinstance(test_settings, Settings)


def test_cache_settings_exists() -> None:
    """Test that CacheSettings class exists."""
    assert CacheSettings is not None


def test_cache_enabled_attribute() -> None:
    """Test that settings has cache_enabled attribute."""
    assert hasattr(settings, "cache_enabled")
    assert isinstance(settings.cache_enabled, bool)


def test_cache_enabled_default() -> None:
    """Test that cache_enabled defaults to True."""
    test_settings = Settings()
    assert test_settings.cache_enabled is True


def test_cache_redis_host_attribute() -> None:
    """Test that settings has cache_redis_host attribute."""
    assert hasattr(settings, "cache_redis_host")


def test_cache_redis_port_attribute() -> None:
    """Test that settings has cache_redis_port attribute."""
    assert hasattr(settings, "cache_redis_port")
    assert isinstance(settings.cache_redis_port, int)


def test_cache_redis_port_default() -> None:
    """Test that cache_redis_port defaults to 6379."""
    test_settings = Settings()
    assert test_settings.cache_redis_port == 6379


def test_cache_default_ttl_attribute() -> None:
    """Test that settings has cache_default_ttl attribute."""
    assert hasattr(settings, "cache_default_ttl")
    assert isinstance(settings.cache_default_ttl, int)


def test_cache_default_ttl_value() -> None:
    """Test that cache_default_ttl has reasonable default."""
    assert settings.cache_default_ttl == 300  # 5 minutes


def test_cache_persistent_ttl_attribute() -> None:
    """Test that settings has cache_persistent_ttl attribute."""
    assert hasattr(settings, "cache_persistent_ttl")
    assert isinstance(settings.cache_persistent_ttl, int)


def test_cache_persistent_ttl_value() -> None:
    """Test that cache_persistent_ttl has reasonable default."""
    assert settings.cache_persistent_ttl == 3600  # 1 hour


def test_debug_defaults_to_false() -> None:
    """Test that debug defaults to False."""
    test_settings = Settings()
    assert test_settings.debug is False


def test_all_required_attributes_present() -> None:
    """Test that all required attributes are present."""
    required_attrs = [
        "debug",
        "cache_enabled",
        "cache_redis_host",
        "cache_redis_port",
        "cache_default_ttl",
        "cache_persistent_ttl",
    ]

    for attr in required_attrs:
        assert hasattr(settings, attr), f"Missing attribute: {attr}"


def test_settings_can_load_from_env() -> None:
    """Test that settings can be overridden by environment variables."""
    # This tests that the Settings class is properly configured
    # to load from environment variables using pydantic-settings
    test_settings = Settings()
    assert hasattr(test_settings, "model_config") or hasattr(test_settings, "Config")


def test_cache_enabled_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that cache_enabled can be set from environment."""
    monkeypatch.setenv("CACHE_ENABLED", "false")
    test_settings = Settings()
    assert test_settings.cache_enabled is False


def test_debug_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that debug can be set from environment."""
    monkeypatch.setenv("DEBUG", "True")
    test_settings = Settings()
    assert test_settings.debug is True


def test_cache_redis_host_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that cache_redis_host can be set from environment."""
    monkeypatch.setenv("CACHE_REDIS_HOST", "test.redis.com")
    test_settings = Settings()
    assert test_settings.cache_redis_host == "test.redis.com"


def test_cache_redis_port_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that cache_redis_port can be set from environment."""
    monkeypatch.setenv("CACHE_REDIS_PORT", "6380")
    test_settings = Settings()
    assert test_settings.cache_redis_port == 6380


def test_settings_validates_types() -> None:
    """Test that settings validates types correctly."""
    # This is implicitly tested by pydantic, but we verify it works
    test_settings = Settings()
    assert isinstance(test_settings.debug, bool)
    assert isinstance(test_settings.cache_enabled, bool)
    assert isinstance(test_settings.cache_redis_port, int)
    assert isinstance(test_settings.cache_default_ttl, int)
