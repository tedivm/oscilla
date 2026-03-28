"""Engine control-flow signals.

Shared between pipeline.py and steps/effects.py to avoid circular imports.
These exceptions are used for internal adventure flow control only —
they never escape AdventurePipeline.run().
"""


class _GotoSignal(Exception):
    """Jump to the top-level adventure step with the given label."""

    def __init__(self, label: str) -> None:
        self.label = label


class _EndSignal(Exception):
    """Terminate the current adventure immediately with the given outcome."""

    def __init__(self, outcome: str) -> None:
        self.outcome = outcome
