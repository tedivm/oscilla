"""Tests for engine signal classes."""

from oscilla.engine.signals import _EndSignal, _GotoSignal


def test_goto_signal_initialization() -> None:
    """Test that _GotoSignal stores the label correctly."""
    signal = _GotoSignal("test-label")
    assert signal.label == "test-label"


def test_end_signal_initialization() -> None:
    """Test that _EndSignal stores the outcome correctly."""
    signal = _EndSignal("defeated")
    assert signal.outcome == "defeated"


def test_goto_signal_is_exception() -> None:
    """Test that _GotoSignal is an exception."""
    signal = _GotoSignal("test")
    assert isinstance(signal, Exception)


def test_end_signal_is_exception() -> None:
    """Test that _EndSignal is an exception."""
    signal = _EndSignal("fled")
    assert isinstance(signal, Exception)
