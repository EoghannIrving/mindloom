from __future__ import annotations

"""Utilities for recording daily energy and mood."""

from datetime import date
from pathlib import Path
from typing import List, Dict
import yaml

from config import config

ENERGY_LOG_PATH = config.ENERGY_LOG_PATH


def read_entries(path: Path = ENERGY_LOG_PATH) -> List[Dict]:
    """Return all energy entries from the log file."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or []
    return data


def record_entry(energy: int, mood: int, path: Path = ENERGY_LOG_PATH) -> Dict:
    """Append a new energy/mood entry and return it."""
    entry = {"date": date.today().isoformat(), "energy": energy, "mood": mood}
    entries = read_entries(path)
    entries.append(entry)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(entries, handle, allow_unicode=True, sort_keys=False)
    return entry

