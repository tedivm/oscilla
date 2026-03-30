"""Tests for crash report path derivation."""

from pathlib import Path
from unittest.mock import patch


def test_crash_report_written_to_data_dir(tmp_path: Path) -> None:
    """write_crash_report() writes the crash file inside the data directory."""
    from oscilla.services.crash import write_crash_report

    exc = RuntimeError("test crash")
    with patch("oscilla.services.crash.platformdirs.user_data_path", return_value=tmp_path):
        crash_path = write_crash_report(exc)

    assert crash_path.parent == tmp_path
    assert crash_path.name.startswith("oscilla-crash-")
    assert crash_path.name.endswith(".log")
    assert crash_path.exists()
