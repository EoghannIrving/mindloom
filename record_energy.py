"""CLI script to record daily energy, mood and free time blocks."""

# pylint: disable=duplicate-code

import argparse
import logging
from pathlib import Path

from energy import record_entry
from config import config

LOG_FILE = Path(config.LOG_DIR) / "energy.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

parser = argparse.ArgumentParser(
    description="Record today's energy, mood and free time blocks"
)
parser.add_argument("energy", type=int, choices=range(1, 6), help="Energy level 1-5")
parser.add_argument(
    "mood",
    type=str,
    choices=["Sad", "Meh", "Okay", "Joyful"],
    help="Mood",
)
parser.add_argument(
    "time_blocks",
    type=int,
    help="Number of free 15-minute blocks available",
)

args = parser.parse_args()

logger.info("CLI invoked to record energy entry")
entry = record_entry(args.energy, args.mood, args.time_blocks)
logger.info("Recorded energy entry for date=%s", entry.get("date"))
logger.debug("Recorded energy entry details: %s", entry)
print(f"Recorded: {entry}")
