"""Tests for the password strength validation service."""

import pytest

from oscilla.services.password_strength import validate_password_strength


def test_weak_password_raises() -> None:
    """Common passwords (score=0) raise ValueError."""
    with pytest.raises(ValueError):
        validate_password_strength("password")


def test_keyboard_walk_raises() -> None:
    """Keyboard-walk passwords (score <= 1) raise ValueError."""
    with pytest.raises(ValueError):
        validate_password_strength("qwerty123")


def test_strong_password_passes() -> None:
    """A passphrase (score=4) does not raise."""
    validate_password_strength("correct-horse-battery-staple")


def test_error_message_is_string() -> None:
    """The raised ValueError has a non-empty string message."""
    with pytest.raises(ValueError) as exc_info:
        validate_password_strength("password")
    assert isinstance(str(exc_info.value), str)
    assert len(str(exc_info.value)) > 0
