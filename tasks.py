"""Utilities for reading saved task entries."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Dict
import yaml

from config import config

TASKS_FILE = Path(config.TASKS_PATH)
TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)

LOG_FILE = Path(config.LOG_DIR) / "tasks.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def read_tasks(path: Path = TASKS_FILE) -> List[Dict]:
    """Return all task entries from the YAML file."""
    logger.info("Reading tasks from %s", path)
    if not path.exists():
        logger.info("%s does not exist", path)
        return []
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or []
    logger.debug("Loaded %d tasks", len(data))
    return data
