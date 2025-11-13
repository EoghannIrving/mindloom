"""Unit tests for the :mod:`energy` utilities."""

from __future__ import annotations

import sys
from pathlib import Path

# pylint: disable=wrong-import-position, import-outside-toplevel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from energy import record_entry, read_entries


def test_record_entry_records_energy_mood_and_timestamp(tmp_path: Path):
    """Ensure each entry stores energy, mood, and a recorded timestamp."""
    path = tmp_path / "energy.yaml"
    entry = record_entry(3, "Sad", path)
    assert entry["energy"] == 3
    assert entry["mood"] == "Sad"
    assert "recorded_at" in entry
    assert read_entries(path)[-1] == entry


def test_record_entry_appends_multiple_entries(tmp_path: Path):
    """Each check-in produces its own log entry."""
    path = tmp_path / "energy.yaml"
    first = record_entry(3, "Sad", path)
    second = record_entry(4, "Meh", path)
    entries = read_entries(path)
    assert len(entries) == 2
    assert entries[0]["energy"] == first["energy"]
    assert entries[0]["mood"] == first["mood"]
    assert entries[1]["energy"] == second["energy"]
    assert entries[1]["mood"] == second["mood"]
    assert entries[0]["recorded_at"] == first["recorded_at"]
    assert entries[1]["recorded_at"] == second["recorded_at"]
