import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from energy import record_entry, read_entries


def test_record_entry_writes_hours_free(tmp_path: Path):
    path = tmp_path / "energy.yaml"
    entry = record_entry(3, "Focused", 2.0, path)
    assert entry["hours_free"] == 2.0
    entries = read_entries(path)
    assert entries[-1]["hours_free"] == 2.0
