"""Unit tests for the :mod:`energy` utilities."""

from __future__ import annotations

import sys
from pathlib import Path

# pylint: disable=wrong-import-position, import-outside-toplevel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from energy import record_entry, read_entries


def test_record_entry_writes_time_blocks(tmp_path: Path):
    """Record an entry and ensure ``time_blocks`` is persisted."""
    path = tmp_path / "energy.yaml"
    entry = record_entry(3, "Sad", 2, path)
    assert entry["time_blocks"] == 2
    assert "recorded_at" in entry
    entries = read_entries(path)
    assert entries[-1]["time_blocks"] == 2


def test_record_entry_appends_multiple_entries(tmp_path: Path):
    """Each check-in produces its own log entry."""
    path = tmp_path / "energy.yaml"
    first = record_entry(3, "Sad", 2, path)
    second = record_entry(4, "Meh", 1, path)
    entries = read_entries(path)
    assert len(entries) == 2
    assert entries[0]["energy"] == first["energy"]
    assert entries[0]["mood"] == first["mood"]
    assert entries[1]["energy"] == second["energy"]
    assert entries[1]["mood"] == second["mood"]
    assert entries[1]["time_blocks"] == 1
    assert entries[0]["recorded_at"] == first["recorded_at"]
    assert entries[1]["recorded_at"] == second["recorded_at"]


def test_record_entry_omits_missing_time_blocks(tmp_path: Path):
    """Entries without time block data should not persist a placeholder value."""
    path = tmp_path / "energy.yaml"
    entry = record_entry(4, "Okay", path=path)
    assert "time_blocks" not in entry
    assert "recorded_at" in entry
    entries = read_entries(path)
    assert "time_blocks" not in entries[-1]
