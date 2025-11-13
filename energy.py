"""Utilities for recording daily energy and mood."""

# pylint: disable=duplicate-code

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Dict, List
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


MOOD_EMOJIS = {
    "Sad": "😔",
    "Meh": "😐",
    "Okay": "😊",
    "Joyful": "😍",
}


def _current_timestamp() -> str:
    """Return the timestamp used to identify when the entry was recorded."""

    return datetime.now().isoformat()


def _parse_iso_date(value: str | date | None) -> date | None:
    """Convert various date representations to a ``date`` object."""

    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _entry_timestamp(entry: Dict) -> datetime | None:
    """Return the timestamp used for sorting energy entries."""

    recorded_at = entry.get("recorded_at")
    if isinstance(recorded_at, str):
        try:
            return datetime.fromisoformat(recorded_at)
        except ValueError:
            pass
    stored_date = _parse_iso_date(entry.get("date"))
    if stored_date:
        return datetime.combine(stored_date, datetime.min.time())
    return None


def latest_entry(entries: List[Dict]) -> Dict | None:
    """Return the entry with the most recent timestamp (or the last entry)."""

    if not entries:
        return None
    latest: Dict | None = None
    latest_timestamp: datetime | None = None
    for entry in entries:
        timestamp = _entry_timestamp(entry)
        if timestamp is None:
            continue
        if latest_timestamp is None or timestamp > latest_timestamp:
            latest = entry
            latest_timestamp = timestamp
    if latest:
        return latest
    return entries[-1]


def record_entry(
    energy: int,
    mood: str,
    path: Path = ENERGY_LOG_PATH,
) -> Dict:
    """Record today's energy and mood snapshot, then return the entry."""

    recorded_at = _current_timestamp()
    logger.info(
        "Recording energy entry for date=%s recorded_at=%s",
        date.today().isoformat(),
        recorded_at,
    )
    entry: Dict[str, object] = {
        "date": date.today().isoformat(),
        "energy": energy,
        "mood": mood,
        "recorded_at": recorded_at,
    }
    entries = read_entries(path)
    entries.append(entry)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(entries, handle, allow_unicode=True, sort_keys=False)
    logger.info("Wrote %d entries to %s", len(entries), path)
    return entry
