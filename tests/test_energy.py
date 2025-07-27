"""Unit tests for the :mod:`energy` utilities."""

from __future__ import annotations

import sys
from pathlib import Path

# pylint: disable=wrong-import-position, import-outside-toplevel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from energy import record_entry, read_entries


def test_record_entry_writes_hours_free(tmp_path: Path):
    """Record an entry and ensure ``hours_free`` is persisted."""
    path = tmp_path / "energy.yaml"
    entry = record_entry(3, "Focused", 2.0, path)
    assert entry["hours_free"] == 2.0
    entries = read_entries(path)
    assert entries[-1]["hours_free"] == 2.0
