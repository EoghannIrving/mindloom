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
    entry = record_entry(3, "Focused", 2, path)
    assert entry["time_blocks"] == 2
    entries = read_entries(path)
    assert entries[-1]["time_blocks"] == 2


def test_record_entry_overwrites_same_day(tmp_path: Path):
    """Saving multiple times in a day replaces the previous entry."""
    path = tmp_path / "energy.yaml"
    record_entry(3, "Focused", 2, path)
    record_entry(4, "Tired", 1, path)
    entries = read_entries(path)
    assert len(entries) == 1
    assert entries[0]["energy"] == 4
    assert entries[0]["mood"] == "Tired"
    assert entries[0]["time_blocks"] == 1
