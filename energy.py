"""Utilities for recording daily energy and mood."""

# pylint: disable=duplicate-code

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List, Dict
import logging
import yaml

from config import config

ENERGY_LOG_PATH = Path(config.ENERGY_LOG_PATH)
ENERGY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

LOG_FILE = Path(config.LOG_DIR) / "energy.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def read_entries(path: Path = ENERGY_LOG_PATH) -> List[Dict]:
    """Return all energy entries from the log file."""
    logger.info("Reading energy log from %s", path)
    if not path.exists():
        logger.info("%s does not exist", path)
        return []
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or []
    logger.debug("Loaded %d entries", len(data))
    return data


def record_entry(energy: int, mood: int, path: Path = ENERGY_LOG_PATH) -> Dict:
    """Append a new energy/mood entry and return it."""
    logger.info("Recording energy=%s mood=%s", energy, mood)
    entry = {"date": date.today().isoformat(), "energy": energy, "mood": mood}
    entries = read_entries(path)
    entries.append(entry)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(entries, handle, allow_unicode=True, sort_keys=False)
    logger.info("Wrote %d entries to %s", len(entries), path)
    return entry
