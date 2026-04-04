"""Tests verifying that bare-key (shorthand) condition syntax produces a hard LoadError."""

from __future__ import annotations

import textwrap
from pathlib import Path

from oscilla.engine.loader import parse


def test_bare_key_condition_is_hard_error(tmp_path: Path) -> None:
    """A manifest with shorthand condition syntax must produce a LoadError, not silently load."""
    manifest = tmp_path / "bad.yaml"
    manifest.write_text(
        textwrap.dedent("""
            apiVersion: game/v1
            kind: Region
            metadata:
              name: test-region
            spec:
              displayName: Test
              unlock:
                level: 3
        """)
    )

    manifests, errors = parse([manifest])

    assert len(manifests) == 0
    assert len(errors) == 1
    # Error message should mention discriminator or type
    assert "type" in errors[0].message.lower() or "discriminator" in errors[0].message.lower()


def test_explicit_condition_loads_cleanly(tmp_path: Path) -> None:
    """A manifest with explicit type-tagged condition syntax must load without errors."""
    manifest = tmp_path / "good.yaml"
    manifest.write_text(
        textwrap.dedent("""
            apiVersion: game/v1
            kind: Region
            metadata:
              name: test-region
            spec:
              displayName: Test
              unlock:
                type: level
                value: 3
        """)
    )

    manifests, errors = parse([manifest])

    assert len(errors) == 0
    assert len(manifests) == 1
