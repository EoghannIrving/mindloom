"""CLI script to record daily energy and mood."""

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

parser = argparse.ArgumentParser(description="Record today's energy and mood")
parser.add_argument("energy", type=int, help="Energy level 1-10")
parser.add_argument("mood", type=int, help="Mood level 1-10")

args = parser.parse_args()

logger.info("CLI invoked with energy=%s mood=%s", args.energy, args.mood)
entry = record_entry(args.energy, args.mood)
logger.info("Recorded entry: %s", entry)
print(f"Recorded: {entry}")
