"""Normalize recurrence metadata in saved tasks."""

from __future__ import annotations

import argparse
from pathlib import Path
import logging

from config import config
from tasks import read_tasks_raw, write_tasks
from utils.recurrence import normalize_recurrence_value

logger = logging.getLogger(__name__)


def normalize_saved_tasks(path: Path | str | None = None) -> bool:
    """Normalize recurrence values stored in the tasks file."""

    target = Path(path or config.TASKS_PATH)
    if not target.exists():
        logger.warning("Tasks file %s does not exist", target)
        return False

    tasks = read_tasks_raw(target, log=False)
    updated = False
    for task in tasks:
        recurrence = task.get("recurrence")
        if not recurrence:
            continue
        normalized = normalize_recurrence_value(recurrence)
        cleaned = str(recurrence).strip()
        if normalized and normalized != cleaned:
            task["recurrence"] = normalized
            updated = True
        elif not normalized:
            logger.debug(
                "Skipping unsupported recurrence %s for task %s",
                recurrence,
                task.get("id"),
            )

    if updated:
        write_tasks(tasks, target)
        logger.info("Normalized recurrence for %s", target)
    else:
        logger.info("No recurrence changes needed for %s", target)
    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize recurrence metadata in the saved tasks file."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Optional path to `tasks.yaml`. Defaults to the configured TASKS_PATH.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = Path(args.path) if args.path else Path(config.TASKS_PATH)
    normalize_saved_tasks(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
